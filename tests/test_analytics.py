from datetime import datetime, timedelta
from app.extensions import db
from app.models.user import User, Role, UserSession, LoginEvent
from app.models.order import Order
from app.admin.services import get_live_login_analytics, get_admin_kpis


def test_customer_login_monitoring_metrics(app, customer_user):
    with app.app_context():
        # Setup multiple sessions and login events for customer
        now = datetime.utcnow()

        # Record 3 successful login events for this single customer
        for i in range(3):
            db.session.add(LoginEvent(
                user_id=customer_user.id,
                identifier=customer_user.email,
                status='success',
                event_type='otp_login',
                created_at=now - timedelta(minutes=i * 10)
            ))

        # Add 2 active sessions (e.g. mobile and desktop)
        s1 = UserSession.start_session(customer_user.id, lifetime_days=7)
        s1.last_activity_at = now - timedelta(minutes=1)  # Recent active within 5m

        s2 = UserSession.start_session(customer_user.id, lifetime_days=7)
        s2.last_activity_at = now - timedelta(hours=2)   # Not recent active (<5m)

        db.session.commit()

        metrics = get_live_login_analytics()

        # Metric A: Registered customers (should be at least 1 customer)
        assert metrics['total_customers'] >= 1

        # Metric B: Total successful logins (cumulative events count >= 3)
        assert metrics['total_successful_logins'] >= 3

        # Metric C: Currently logged-in customers (unique customers with active session = 1)
        assert metrics['currently_logged_in_customers'] >= 1

        # Metric D: Recent active customers within 5m (customer_user had activity 1 min ago = 1)
        assert metrics['recent_active_customers_5m'] >= 1

        # Metric E: Currently active sessions (at least s1 and s2 = 2)
        assert metrics['active_sessions_count'] >= 2


def test_admin_kpis_calculation(app, customer_user):
    with app.app_context():
        # Create paid order and pending order
        o1 = Order(
            order_number="SS-KPI-01",
            user_id=customer_user.id,
            subtotal=2000.0,
            total_amount=2000.0,
            payment_status='paid',
            fulfillment_status='paid'
        )
        o2 = Order(
            order_number="SS-KPI-02",
            user_id=customer_user.id,
            subtotal=1500.0,
            total_amount=1500.0,
            payment_status='pending',
            fulfillment_status='pending_payment'
        )
        db.session.add_all([o1, o2])
        db.session.commit()

        kpis = get_admin_kpis()
        assert kpis['total_orders'] >= 2
        assert kpis['paid_orders'] >= 1
        assert kpis['pending_orders'] >= 1
        assert kpis['total_revenue'] >= 2000.0
