import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models.cart import Cart, Coupon
from app.models.order import Order, OrderItem
from app.models.user import Address
from app.models.payment import PaymentTransaction, PaymentWebhookEvent
from app.checkout.services import (
    create_razorpay_order, verify_razorpay_signature,
    verify_webhook_signature, record_payment_transaction
)

checkout_bp = Blueprint('checkout', __name__, url_prefix='/checkout')


@checkout_bp.route('/')
@login_required
def checkout():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart or not cart.items:
        flash("Your shopping cart is empty.", "warning")
        return redirect(url_for('products.shop'))

    # Revalidate stock for every variant in cart
    for item in cart.items:
        if not item.is_available:
            flash(f"Item '{item.variant.product.name} ({item.variant.size})' has insufficient stock. Please update your cart.", "danger")
            return redirect(url_for('cart.view_cart'))

    subtotal = cart.subtotal
    shipping_fee = 0.0 if (subtotal >= 999.0 or subtotal == 0) else 99.0

    # Coupon validation
    coupon_code = session.get('applied_coupon')
    discount_amount = 0.0
    applied_coupon = None

    if coupon_code:
        applied_coupon = Coupon.query.filter_by(code=coupon_code).first()
        if applied_coupon:
            discount_amount, _ = applied_coupon.calculate_discount(subtotal)
        else:
            session.pop('applied_coupon', None)

    tax_amount = round(float(subtotal) * 0.05, 2)
    final_total = max(0.0, round(float(subtotal) - discount_amount + shipping_fee, 2))

    addresses = Address.query.filter_by(user_id=current_user.id).all()

    return render_template(
        'checkout/checkout.html',
        cart=cart,
        addresses=addresses,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        discount_amount=discount_amount,
        applied_coupon=applied_coupon,
        tax_amount=tax_amount,
        final_total=final_total,
        razorpay_key=current_app.config.get('RAZORPAY_KEY_ID'),
        mock_mode=current_app.config.get('MOCK_RAZORPAY')
    )


@checkout_bp.route('/create-order', methods=['POST'])
@login_required
def create_order():
    data = request.get_json() if request.is_json else request.form

    address_id = data.get('address_id', type=int)

    # If new address provided in form
    if not address_id:
        full_name = data.get('full_name', '').strip()
        mobile = data.get('mobile_number', '').strip()
        street = data.get('street_address', '').strip()
        city = data.get('city', '').strip()
        state = data.get('state', '').strip()
        postal = data.get('postal_code', '').strip()
        landmark = data.get('landmark', '').strip()

        if not all([full_name, mobile, street, city, state, postal]):
            return jsonify({'success': False, 'message': 'Please provide all required shipping address fields.'}), 400

        address = Address(
            user_id=current_user.id,
            full_name=full_name,
            mobile_number=mobile,
            street_address=street,
            landmark=landmark,
            city=city,
            state=state,
            postal_code=postal,
            country='India',
            is_default=True
        )
        db.session.add(address)
        db.session.flush()
        address_id = address.id
    else:
        address = Address.query.filter_by(id=address_id, user_id=current_user.id).first()
        if not address:
            return jsonify({'success': False, 'message': 'Selected address not found.'}), 404

    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart or not cart.items:
        return jsonify({'success': False, 'message': 'Cart is empty.'}), 400

    # Stock validation under database transaction
    for item in cart.items:
        if item.quantity > item.variant.stock_quantity:
            return jsonify({
                'success': False,
                'message': f"Insufficient stock for {item.variant.product.name} ({item.variant.size}). Only {item.variant.stock_quantity} left."
            }), 400

    # Calculate final amounts strictly server-side
    subtotal = float(cart.subtotal)
    shipping_fee = 0.0 if subtotal >= 999.0 else 99.0

    coupon_code = session.get('applied_coupon')
    discount_amount = 0.0
    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code).first()
        if coupon:
            discount_amount, _ = coupon.calculate_discount(subtotal)
            coupon.usage_count += 1

    tax_amount = round(subtotal * 0.05, 2)
    final_total = max(0.0, round(subtotal - discount_amount + shipping_fee, 2))

    order_number = Order.generate_order_number()

    # Create Order record with shipping address snapshot
    order = Order(
        order_number=order_number,
        user_id=current_user.id,
        address_id=address_id,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total_amount=final_total,
        payment_status='pending',
        fulfillment_status='pending_payment',
        coupon_code=coupon_code,
        shipping_address_snapshot=address.to_dict(),
        notes=data.get('notes', '')
    )
    db.session.add(order)
    db.session.flush()

    # Create immutable OrderItem snapshots
    for item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.variant.product_id,
            variant_id=item.variant_id,
            product_name=item.variant.product.name,
            size=item.variant.size,
            color=item.variant.color,
            sku=item.variant.sku,
            unit_price=item.variant.price,
            quantity=item.quantity,
            subtotal=item.line_total
        )
        db.session.add(order_item)

    db.session.commit()

    # Create Razorpay Payment Order on server
    try:
        rzp_order = create_razorpay_order(
            amount_in_rupees=final_total,
            receipt_id=order.order_number
        )
    except Exception as e:
        current_app.logger.error(f"Razorpay order creation failed: {e}")
        return jsonify({'success': False, 'message': 'Payment gateway error. Please try again.'}), 500

    return jsonify({
        'success': True,
        'order_number': order.order_number,
        'order_id': order.id,
        'razorpay_order_id': rzp_order['id'],
        'amount': rzp_order['amount'],
        'currency': 'INR',
        'key_id': current_app.config.get('RAZORPAY_KEY_ID'),
        'customer_name': current_user.display_name,
        'customer_email': current_user.email or '',
        'customer_mobile': current_user.mobile_number or '',
        'mock_mode': current_app.config.get('MOCK_RAZORPAY')
    })


@checkout_bp.route('/verify-payment', methods=['POST'])
@login_required
def verify_payment():
    data = request.get_json()

    order_number = data.get('order_number')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    if not all([order_number, razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return jsonify({'success': False, 'message': 'Missing payment verification parameters.'}), 400

    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first()
    if not order:
        return jsonify({'success': False, 'message': 'Order not found.'}), 404

    # Verify cryptographic signature
    is_valid = verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
    if not is_valid:
        # Record failed attempt
        record_payment_transaction(
            order=order,
            gateway_order_id=razorpay_order_id,
            payment_id=razorpay_payment_id,
            signature=razorpay_signature,
            amount=order.total_amount,
            status='failed',
            raw_data=data
        )
        db.session.commit()
        return jsonify({'success': False, 'message': 'Payment signature verification failed.'}), 400

    # Idempotent verification check: if already paid, return success immediately
    if order.payment_status == 'paid':
        return jsonify({
            'success': True,
            'message': 'Order already processed.',
            'redirect_url': url_for('checkout.order_confirmation', order_number=order.order_number)
        })

    # Transition order state
    order.transition_to('paid')

    # Record successful transaction
    record_payment_transaction(
        order=order,
        gateway_order_id=razorpay_order_id,
        payment_id=razorpay_payment_id,
        signature=razorpay_signature,
        amount=order.total_amount,
        status='captured',
        raw_data=data
    )

    # Deduct stock for each variant and log movement
    for item in order.items:
        if item.variant:
            try:
                item.variant.adjust_stock(
                    delta=-item.quantity,
                    change_type='sale',
                    reference_id=order.order_number,
                    reference_type='order',
                    notes=f"Order {order.order_number} fulfillment deduction"
                )
            except ValueError as e:
                current_app.logger.error(f"Stock adjustment error: {e}")

    # Clear user shopping cart
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if cart:
        cart.clear()

    session.pop('applied_coupon', None)
    db.session.commit()

    # Trigger real-time order update for admin dashboard
    try:
        from app.realtime.events import broadcast_order_event
        broadcast_order_event(order)
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': 'Payment verified and order confirmed!',
        'redirect_url': url_for('checkout.order_confirmation', order_number=order.order_number)
    })


@checkout_bp.route('/order-confirmation/<order_number>')
@login_required
def order_confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return render_template('checkout/order_confirmation.html', order=order)


@csrf.exempt
@checkout_bp.route('/webhook', methods=['POST'])
def razorpay_webhook():
    """
    Webhook endpoint to handle asynchronous payment captures and refunds with idempotency.
    """
    signature = request.headers.get('X-Razorpay-Signature')
    payload_body = request.get_data()

    if not signature or not verify_webhook_signature(payload_body, signature):
        return jsonify({'status': 'invalid signature'}), 400

    try:
        data = json.loads(payload_body.decode('utf-8'))
        event_id = data.get('event_id') or f"evt_{uuid.uuid4().hex}"
        event_type = data.get('event')

        # Idempotency check: prevent duplicate execution
        existing_event = PaymentWebhookEvent.query.filter_by(event_id=event_id).first()
        if existing_event and existing_event.status == 'processed':
            return jsonify({'status': 'already processed'}), 200

        webhook_record = PaymentWebhookEvent(
            event_id=event_id,
            event_type=event_type or 'unknown',
            payload=data,
            status='received'
        )
        db.session.add(webhook_record)
        db.session.flush()

        # Handle payment captured event
        if event_type == 'payment.captured':
            payment_entity = data.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment_entity.get('order_id')
            payment_id = payment_entity.get('id')

            txn = PaymentTransaction.query.filter_by(payment_order_id=order_id).first()
            if txn and txn.order and txn.order.payment_status != 'paid':
                txn.order.transition_to('paid')
                txn.status = 'captured'
                txn.transaction_id = payment_id

        webhook_record.mark_processed('processed')
        db.session.commit()
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        current_app.logger.error(f"Webhook processing error: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
