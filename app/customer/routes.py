from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import CustomerProfile, Address
from app.models.order import Order
from app.models.cart import Wishlist, WishlistItem, Cart
from app.models.product import Product, ProductVariant

customer_bp = Blueprint('customer', __name__, url_prefix='/customer')


@customer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user
    profile = user.profile
    if not profile:
        profile = CustomerProfile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == 'POST':
        profile.first_name = request.form.get('first_name', '').strip()
        profile.last_name = request.form.get('last_name', '').strip()
        profile.gender = request.form.get('gender')
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('customer.profile'))

    addresses = Address.query.filter_by(user_id=user.id).order_by(Address.is_default.desc()).all()
    recent_orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).limit(5).all()

    return render_template('customer/profile.html', user=user, profile=profile, addresses=addresses, recent_orders=recent_orders)


@customer_bp.route('/addresses/new', methods=['POST'])
@login_required
def add_address():
    full_name = request.form.get('full_name', '').strip()
    mobile = request.form.get('mobile_number', '').strip()
    street = request.form.get('street_address', '').strip()
    landmark = request.form.get('landmark', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    postal = request.form.get('postal_code', '').strip()
    address_type = request.form.get('address_type', 'home')
    is_default = 'is_default' in request.form

    if not all([full_name, mobile, street, city, state, postal]):
        flash('Please fill in all required address fields.', 'danger')
        return redirect(url_for('customer.profile'))

    if is_default:
        Address.query.filter_by(user_id=current_user.id).update({'is_default': False})

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
        address_type=address_type,
        is_default=is_default
    )
    db.session.add(address)
    db.session.commit()

    flash('New address added successfully.', 'success')
    return redirect(url_for('customer.profile'))


@customer_bp.route('/addresses/<int:id>/delete', methods=['POST'])
@login_required
def delete_address(id):
    address = Address.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(address)
    db.session.commit()
    flash('Address removed.', 'info')
    return redirect(url_for('customer.profile'))


@customer_bp.route('/orders')
@login_required
def orders():
    customer_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('customer/orders.html', orders=customer_orders)


@customer_bp.route('/orders/<order_number>/track')
@login_required
def track_order(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()

    # Timeline stage index calculation
    stages = [
        {'id': 'placed', 'name': 'Order Placed', 'desc': 'Order created and payment verified', 'completed': True},
        {'id': 'confirmed', 'name': 'Confirmed', 'desc': 'Order confirmed by StyleSphere', 'completed': False},
        {'id': 'processing', 'name': 'Processing', 'desc': 'Packed in our fashion warehouse', 'completed': False},
        {'id': 'shipped', 'name': 'Shipped', 'desc': 'Handed over to delivery carrier', 'completed': False},
        {'id': 'delivered', 'name': 'Delivered', 'desc': 'Package delivered to your address', 'completed': False}
    ]

    status = order.fulfillment_status
    if status in ('paid', 'confirmed', 'processing', 'shipped', 'delivered'):
        stages[0]['completed'] = True
    if status in ('confirmed', 'processing', 'shipped', 'delivered'):
        stages[1]['completed'] = True
    if status in ('processing', 'shipped', 'delivered'):
        stages[2]['completed'] = True
    if status in ('shipped', 'delivered'):
        stages[3]['completed'] = True
    if status == 'delivered':
        stages[4]['completed'] = True

    return render_template('customer/track_order.html', order=order, stages=stages)


@customer_bp.route('/wishlist')
@login_required
def wishlist():
    user_wishlist = Wishlist.query.filter_by(user_id=current_user.id).first()
    items = user_wishlist.items if user_wishlist else []
    return render_template('customer/wishlist.html', items=items)


@customer_bp.route('/wishlist/toggle', methods=['POST'])
@login_required
def toggle_wishlist():
    if request.is_json:
        data = request.get_json() or {}
        product_id = int(data.get('product_id')) if data.get('product_id') is not None else None
    else:
        product_id = request.form.get('product_id', type=int)

    if not product_id:
        return jsonify({'success': False, 'message': 'Missing product ID.'}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({'success': False, 'message': 'Product not found.'}), 404

    user_wishlist = Wishlist.query.filter_by(user_id=current_user.id).first()
    if not user_wishlist:
        user_wishlist = Wishlist(user_id=current_user.id)
        db.session.add(user_wishlist)
        db.session.flush()

    if user_wishlist.has_product(product_id):
        user_wishlist.remove_product(product_id)
        db.session.commit()
        return jsonify({'success': True, 'in_wishlist': False, 'message': f'{product.name} removed from wishlist.'})
    else:
        user_wishlist.add_product(product_id)
        db.session.commit()
        return jsonify({'success': True, 'in_wishlist': True, 'message': f'{product.name} added to your wishlist.'})


@customer_bp.route('/wishlist/move-to-cart', methods=['POST'])
@login_required
def wishlist_move_to_cart():
    if request.is_json:
        data = request.get_json() or {}
        product_id = int(data.get('product_id')) if data.get('product_id') is not None else None
    else:
        product_id = request.form.get('product_id', type=int)

    if not product_id:
        return jsonify({'success': False, 'message': 'Missing product ID.'}), 400

    product = Product.query.get_or_404(product_id)
    # Pick first in-stock variant
    variant = next((v for v in product.variants if v.is_active and v.stock_quantity > 0), None)
    if not variant:
        return jsonify({'success': False, 'message': 'Product is currently out of stock.'}), 400

    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.flush()

    cart.add_item(variant, quantity=1)

    # Remove from wishlist
    user_wishlist = Wishlist.query.filter_by(user_id=current_user.id).first()
    if user_wishlist:
        user_wishlist.remove_product(product_id)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{product.name} moved to your shopping cart!',
        'cart_count': cart.total_items
    })
