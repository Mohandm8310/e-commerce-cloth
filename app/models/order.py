import uuid
from datetime import datetime
from app.extensions import db


class Order(db.Model):
    __tablename__ = 'orders'

    VALID_TRANSITIONS = {
        'pending_payment': ['paid', 'cancelled'],
        'paid': ['confirmed', 'cancelled', 'refund_pending'],
        'confirmed': ['processing', 'cancelled', 'refund_pending'],
        'processing': ['shipped', 'cancelled', 'refund_pending'],
        'shipped': ['delivered', 'refund_pending'],
        'delivered': ['refund_pending'],
        'refund_pending': ['refunded'],
        'cancelled': [],
        'refunded': []
    }

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    address_id = db.Column(db.Integer, db.ForeignKey('addresses.id'), nullable=True)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_fee = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_status = db.Column(db.String(30), default='pending', nullable=False)  # pending, paid, failed, refunded
    fulfillment_status = db.Column(db.String(30), default='pending_payment', nullable=False)
    coupon_code = db.Column(db.String(50), nullable=True)
    shipping_address_snapshot = db.Column(db.JSON, nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True)
    carrier = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='orders')
    address = db.relationship('Address', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')
    payment_transactions = db.relationship('PaymentTransaction', back_populates='order', cascade='all, delete-orphan')

    @classmethod
    def generate_order_number(cls):
        date_part = datetime.utcnow().strftime('%Y%m%d')
        unique_part = uuid.uuid4().hex[:6].upper()
        return f"SS-{date_part}-{unique_part}"

    def can_transition_to(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.fulfillment_status, [])
        return new_status in allowed

    def transition_to(self, new_status, reason=None):
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid status transition from '{self.fulfillment_status}' to '{new_status}'. "
                f"Allowed transitions are: {', '.join(self.VALID_TRANSITIONS.get(self.fulfillment_status, [])) or 'None (Terminal state)'}"
            )
        self.fulfillment_status = new_status
        if new_status == 'paid':
            self.payment_status = 'paid'
        elif new_status == 'refunded':
            self.payment_status = 'refunded'
        return True

    @property
    def status_badge_class(self):
        badges = {
            'pending_payment': 'warning',
            'paid': 'info',
            'confirmed': 'primary',
            'processing': 'info',
            'shipped': 'primary',
            'delivered': 'success',
            'cancelled': 'danger',
            'refund_pending': 'warning',
            'refunded': 'secondary'
        }
        return badges.get(self.fulfillment_status, 'secondary')

    def __repr__(self):
        return f'<Order {self.order_number} status={self.fulfillment_status} total={self.total_amount}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=True)
    product_name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    sku = db.Column(db.String(100), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')
    variant = db.relationship('ProductVariant', back_populates='order_items')

    def __repr__(self):
        return f'<OrderItem order_id={self.order_id} sku={self.sku} qty={self.quantity}>'
