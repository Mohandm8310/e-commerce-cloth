from app.extensions import db
from app.models.product import Product, ProductVariant
from app.models.order import Order
from app.models.cart import Cart
from app.auth.services import request_otp_for_identifier


def test_twenty_public_pages_render(client, customer_user, sample_product):
    # 1. Home page
    r1 = client.get('/')
    assert r1.status_code == 200
    assert b'StyleSphere' in r1.data

    # 2. Shop all clothing
    r2 = client.get('/shop')
    assert r2.status_code == 200

    # 3. Men's collection
    r3 = client.get('/shop/men')
    assert r3.status_code == 200

    # 4. Women's collection
    r4 = client.get('/shop/women')
    assert r4.status_code == 200

    # 5. New arrivals
    r5 = client.get('/new-arrivals')
    assert r5.status_code == 200

    # 6. Best sellers
    r6 = client.get('/best-sellers')
    assert r6.status_code == 200

    # 7. Product details
    r7 = client.get(f'/products/{sample_product.slug}')
    assert r7.status_code == 200
    assert sample_product.name.encode('utf-8') in r7.data

    # 8. Search results
    r8 = client.get('/search?q=jacket')
    assert r8.status_code == 200

    # 9. Shopping cart
    r9 = client.get('/cart/')
    assert r9.status_code == 200

    # 11. OTP login and registration pages as guest
    r11_login = client.get('/auth/login')
    assert r11_login.status_code == 200

    with client.session_transaction() as sess:
        sess['otp_identifier'] = 'guest@stylesphere.com'
    r11_verify = client.get('/auth/verify-otp')
    assert r11_verify.status_code == 200

    # 16. Contact page
    r16 = client.get('/contact')
    assert r16.status_code == 200

    # 17. About page
    r17 = client.get('/about')
    assert r17.status_code == 200

    # 18. Privacy policy
    r18 = client.get('/privacy')
    assert r18.status_code == 200

    # 19. Terms and conditions
    r19 = client.get('/terms')
    assert r19.status_code == 200

    # 20. Return and refund policy
    r20 = client.get('/returns')
    assert r20.status_code == 200

    # Authenticate customer via real OTP verification
    _, _, _, otp = request_otp_for_identifier(customer_user.email)
    client.post('/auth/verify-otp', data={'identifier': customer_user.email, 'otp_code': otp})

    # Add item to customer's cart
    v = db.session.get(ProductVariant, sample_product.variants[0].id)
    cart = Cart.query.filter_by(user_id=customer_user.id).first()
    if not cart:
        cart = Cart(user_id=customer_user.id)
        db.session.add(cart)
        db.session.flush()
    cart.add_item(v, quantity=1)
    db.session.commit()

    # 10. Checkout (with item in cart)
    r10 = client.get('/checkout/')
    assert r10.status_code == 200

    # 12. Customer profile
    r12 = client.get('/customer/profile')
    assert r12.status_code == 200

    # 13. My orders
    r13 = client.get('/customer/orders')
    assert r13.status_code == 200

    # 14. Order tracking
    test_order = Order(
        order_number="SS-TRACK-TEST-02",
        user_id=customer_user.id,
        subtotal=2000.0,
        total_amount=2000.0,
        fulfillment_status='processing'
    )
    db.session.add(test_order)
    db.session.commit()

    r14 = client.get(f'/customer/orders/{test_order.order_number}/track')
    assert r14.status_code == 200

    # 15. Wishlist
    r15 = client.get('/customer/wishlist')
    assert r15.status_code == 200
