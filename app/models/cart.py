from datetime import datetime
from app.extensions import db


class Cart(db.Model):
    __tablename__ = 'carts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True)
    session_id = db.Column(db.String(128), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='cart')
    items = db.relationship('CartItem', back_populates='cart', cascade='all, delete-orphan')

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items)

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items)

    def add_item(self, variant, quantity=1):
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if variant.stock_quantity < quantity:
            raise ValueError(f"Only {variant.stock_quantity} item(s) available in stock.")

        existing = next((i for i in self.items if i.variant_id == variant.id), None)
        if existing:
            new_qty = existing.quantity + quantity
            if new_qty > variant.stock_quantity:
                raise ValueError(f"Cannot add {quantity} more. Current in cart: {existing.quantity}, Available: {variant.stock_quantity}")
            existing.quantity = new_qty
            existing.unit_price_at_addition = variant.price
            return existing
        else:
            item = CartItem(
                cart=self,
                variant_id=variant.id,
                quantity=quantity,
                unit_price_at_addition=variant.price
            )
            db.session.add(item)
            return item

    def update_quantity(self, variant_id, quantity):
        existing = next((i for i in self.items if i.variant_id == variant_id), None)
        if not existing:
            raise ValueError("Item not found in cart.")
        if quantity <= 0:
            db.session.delete(existing)
            return None
        if quantity > existing.variant.stock_quantity:
            raise ValueError(f"Requested {quantity} exceeds available stock of {existing.variant.stock_quantity}.")
        existing.quantity = quantity
        return existing

    def remove_item(self, variant_id):
        existing = next((i for i in self.items if i.variant_id == variant_id), None)
        if existing:
            db.session.delete(existing)
            return True
        return False

    def clear(self):
        for item in list(self.items):
            db.session.delete(item)

    def __repr__(self):
        return f'<Cart id={self.id} user_id={self.user_id} items_count={self.total_items}>'


class CartItem(db.Model):
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price_at_addition = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cart = db.relationship('Cart', back_populates='items')
    variant = db.relationship('ProductVariant', back_populates='cart_items')

    @property
    def current_unit_price(self):
        if self.variant:
            return self.variant.price
        return float(self.unit_price_at_addition)

    @property
    def line_total(self):
        return float(self.current_unit_price) * self.quantity

    @property
    def is_available(self):
        return self.variant.is_active and not self.variant.product.is_deleted and self.variant.stock_quantity >= self.quantity

    def __repr__(self):
        return f'<CartItem cart_id={self.cart_id} variant_id={self.variant_id} qty={self.quantity}>'


class Wishlist(db.Model):
    __tablename__ = 'wishlists'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='wishlist')
    items = db.relationship('WishlistItem', back_populates='wishlist', cascade='all, delete-orphan')

    def add_product(self, product_id):
        existing = next((i for i in self.items if i.product_id == product_id), None)
        if not existing:
            item = WishlistItem(wishlist_id=self.id, product_id=product_id)
            db.session.add(item)
            return item
        return existing

    def remove_product(self, product_id):
        existing = next((i for i in self.items if i.product_id == product_id), None)
        if existing:
            db.session.delete(existing)
            return True
        return False

    def has_product(self, product_id):
        return any(i.product_id == product_id for i in self.items)

    def __repr__(self):
        return f'<Wishlist user_id={self.user_id} items={len(self.items)}>'


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'

    id = db.Column(db.Integer, primary_key=True)
    wishlist_id = db.Column(db.Integer, db.ForeignKey('wishlists.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    wishlist = db.relationship('Wishlist', back_populates='items')
    product = db.relationship('Product', back_populates='wishlist_items')

    def __repr__(self):
        return f'<WishlistItem wishlist_id={self.wishlist_id} product_id={self.product_id}>'


class Coupon(db.Model):
    __tablename__ = 'coupons'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_type = db.Column(db.String(20), default='percentage', nullable=False)  # percentage, fixed
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    min_order_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    max_discount_amount = db.Column(db.Numeric(10, 2), nullable=True)
    usage_limit = db.Column(db.Integer, nullable=True)
    usage_count = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def is_valid_for(self, subtotal):
        if not self.is_active:
            return False, "This coupon is no longer active."
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False, "This coupon has expired."
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False, "This coupon's usage limit has been reached."
        if float(subtotal) < float(self.min_order_amount):
            return False, f"Minimum order amount for this coupon is ₹{float(self.min_order_amount):.2f}"
        return True, "Coupon is valid."

    def calculate_discount(self, subtotal):
        valid, msg = self.is_valid_for(subtotal)
        if not valid:
            return 0.0, msg

        sub = float(subtotal)
        val = float(self.discount_value)
        if self.discount_type == 'percentage':
            discount = (sub * val) / 100.0
            if self.max_discount_amount:
                discount = min(discount, float(self.max_discount_amount))
        else:
            discount = min(sub, val)
        return round(discount, 2), "Discount applied successfully."

    def __repr__(self):
        return f'<Coupon {self.code} type={self.discount_type} value={self.discount_value}>'
