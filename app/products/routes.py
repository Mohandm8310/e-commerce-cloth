from flask import Blueprint, render_template, request, abort
from flask_login import current_user
from sqlalchemy import or_, and_
from app.extensions import db
from app.models.product import Product, ProductVariant, Category
from app.models.cart import Wishlist

products_bp = Blueprint('products', __name__)


@products_bp.route('/')
def home():
    featured_products = Product.query.filter_by(
        is_featured=True, is_active=True, is_deleted=False
    ).limit(8).all()

    new_arrivals = Product.query.filter_by(
        is_active=True, is_deleted=False
    ).order_by(Product.created_at.desc()).limit(8).all()

    categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        'index.html',
        featured_products=featured_products,
        new_arrivals=new_arrivals,
        categories=categories
    )


@products_bp.route('/shop')
def shop():
    category_slug = request.args.get('category')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    size = request.args.get('size')
    color = request.args.get('color')
    in_stock_only = request.args.get('in_stock', '0') == '1'
    sort_by = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = Product.query.filter_by(is_active=True, is_deleted=False)

    selected_category = None
    if category_slug:
        selected_category = Category.query.filter_by(slug=category_slug).first()
        if selected_category:
            # Include child categories if any
            cat_ids = [selected_category.id] + [c.id for c in selected_category.children]
            query = query.filter(Product.category_id.in_(cat_ids))

    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if size or color or in_stock_only:
        variant_conditions = [ProductVariant.is_active == True]
        if size:
            variant_conditions.append(ProductVariant.size == size)
        if color:
            variant_conditions.append(ProductVariant.color.ilike(f'%{color}%'))
        if in_stock_only:
            variant_conditions.append(ProductVariant.stock_quantity > 0)

        query = query.join(Product.variants).filter(and_(*variant_conditions)).distinct()

    # Sorting
    if sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'featured':
        query = query.order_by(Product.is_featured.desc(), Product.created_at.desc())
    else:  # newest
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()

    # Pre-extract distinct sizes and colors for filter sidebar
    available_sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
    available_colors = ['Black', 'White', 'Beige', 'Navy', 'Olive', 'Camel', 'Grey', 'Brown']

    return render_template(
        'products/catalog.html',
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        selected_category=selected_category,
        category_slug=category_slug,
        min_price=min_price,
        max_price=max_price,
        selected_size=size,
        selected_color=color,
        in_stock_only=in_stock_only,
        sort_by=sort_by,
        available_sizes=available_sizes,
        available_colors=available_colors,
        page_title=selected_category.name if selected_category else "All Clothing"
    )


@products_bp.route('/shop/men')
def shop_men():
    return shop_by_category_slug('men')


@products_bp.route('/shop/women')
def shop_women():
    return shop_by_category_slug('women')


def shop_by_category_slug(slug):
    category = Category.query.filter_by(slug=slug).first()
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'newest')

    query = Product.query.filter_by(is_active=True, is_deleted=False)
    if category:
        cat_ids = [category.id] + [c.id for c in category.children]
        query = query.filter(Product.category_id.in_(cat_ids))

    if sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        'products/catalog.html',
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        selected_category=category,
        category_slug=slug,
        sort_by=sort_by,
        page_title=f"{category.name if category else slug.title()} Collection"
    )


@products_bp.route('/new-arrivals')
def new_arrivals():
    page = request.args.get('page', 1, type=int)
    pagination = Product.query.filter_by(
        is_active=True, is_deleted=False
    ).order_by(Product.created_at.desc()).paginate(page=page, per_page=12, error_out=False)

    categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        'products/catalog.html',
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        page_title="New Arrivals"
    )


@products_bp.route('/best-sellers')
def best_sellers():
    page = request.args.get('page', 1, type=int)
    pagination = Product.query.filter_by(
        is_featured=True, is_active=True, is_deleted=False
    ).order_by(Product.created_at.desc()).paginate(page=page, per_page=12, error_out=False)

    categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        'products/catalog.html',
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        page_title="Best Sellers"
    )


@products_bp.route('/search')
def search():
    query_str = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Product.query.filter_by(is_active=True, is_deleted=False)
    if query_str:
        query = query.filter(
            or_(
                Product.name.ilike(f'%{query_str}%'),
                Product.description.ilike(f'%{query_str}%'),
                Product.brand.ilike(f'%{query_str}%'),
                Product.sku.ilike(f'%{query_str}%')
            )
        )

    pagination = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        'products/catalog.html',
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        search_query=query_str,
        page_title=f"Search results for '{query_str}'" if query_str else "All Products"
    )


@products_bp.route('/products/<identifier>')
def product_detail(identifier):
    # Lookup by slug or id
    if identifier.isdigit():
        product = Product.query.filter_by(id=int(identifier), is_deleted=False).first()
    else:
        product = Product.query.filter_by(slug=identifier, is_deleted=False).first()

    if not product:
        abort(404)

    # Check wishlist status if customer is logged in
    in_wishlist = False
    if current_user.is_authenticated:
        wishlist = Wishlist.query.filter_by(user_id=current_user.id).first()
        if wishlist and wishlist.has_product(product.id):
            in_wishlist = True

    # Related products from same category
    related_products = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active == True,
        Product.is_deleted == False
    ).limit(4).all()

    # Active variants formatted for JavaScript interactive selection
    variants_data = [
        {
            'id': v.id,
            'size': v.size,
            'color': v.color,
            'sku': v.sku,
            'stock': v.stock_quantity,
            'price': v.price
        }
        for v in product.variants if v.is_active
    ]

    return render_template(
        'products/detail.html',
        product=product,
        variants_data=variants_data,
        in_wishlist=in_wishlist,
        related_products=related_products
    )


# ---------------------------------------------------------
# INFORMATIONAL & LEGAL PAGES
# ---------------------------------------------------------
@products_bp.route('/contact')
def contact():
    return render_template('pages/contact.html')


@products_bp.route('/about')
def about():
    return render_template('pages/about.html')


@products_bp.route('/privacy')
def privacy():
    return render_template('pages/privacy.html')


@products_bp.route('/terms')
def terms():
    return render_template('pages/terms.html')


@products_bp.route('/returns')
def returns():
    return render_template('pages/returns.html')
