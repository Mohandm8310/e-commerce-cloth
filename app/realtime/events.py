from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio
from app.admin.services import get_live_login_analytics, get_admin_kpis


@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated and current_user.is_admin:
        join_room('admin_room')
        emit('admin_connected', {'message': 'Connected to live admin channel.'})


@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated and current_user.is_admin:
        leave_room('admin_room')


@socketio.on('request_kpi_update')
def handle_request_kpis():
    if current_user.is_authenticated and current_user.is_admin:
        kpis = get_admin_kpis()
        emit('kpi_update', kpis)


def broadcast_login_event(user):
    """
    Broadcasts live customer login event to admin room with updated metrics.
    """
    try:
        metrics = get_live_login_analytics()
        socketio.emit('customer_login', {
            'user_display': user.display_name,
            'metrics': metrics
        }, room='admin_room')
    except Exception as e:
        print(f"SocketIO broadcast_login_event error: {e}")


def broadcast_order_event(order):
    """
    Broadcasts new order placement to admin room.
    """
    try:
        kpis = get_admin_kpis()
        socketio.emit('new_order', {
            'order_number': order.order_number,
            'total': float(order.total_amount),
            'customer': order.user.display_name,
            'kpis': kpis
        }, room='admin_room')
    except Exception as e:
        print(f"SocketIO broadcast_order_event error: {e}")


def broadcast_inventory_event(variant):
    """
    Broadcasts inventory stock movement.
    """
    try:
        socketio.emit('inventory_alert', {
            'sku': variant.sku,
            'product_name': variant.product.name,
            'new_stock': variant.stock_quantity
        }, room='admin_room')
    except Exception as e:
        print(f"SocketIO broadcast_inventory_event error: {e}")
