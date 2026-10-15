from datetime import datetime
from app.extensions import db


class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transactions'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    gateway = db.Column(db.String(50), default='razorpay', nullable=False)
    transaction_id = db.Column(db.String(120), nullable=True)  # razorpay_payment_id
    payment_order_id = db.Column(db.String(120), nullable=False, index=True)  # razorpay_order_id
    signature = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(10), default='INR', nullable=False)
    status = db.Column(db.String(30), nullable=False)  # created, authorized, captured, failed, refunded
    raw_response = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    order = db.relationship('Order', back_populates='payment_transactions')

    def __repr__(self):
        return f'<PaymentTransaction order_id={self.order_id} txn={self.transaction_id} status={self.status}>'


class PaymentWebhookEvent(db.Model):
    __tablename__ = 'payment_webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(120), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(100), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(30), default='received', nullable=False)  # received, processed, ignored, failed
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def mark_processed(self, status='processed'):
        self.status = status
        self.processed_at = datetime.utcnow()

    def __repr__(self):
        return f'<PaymentWebhookEvent event_id={self.event_id} status={self.status}>'
