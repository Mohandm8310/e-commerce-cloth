from functools import wraps
from datetime import datetime, timedelta
from flask import abort, redirect, url_for, flash, request
from flask_login import current_user
from sqlalchemy import func, distinct, desc
from app.extensions import db
from app.models.user import User, Role, UserSession, LoginEvent
from app.models.product import Product, ProductVariant, Category
from app.models.order import Order, OrderItem
from app.models.analytics import AdminAuditLog


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Administrator authentication required.", "warning")
            return redirect(url_for('admin.login', next=request.url))
        if not current_user.is_admin:
            flash("Access denied. Administrator privileges required.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def get_live_login_analytics():
    """
    Computes accurate, privacy-conscious live customer login monitoring metrics:
    A. Total registered customers: Count unique customer accounts.
    B. Total successful logins: Count successful login events.
    C. Currently logged-in customers: Count distinct customers with valid active session.
    D. Recent active customers: Count distinct customers with activity within 5 minutes.
    E. Currently active sessions: Count valid active sessions.
    """
    now = datetime.utcnow()
    five_mins_ago = now - timedelta(minutes=5)

    # A: Total registered customers
    customer_role = Role.query.filter_by(name='customer').first()
    role_id = customer_role.id if customer_role else 1
    total_customers = User.query.filter_by(role_id=role_id).count()

    # B: Total successful customer logins
    total_successful_logins = LoginEvent.query.filter_by(status='success').count()

    # C: Currently logged-in customers (valid active session)
    logged_in_customers = db.session.query(
        func.count(distinct(UserSession.user_id))
    ).filter(
        UserSession.is_active == True,
        UserSession.expires_at > now
    ).scalar() or 0

    # D: Recent active customers (activity within last 5 minutes)
    recent_active_customers = db.session.query(
        func.count(distinct(UserSession.user_id))
    ).filter(
        UserSession.is_active == True,
        UserSession.last_activity_at >= five_mins_ago
    ).scalar() or 0

    # E: Currently active sessions (including multiple devices per customer)
    active_sessions_count = UserSession.query.filter(
        UserSession.is_active == True,
        UserSession.expires_at > now
    ).count()

    return {
        'total_customers': total_customers,
        'total_successful_logins': total_successful_logins,
        'currently_logged_in_customers': logged_in_customers,
        'recent_active_customers_5m': recent_active_customers,
        'active_sessions_count': active_sessions_count,
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S UTC')
    }


def get_admin_kpis():
    """
    Calculates all required executive and operational KPIs.
    """
    now = datetime.utcnow()
    start_of_today = datetime(now.year, now.month, now.day)

    login_metrics = get_live_login_analytics()

    # Orders
    total_orders = Order.query.count()
    orders_today = Order.query.filter(Order.created_at >= start_of_today).count()
    paid_orders = Order.query.filter(Order.payment_status == 'paid').count()
    pending_orders = Order.query.filter(Order.payment_status == 'pending').count()
    cancelled_orders = Order.query.filter(Order.fulfillment_status == 'cancelled').count()

    # Revenue (verified paid orders only)
    total_revenue = db.session.query(
        func.sum(Order.total_amount)
    ).filter(Order.payment_status == 'paid').scalar() or 0.0

    revenue_today = db.session.query(
        func.sum(Order.total_amount)
    ).filter(
        Order.payment_status == 'paid',
        Order.created_at >= start_of_today
    ).scalar() or 0.0

    # Inventory
    available_products = Product.query.filter_by(is_active=True, is_deleted=False).count()

    # Low-stock variants (< 5) and Out-of-stock (0)
    low_stock_count = ProductVariant.query.filter(
        ProductVariant.is_active == True,
        ProductVariant.stock_quantity > 0,
        ProductVariant.stock_quantity < 5
    ).count()

    out_of_stock_count = ProductVariant.query.filter(
        ProductVariant.is_active == True,
        ProductVariant.stock_quantity == 0
    ).count()

    return {
        **login_metrics,
        'total_orders': total_orders,
        'orders_today': orders_today,
        'paid_orders': paid_orders,
        'pending_orders': pending_orders,
        'cancelled_orders': cancelled_orders,
        'total_revenue': float(total_revenue),
        'revenue_today': float(revenue_today),
        'available_products': available_products,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }


def get_chart_analytics(days=30):
    """
    Produces structured data arrays ready for Chart.js rendering.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # 1. Daily Sales & Orders over time
    sales_query = db.session.query(
        func.date(Order.created_at).label('order_date'),
        func.sum(Order.total_amount).label('daily_revenue'),
        func.count(Order.id).label('daily_orders')
    ).filter(
        Order.created_at >= start_date,
        Order.payment_status == 'paid'
    ).group_by(func.date(Order.created_at)).order_by('order_date').all()

    sales_labels = [str(r.order_date) for r in sales_query]
    sales_revenue = [float(r.daily_revenue or 0) for r in sales_query]
    sales_orders = [int(r.daily_orders or 0) for r in sales_query]

    # Fill empty dates if sparse
    if not sales_labels:
        for i in range(days - 1, -1, -1):
            d = (now - timedelta(days=i)).strftime('%Y-%m-%d')
            sales_labels.append(d)
            sales_revenue.append(0.0)
            sales_orders.append(0)

    # 2. Top-selling products
    top_products_query = db.session.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label('total_qty'),
        func.sum(OrderItem.subtotal).label('total_sales')
    ).join(Order).filter(
        Order.payment_status == 'paid'
    ).group_by(OrderItem.product_name).order_by(desc('total_qty')).limit(5).all()

    top_products_labels = [r.product_name for r in top_products_query]
    top_products_qty = [int(r.total_qty or 0) for r in top_products_query]

    # 3. Revenue by category
    category_revenue_query = db.session.query(
        Category.name,
        func.sum(OrderItem.subtotal).label('cat_revenue')
    ).join(Product, Product.category_id == Category.id
    ).join(OrderItem, OrderItem.product_id == Product.id
    ).join(Order, Order.id == OrderItem.order_id
    ).filter(
        Order.payment_status == 'paid'
    ).group_by(Category.name).all()

    category_labels = [r.name for r in category_revenue_query]
    category_revenue = [float(r.cat_revenue or 0) for r in category_revenue_query]

    # 4. Order status distribution
    status_query = db.session.query(
        Order.fulfillment_status,
        func.count(Order.id).label('count')
    ).group_by(Order.fulfillment_status).all()

    order_status_labels = [r.fulfillment_status.replace('_', ' ').title() for r in status_query]
    order_status_counts = [int(r.count) for r in status_query]

    # 5. Customer registration growth
    reg_query = db.session.query(
        func.date(User.created_at).label('reg_date'),
        func.count(User.id).label('reg_count')
    ).filter(
        User.created_at >= start_date
    ).group_by(func.date(User.created_at)).order_by('reg_date').all()

    reg_labels = [str(r.reg_date) for r in reg_query]
    reg_counts = [int(r.reg_count) for r in reg_query]

    # 6. Login activity over time
    login_act_query = db.session.query(
        func.date(LoginEvent.created_at).label('login_date'),
        func.count(LoginEvent.id).label('logins_count')
    ).filter(
        LoginEvent.created_at >= start_date,
        LoginEvent.status == 'success'
    ).group_by(func.date(LoginEvent.created_at)).order_by('login_date').all()

    login_act_labels = [str(r.login_date) for r in login_act_query]
    login_act_counts = [int(r.logins_count) for r in login_act_query]

    return {
        'sales': {
            'labels': sales_labels,
            'revenue': sales_revenue,
            'orders': sales_orders
        },
        'top_products': {
            'labels': top_products_labels,
            'quantities': top_products_qty
        },
        'category_revenue': {
            'labels': category_labels,
            'revenue': category_revenue
        },
        'order_status': {
            'labels': order_status_labels,
            'counts': order_status_counts
        },
        'registrations': {
            'labels': reg_labels,
            'counts': reg_counts
        },
        'login_activity': {
            'labels': login_act_labels,
            'counts': login_act_counts
        }
    }
