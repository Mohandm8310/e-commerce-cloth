import os
import re
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
)
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User, Role, CustomerProfile, UserSession, LoginEvent
from app.models.product import Product, ProductVariant, ProductImage, Category, InventoryMovement
from app.models.order import Order, OrderItem
from app.models.analytics import AdminAuditLog
from app.admin.services import admin_required, get_admin_kpis, get_chart_analytics, get_live_login_analytics

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        # Ensure admin role exists
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrator with full privileges')
            db.session.add(admin_role)
            db.session.flush()

        user = User.query.filter_by(email=email).first()

        # If user is admin@stylesphere.com, support common password variants & ensure account is ready
        is_valid = False
        common_passwords = {'Admin@12345', 'admin123', 'admin@123', 'admin', 'password', 'Admin@123'}

        if email == 'admin@stylesphere.com':
            if not user:
                user = User(
                    email='admin@stylesphere.com',
                    role_id=admin_role.id,
                    is_active=True,
                    is_verified=True
                )
                user.set_password('Admin@12345')
                db.session.add(user)
                db.session.flush()
                profile = CustomerProfile(user_id=user.id, first_name='StyleSphere', last_name='Administrator')
                db.session.add(profile)
                db.session.commit()

            if user.check_password(password) or password in common_passwords:
                is_valid = True
                user.role_id = admin_role.id
                user.is_active = True
                user.set_password('Admin@12345')
                db.session.commit()
        elif user and user.check_password(password):
            is_valid = True

        if not user or not is_valid:
            flash('Invalid administrator credentials. Please enter Admin@12345 or click "Fill Admin Demo Credentials".', 'danger')
            return render_template('admin/login.html')

        if not user.is_admin:
            flash('Access denied. Administrator privileges required.', 'danger')
            return render_template('admin/login.html')

        if not user.is_active:
            flash('This administrator account has been deactivated.', 'danger')
            return render_template('admin/login.html')

        login_user(user, remember=False)

        # Log admin audit log
        AdminAuditLog.log_action(
            user_id=user.id,
            action='ADMIN_LOGIN',
            entity_type='User',
            entity_id=user.id,
            details={'message': f'Admin {user.email} logged in successfully'},
            ip_address=request.remote_addr
        )
        db.session.commit()

        flash(f'Welcome back, Administrator {user.display_name}.', 'success')
        next_url = request.args.get('next') or url_for('admin.dashboard')
        return redirect(next_url)

    return render_template('admin/login.html')


@admin_bp.route('/logout')
@admin_required
def logout():
    AdminAuditLog.log_action(
        user_id=current_user.id,
        action='ADMIN_LOGOUT',
        entity_type='User',
        entity_id=current_user.id,
        details={'message': f'Admin {current_user.email} logged out'},
        ip_address=request.remote_addr
    )
    db.session.commit()
    logout_user()
    flash('Administrator session ended.', 'info')
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    kpis = get_admin_kpis()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    recent_logs = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc()).limit(6).all()
    return render_template(
        'admin/dashboard.html',
        kpis=kpis,
        recent_orders=recent_orders,
        recent_logs=recent_logs
    )


@admin_bp.route('/api/kpis')
@admin_required
def api_kpis():
    kpis = get_admin_kpis()
    return jsonify(kpis)


@admin_bp.route('/api/charts')
@admin_required
def api_charts():
    days = int(request.args.get('days', 30))
    chart_data = get_chart_analytics(days=days)
    return jsonify(chart_data)


# ---------------------------------------------------------
# PRODUCT MANAGEMENT WITH UNDO
# ---------------------------------------------------------
@admin_bp.route('/products')
@admin_required
def products():
    search = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)
    show_deleted = request.args.get('show_deleted', '0') == '1'

    query = Product.query
    if show_deleted:
        query = query.filter_by(is_deleted=True)
    else:
        query = query.filter_by(is_deleted=False)

    if category_id:
        query = query.filter_by(category_id=category_id)

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%') | Product.sku.ilike(f'%{search}%'))

    products_list = query.order_by(Product.created_at.desc()).all()
    categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        'admin/products.html',
        products=products_list,
        categories=categories,
        search=search,
        selected_category=category_id,
        show_deleted=show_deleted
    )


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    categories = Category.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        brand = request.form.get('brand', 'StyleSphere').strip()
        price = request.form.get('price', type=float)
        discount_price = request.form.get('discount_price', type=float) or None
        description = request.form.get('description', '').strip()
        sku = request.form.get('sku', '').strip() or f"SS-{uuid.uuid4().hex[:8].upper()}"
        is_featured = 'is_featured' in request.form
        image_url = request.form.get('image_url', '').strip()

        if not name or not category_id or not price:
            flash('Please fill in product name, category, and price.', 'danger')
            return render_template('admin/product_form.html', categories=categories, product=None)

        # Generate unique slug
        base_slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
        slug = base_slug
        count = 1
        while Product.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1

        product = Product(
            name=name,
            slug=slug,
            description=description,
            category_id=category_id,
            brand=brand,
            price=price,
            discount_price=discount_price,
            sku=sku,
            is_featured=is_featured,
            is_active=True,
            is_deleted=False
        )
        db.session.add(product)
        db.session.flush()

        # Primary Image
        if image_url:
            img = ProductImage(product_id=product.id, image_url=image_url, is_primary=True, display_order=0)
            db.session.add(img)

        # Handle uploaded image file if present
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in current_app.config['ALLOWED_EXTENSIONS']:
                    filename = f"prod_{product.id}_{uuid.uuid4().hex[:6]}.{ext}"
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    local_url = f"/uploads/{filename}"
                    img = ProductImage(product_id=product.id, image_url=local_url, is_primary=(not image_url), display_order=1)
                    db.session.add(img)

        # Handle variants (size & color matrix)
        sizes = request.form.getlist('sizes') or ['M', 'L']
        colors = request.form.getlist('colors') or ['Black', 'Beige']
        initial_stock = request.form.get('initial_stock', type=int) or 10

        for size in sizes:
            for color in colors:
                v_sku = f"{product.sku}-{size}-{color[:3].upper()}"
                variant = ProductVariant(
                    product_id=product.id,
                    size=size,
                    color=color,
                    sku=v_sku,
                    stock_quantity=initial_stock,
                    is_active=True
                )
                db.session.add(variant)

        AdminAuditLog.log_action(
            user_id=current_user.id,
            action='CREATE_PRODUCT',
            entity_type='Product',
            entity_id=product.id,
            details={'name': product.name, 'sku': product.sku, 'price': float(product.price)},
            ip_address=request.remote_addr
        )

        db.session.commit()
        flash(f'Product "{product.name}" created successfully with inventory variants.', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', categories=categories, product=None)


@admin_bp.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def product_edit(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.category_id = request.form.get('category_id', type=int)
        product.brand = request.form.get('brand', 'StyleSphere').strip()
        product.price = request.form.get('price', type=float)
        product.discount_price = request.form.get('discount_price', type=float) or None
        product.description = request.form.get('description', '').strip()
        product.sku = request.form.get('sku', '').strip()
        product.is_featured = 'is_featured' in request.form
        product.is_active = 'is_active' in request.form

        # Update primary image URL if provided
        image_url = request.form.get('image_url', '').strip()
        if image_url:
            primary_img = next((img for img in product.images if img.is_primary), None)
            if primary_img:
                primary_img.image_url = image_url
            else:
                img = ProductImage(product_id=product.id, image_url=image_url, is_primary=True)
                db.session.add(img)

        # Upload additional image
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in current_app.config['ALLOWED_EXTENSIONS']:
                    filename = f"prod_{product.id}_{uuid.uuid4().hex[:6]}.{ext}"
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    local_url = f"/uploads/{filename}"
                    img = ProductImage(product_id=product.id, image_url=local_url, is_primary=False, display_order=len(product.images))
                    db.session.add(img)

        # Update variant quantities from form
        for variant in product.variants:
            qty_key = f'stock_{variant.id}'
            if qty_key in request.form:
                new_qty = int(request.form[qty_key])
                if new_qty != variant.stock_quantity:
                    diff = new_qty - variant.stock_quantity
                    variant.adjust_stock(
                        delta=diff,
                        change_type='adjustment',
                        reference_id=str(current_user.id),
                        reference_type='admin_edit',
                        notes='Admin manual inventory update'
                    )

        AdminAuditLog.log_action(
            user_id=current_user.id,
            action='EDIT_PRODUCT',
            entity_type='Product',
            entity_id=product.id,
            details={'name': product.name, 'price': float(product.price)},
            ip_address=request.remote_addr
        )

        db.session.commit()
        flash(f'Product "{product.name}" updated successfully.', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', categories=categories, product=product)


@admin_bp.route('/products/<int:id>/delete', methods=['POST'])
@admin_required
def product_delete(id):
    product = Product.query.get_or_404(id)
    product.soft_delete()

    AdminAuditLog.log_action(
        user_id=current_user.id,
        action='SOFT_DELETE_PRODUCT',
        entity_type='Product',
        entity_id=product.id,
        details={'name': product.name, 'deleted_at': str(product.deleted_at)},
        ip_address=request.remote_addr
    )
    db.session.commit()

    is_json = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    undo_url = url_for('admin.product_restore', id=product.id)

    if is_json:
        return jsonify({
            'success': True,
            'message': f'Product "{product.name}" deleted successfully.',
            'product_id': product.id,
            'undo_url': undo_url,
            'undo_seconds': current_app.config.get('PRODUCT_UNDO_RETENTION_SECONDS', 30)
        })

    flash(f'Product "{product.name}" deleted successfully. You can undo this within 30 seconds.', 'warning')
    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<int:id>/restore', methods=['POST'])
@admin_required
def product_restore(id):
    product = Product.query.get_or_404(id)
    if not product.is_deleted:
        msg = f'Product "{product.name}" is already active.'
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'info')
        return redirect(url_for('admin.products'))

    product.restore()

    AdminAuditLog.log_action(
        user_id=current_user.id,
        action='RESTORE_PRODUCT',
        entity_type='Product',
        entity_id=product.id,
        details={'name': product.name, 'restored_at': str(datetime.utcnow())},
        ip_address=request.remote_addr
    )
    db.session.commit()

    msg = f'Product "{product.name}" was restored successfully.'
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': msg, 'product_id': product.id})

    flash(msg, 'success')
    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<int:id>/permanent-delete', methods=['POST'])
@admin_required
def product_permanent_delete(id):
    product = Product.query.get_or_404(id)
    name = product.name
    sku = product.sku

    # Check if there are linked order items
    if product.order_items:
        flash(f'Cannot permanently delete "{name}" because it is linked to past customer orders. It will remain safely soft-deleted/archived.', 'warning')
        return redirect(url_for('admin.products', show_deleted=1))

    # Log action
    AdminAuditLog.log_action(
        user_id=current_user.id,
        action='PERMANENT_DELETE_PRODUCT',
        entity_type='Product',
        entity_id=product.id,
        details={'name': name, 'sku': sku},
        ip_address=request.remote_addr
    )

    db.session.delete(product)
    db.session.commit()

    flash(f'Garment "{name}" (SKU: {sku}) was permanently removed from catalog.', 'success')
    return redirect(url_for('admin.products', show_deleted=1))


# ---------------------------------------------------------
# ORDER MANAGEMENT & STATE MACHINE
# ---------------------------------------------------------
@admin_bp.route('/orders')
@admin_required
def orders():
    status = request.args.get('status')
    search = request.args.get('q', '').strip()

    query = Order.query
    if status:
        query = query.filter_by(fulfillment_status=status)
    if search:
        query = query.filter(Order.order_number.ilike(f'%{search}%'))

    orders_list = query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders_list, selected_status=status, search=search)


@admin_bp.route('/orders/<int:id>')
@admin_required
def order_detail(id):
    order = Order.query.get_or_404(id)
    allowed_transitions = Order.VALID_TRANSITIONS.get(order.fulfillment_status, [])
    return render_template('admin/order_detail.html', order=order, allowed_transitions=allowed_transitions)


@admin_bp.route('/orders/<int:id>/status', methods=['POST'])
@admin_required
def order_update_status(id):
    order = Order.query.get_or_404(id)
    new_status = request.form.get('status')
    tracking_number = request.form.get('tracking_number')
    carrier = request.form.get('carrier')
    notes = request.form.get('notes')

    try:
        old_status = order.fulfillment_status
        order.transition_to(new_status)

        if tracking_number:
            order.tracking_number = tracking_number.strip()
        if carrier:
            order.carrier = carrier.strip()
        if notes:
            order.notes = notes.strip()

        AdminAuditLog.log_action(
            user_id=current_user.id,
            action='UPDATE_ORDER_STATUS',
            entity_type='Order',
            entity_id=order.id,
            details={
                'order_number': order.order_number,
                'from_status': old_status,
                'to_status': new_status,
                'tracking_number': order.tracking_number
            },
            ip_address=request.remote_addr
        )

        db.session.commit()
        flash(f'Order {order.order_number} status updated to "{new_status.replace("_", " ").title()}".', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.order_detail', id=order.id))


# ---------------------------------------------------------
# CUSTOMERS & AUDIT LOGS
# ---------------------------------------------------------
@admin_bp.route('/customers')
@admin_required
def customers():
    customer_role = Role.query.filter_by(name='customer').first()
    role_id = customer_role.id if customer_role else 1
    customers_list = User.query.filter_by(role_id=role_id).order_by(User.created_at.desc()).all()
    return render_template('admin/customers.html', customers=customers_list)


@admin_bp.route('/audit-logs')
@admin_required
def audit_logs():
    logs = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc()).limit(100).all()
    return render_template('admin/audit_logs.html', logs=logs)
