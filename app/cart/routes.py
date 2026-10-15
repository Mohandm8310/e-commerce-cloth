import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import current_user
from app.extensions import db
from app.models.cart import Cart, CartItem, Coupon
from app.models.product import ProductVariant

cart_bp = Blueprint('cart', __name__, url_prefix='/cart')


def get_current_cart():
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not cart:
            cart = Cart(user_id=current_user.id)
            db.session.add(cart)
            db.session.commit()
        return cart

    # Guest session cart
    cart_session_id = session.get('cart_session_id')
    if not cart_session_id:
        cart_session_id = f"guest_{uuid.uuid4().hex}"
        session['cart_session_id'] = cart_session_id

    cart = Cart.query.filter_by(session_id=cart_session_id).first()
    if not cart:
        cart = Cart(session_id=cart_session_id)
        db.session.add(cart)
        db.session.commit()
    return cart


@cart_bp.route('/')
def view_cart():
    cart = get_current_cart()
    subtotal = cart.subtotal

    # Shipping calculation: Free over ₹999, else ₹99
    shipping_fee = 0.0 if (subtotal >= 999.0 or subtotal == 0) else 99.0

    # Coupon validation
    coupon_code = session.get('applied_coupon')
    discount_amount = 0.0
    applied_coupon = None

    if coupon_code and subtotal > 0:
        applied_coupon = Coupon.query.filter_by(code=coupon_code).first()
        if applied_coupon:
            discount_amount, _ = applied_coupon.calculate_discount(subtotal)
        else:
            session.pop('applied_coupon', None)

    # Tax (GST 5% included or calculated)
    tax_amount = round(float(subtotal) * 0.05, 2)
    final_total = max(0.0, round(float(subtotal) - discount_amount + shipping_fee, 2))

    return render_template(
        'cart/cart.html',
        cart=cart,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        discount_amount=discount_amount,
        applied_coupon=applied_coupon,
        tax_amount=tax_amount,
        final_total=final_total
    )


@cart_bp.route('/add', methods=['POST'])
def add_to_cart():
    is_json = request.is_json
    if is_json:
        data = request.get_json() or {}
        variant_id = int(data.get('variant_id')) if data.get('variant_id') is not None else None
        quantity = int(data.get('quantity', 1)) if data.get('quantity') is not None else 1
    else:
        variant_id = request.form.get('variant_id', type=int)
        quantity = request.form.get('quantity', 1, type=int)

    if not variant_id:
        msg = "Please select a size and color."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'warning')
        return redirect(request.referrer or url_for('products.shop'))

    variant = ProductVariant.query.get(variant_id)
    if not variant or not variant.is_active or variant.product.is_deleted:
        msg = "Selected product variant is no longer available."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 404
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('products.shop'))

    cart = get_current_cart()

    try:
        cart.add_item(variant, quantity=quantity)
        db.session.commit()
    except ValueError as e:
        if is_json:
            return jsonify({'success': False, 'message': str(e)}), 400
        flash(str(e), 'warning')
        return redirect(request.referrer or url_for('products.shop'))

    msg = f"Added {variant.product.name} ({variant.size} / {variant.color}) to your shopping cart."
    if is_json:
        return jsonify({
            'success': True,
            'message': msg,
            'cart_count': cart.total_items,
            'cart_subtotal': float(cart.subtotal)
        }), 200

    flash(msg, 'success')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/update', methods=['POST'])
def update_quantity():
    is_json = request.is_json
    if is_json:
        data = request.get_json() or {}
        variant_id = int(data.get('variant_id')) if data.get('variant_id') is not None else None
        quantity = int(data.get('quantity')) if data.get('quantity') is not None else None
    else:
        variant_id = request.form.get('variant_id', type=int)
        quantity = request.form.get('quantity', type=int)

    if variant_id is None or quantity is None:
        return jsonify({'success': False, 'message': 'Missing variant or quantity.'}), 400

    cart = get_current_cart()

    try:
        cart.update_quantity(variant_id, quantity)
        db.session.commit()
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400

    return jsonify({
        'success': True,
        'cart_count': cart.total_items,
        'cart_subtotal': float(cart.subtotal),
        'message': 'Cart updated.'
    }), 200


@cart_bp.route('/remove', methods=['POST'])
def remove_item():
    is_json = request.is_json
    if is_json:
        data = request.get_json() or {}
        variant_id = int(data.get('variant_id')) if data.get('variant_id') is not None else None
    else:
        variant_id = request.form.get('variant_id', type=int)

    cart = get_current_cart()
    cart.remove_item(variant_id)
    db.session.commit()

    if is_json:
        return jsonify({
            'success': True,
            'cart_count': cart.total_items,
            'cart_subtotal': float(cart.subtotal),
            'message': 'Item removed from cart.'
        }), 200

    flash('Item removed from cart.', 'info')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/clear', methods=['POST'])
def clear_cart():
    cart = get_current_cart()
    cart.clear()
    session.pop('applied_coupon', None)
    db.session.commit()
    flash('Your cart has been cleared.', 'info')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/apply-coupon', methods=['POST'])
def apply_coupon():
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    code = data.get('code', '').strip().upper()
    cart = get_current_cart()

    if not code:
        msg = "Please enter a coupon code."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'warning')
        return redirect(url_for('cart.view_cart'))

    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        msg = f"Coupon code '{code}' is invalid."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('cart.view_cart'))

    is_valid, msg = coupon.is_valid_for(cart.subtotal)
    if not is_valid:
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('cart.view_cart'))

    session['applied_coupon'] = coupon.code
    discount, _ = coupon.calculate_discount(cart.subtotal)

    if is_json:
        return jsonify({
            'success': True,
            'message': f"Coupon '{code}' applied! You save ₹{discount:.2f}",
            'discount': discount,
            'coupon_code': code
        }), 200

    flash(f"Coupon '{code}' applied! You saved ₹{discount:.2f}", 'success')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/remove-coupon', methods=['POST'])
def remove_coupon():
    session.pop('applied_coupon', None)
    if request.is_json:
        return jsonify({'success': True, 'message': 'Coupon removed.'}), 200
    flash('Coupon removed.', 'info')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/api/count')
def cart_count():
    cart = get_current_cart()
    return jsonify({
        'count': cart.total_items,
        'subtotal': float(cart.subtotal)
    })
