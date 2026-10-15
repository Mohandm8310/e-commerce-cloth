from datetime import datetime
from app.extensions import db


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    products = db.relationship('Product', back_populates='category', lazy='dynamic')
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(280), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    brand = db.Column(db.String(100), default='StyleSphere', nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    discount_price = db.Column(db.Numeric(10, 2), nullable=True)
    sku = db.Column(db.String(64), unique=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = db.relationship('Category', back_populates='products')
    images = db.relationship('ProductImage', back_populates='product', cascade='all, delete-orphan', order_by='ProductImage.display_order')
    variants = db.relationship('ProductVariant', back_populates='product', cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', back_populates='product')
    wishlist_items = db.relationship('WishlistItem', back_populates='product', cascade='all, delete-orphan')

    @property
    def primary_image_url(self):
        for img in self.images:
            if img.is_primary:
                return img.image_url
        if self.images:
            return self.images[0].image_url
        return 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&auto=format&fit=crop&q=80'

    @property
    def total_stock(self):
        return sum(v.stock_quantity for v in self.variants if v.is_active)

    @property
    def in_stock(self):
        return self.total_stock > 0

    @property
    def effective_price(self):
        if self.discount_price and self.discount_price > 0 and self.discount_price < self.price:
            return float(self.discount_price)
        return float(self.price)

    @property
    def discount_percent(self):
        if self.discount_price and self.discount_price < self.price:
            diff = float(self.price) - float(self.discount_price)
            return round((diff / float(self.price)) * 100)
        return 0

    @property
    def available_sizes(self):
        sizes = []
        for v in self.variants:
            if v.is_active and v.size not in sizes:
                sizes.append(v.size)
        return sizes

    @property
    def available_colors(self):
        colors = []
        for v in self.variants:
            if v.is_active and v.color not in colors:
                colors.append(v.color)
        return colors

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.is_active = False

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.is_active = True

    def __repr__(self):
        return f'<Product {self.name} sku={self.sku}>'


class ProductImage(db.Model):
    __tablename__ = 'product_images'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(255), nullable=True)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    product = db.relationship('Product', back_populates='images')

    def __repr__(self):
        return f'<ProductImage id={self.id} product_id={self.product_id} primary={self.is_primary}>'


class ProductVariant(db.Model):
    __tablename__ = 'product_variants'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    size = db.Column(db.String(20), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    stock_quantity = db.Column(db.Integer, default=0, nullable=False)
    price_override = db.Column(db.Numeric(10, 2), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    product = db.relationship('Product', back_populates='variants')
    cart_items = db.relationship('CartItem', back_populates='variant', cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', back_populates='variant')
    inventory_movements = db.relationship('InventoryMovement', back_populates='variant')

    @property
    def price(self):
        if self.price_override is not None:
            return float(self.price_override)
        return self.product.effective_price

    def adjust_stock(self, delta, change_type='adjustment', reference_id=None, reference_type=None, notes=None):
        previous = self.stock_quantity
        new_qty = previous + delta
        if new_qty < 0:
            raise ValueError(f"Insufficient stock for variant {self.sku}. Current: {previous}, Requested reduction: {-delta}")
        
        self.stock_quantity = new_qty
        movement = InventoryMovement(
            variant_id=self.id,
            change_type=change_type,
            quantity_change=delta,
            previous_quantity=previous,
            new_quantity=new_qty,
            reference_id=str(reference_id) if reference_id else None,
            reference_type=reference_type,
            notes=notes
        )
        db.session.add(movement)
        return movement

    def __repr__(self):
        return f'<ProductVariant {self.sku} size={self.size} color={self.color} stock={self.stock_quantity}>'


class InventoryMovement(db.Model):
    __tablename__ = 'inventory_movements'

    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=False)
    change_type = db.Column(db.String(50), nullable=False)  # purchase, sale, return, adjustment, reservation
    quantity_change = db.Column(db.Integer, nullable=False)
    previous_quantity = db.Column(db.Integer, nullable=False)
    new_quantity = db.Column(db.Integer, nullable=False)
    reference_id = db.Column(db.String(100), nullable=True)
    reference_type = db.Column(db.String(50), nullable=True)  # order, admin, restock
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    variant = db.relationship('ProductVariant', back_populates='inventory_movements')

    def __repr__(self):
        return f'<InventoryMovement variant_id={self.variant_id} change={self.quantity_change}>'
