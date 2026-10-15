import os
import sys
from datetime import datetime, timedelta

# Ensure parent directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import Role, User, CustomerProfile, Address, UserSession, LoginEvent
from app.models.product import Category, Product, ProductImage, ProductVariant, InventoryMovement
from app.models.cart import Coupon
from app.models.order import Order, OrderItem
from app.models.payment import PaymentTransaction
from app.models.analytics import AdminAuditLog


def run_seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        print("[1/6] Seeding Roles...")
        roles = {}
        for role_name, desc in [
            ('customer', 'Standard registered customer'),
            ('admin', 'Store administrator with management privileges'),
            ('superadmin', 'System super-administrator')
        ]:
            r = Role.query.filter_by(name=role_name).first()
            if not r:
                r = Role(name=role_name, description=desc)
                db.session.add(r)
                db.session.flush()
            roles[role_name] = r

        print("[2/6] Seeding Administrator and Demo Customer...")
        # Admin account
        admin = User.query.filter_by(email='admin@stylesphere.com').first()
        if not admin:
            admin = User(
                email='admin@stylesphere.com',
                mobile_number='9999999999',
                role_id=roles['admin'].id,
                is_active=True,
                is_verified=True
            )
            admin.set_password('Admin@12345')
            db.session.add(admin)
            db.session.flush()

            admin_profile = CustomerProfile(
                user_id=admin.id,
                first_name='StyleSphere',
                last_name='Administrator'
            )
            db.session.add(admin_profile)

        # Demo Customer account
        customer = User.query.filter_by(email='customer@example.com').first()
        if not customer:
            customer = User(
                email='customer@example.com',
                mobile_number='9876543210',
                role_id=roles['customer'].id,
                is_active=True,
                is_verified=True
            )
            customer.set_password('Customer@12345')
            db.session.add(customer)
            db.session.flush()

            cust_profile = CustomerProfile(
                user_id=customer.id,
                first_name='Ananya',
                last_name='Sharma',
                gender='female'
            )
            db.session.add(cust_profile)

            # Customer Address
            address = Address(
                user_id=customer.id,
                full_name='Ananya Sharma',
                mobile_number='9876543210',
                street_address='Flat 402, Highline Luxury Towers, Indiranagar',
                landmark='Near Metro Pillar 88',
                city='Bengaluru',
                state='Karnataka',
                postal_code='560038',
                country='India',
                is_default=True,
                address_type='home'
            )
            db.session.add(address)

        # Log some login events for customer login analytics
        now = datetime.utcnow()
        for i in range(5):
            login_time = now - timedelta(hours=i * 6)
            db.session.add(LoginEvent(
                user_id=customer.id,
                identifier=customer.email,
                event_type='otp_login',
                status='success',
                ip_address='127.0.0.1',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                created_at=login_time
            ))

        # Active session for customer
        db.session.add(UserSession(
            user_id=customer.id,
            session_token='seed_token_' + os.urandom(16).hex(),
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            is_active=True,
            last_activity_at=now - timedelta(minutes=2),
            expires_at=now + timedelta(days=14)
        ))

        print("[3/6] Seeding Categories...")
        categories_data = [
            {
                'name': "Men's Collection",
                'slug': 'men',
                'description': 'Elevated menswear, tailored essentials, and modern silhouettes.',
                'image_url': 'https://images.unsplash.com/photo-1617137984095-74e4e5e3613f?w=600&auto=format&fit=crop&q=80'
            },
            {
                'name': "Women's Collection",
                'slug': 'women',
                'description': 'Refined contemporary womenswear designed for effortless elegance.',
                'image_url': 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=600&auto=format&fit=crop&q=80'
            },
            {
                'name': 'Accessories & Essentials',
                'slug': 'accessories',
                'description': 'Curated scarves, leather goods, and timeless finishing pieces.',
                'image_url': 'https://images.unsplash.com/photo-1523293182086-7651a899d37f?w=600&auto=format&fit=crop&q=80'
            }
        ]

        cat_objs = {}
        for cdata in categories_data:
            cat = Category.query.filter_by(slug=cdata['slug']).first()
            if not cat:
                cat = Category(
                    name=cdata['name'],
                    slug=cdata['slug'],
                    description=cdata['description'],
                    image_url=cdata['image_url'],
                    is_active=True
                )
                db.session.add(cat)
                db.session.flush()
            cat_objs[cdata['slug']] = cat

        print("[4/6] Seeding Products & Variants...")
        products_data = [
            {
                'name': 'Tailored Italian Wool Blend Blazer',
                'slug': 'tailored-italian-wool-blend-blazer',
                'category': 'men',
                'brand': 'StyleSphere Atelier',
                'price': 6999.00,
                'discount_price': 5499.00,
                'sku': 'SS-MN-BLZ-001',
                'is_featured': True,
                'description': 'Constructed from a premium Italian wool-cashmere blend. Features notched lapels, horn buttons, a double vent, and functional interior welt pockets.',
                'images': [
                    'https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&auto=format&fit=crop&q=80',
                    'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['S', 'M', 'L', 'XL'],
                'colors': ['Charcoal Black', 'Navy Blue', 'Camel'],
                'stock': 12
            },
            {
                'name': 'Silk Charmeuse Evening Slip Dress',
                'slug': 'silk-charmeuse-evening-slip-dress',
                'category': 'women',
                'brand': 'StyleSphere Atelier',
                'price': 4999.00,
                'discount_price': 3999.00,
                'sku': 'SS-WN-DRS-002',
                'is_featured': True,
                'description': 'Pure mulberry silk cut on the bias for a fluid, flattering drape. Subtle cowl neckline, adjustable delicate straps, and a side slit.',
                'images': [
                    'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800&auto=format&fit=crop&q=80',
                    'https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['XS', 'S', 'M', 'L'],
                'colors': ['Champagne Beige', 'Obsidian Black', 'Emerald Green'],
                'stock': 15
            },
            {
                'name': 'Oversized Minimalist Trench Coat',
                'slug': 'oversized-minimalist-trench-coat',
                'category': 'women',
                'brand': 'StyleSphere Studio',
                'price': 7999.00,
                'discount_price': 6499.00,
                'sku': 'SS-WN-COT-003',
                'is_featured': True,
                'description': 'Water-resistant gabardine cotton trench coat with raglan sleeves, a belted waist, storm flap, and horn buckle details.',
                'images': [
                    'https://images.unsplash.com/photo-1544441893-675973e31985?w=800&auto=format&fit=crop&q=80',
                    'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['S', 'M', 'L'],
                'colors': ['Warm Beige', 'Muted Olive', 'Black'],
                'stock': 8
            },
            {
                'name': 'Selvedge Slim-Fit Denim Jeans',
                'slug': 'selvedge-slim-fit-denim-jeans',
                'category': 'men',
                'brand': 'StyleSphere Denim',
                'price': 3499.00,
                'discount_price': 2799.00,
                'sku': 'SS-MN-DNM-004',
                'is_featured': True,
                'description': '13.5oz shuttle-loomed Japanese selvedge denim. Raw indigo finish that ages with bespoke whiskering and honeycombs over time.',
                'images': [
                    'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=800&auto=format&fit=crop&q=80',
                    'https://images.unsplash.com/photo-1542272604-780c96856592?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['30', '32', '34', '36'],
                'colors': ['Raw Indigo', 'Faded Stone Black'],
                'stock': 18
            },
            {
                'name': 'Cashmere Knit Crewneck Sweater',
                'slug': 'cashmere-knit-crewneck-sweater',
                'category': 'women',
                'brand': 'StyleSphere Essentials',
                'price': 5299.00,
                'discount_price': None,
                'sku': 'SS-WN-KNT-005',
                'is_featured': True,
                'description': '100% Grade-A Mongolian cashmere. Ultra-soft 2-ply yarn with ribbed cuffs and hem, designed for everyday warmth and effortless luxury.',
                'images': [
                    'https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['XS', 'S', 'M', 'L'],
                'colors': ['Oatmeal Heather', 'Cream White', 'Soft Charcoal'],
                'stock': 14
            },
            {
                'name': 'Supima Cotton Heavyweight Tee',
                'slug': 'supima-cotton-heavyweight-tee',
                'category': 'men',
                'brand': 'StyleSphere Essentials',
                'price': 1499.00,
                'discount_price': 1199.00,
                'sku': 'SS-MN-TEE-006',
                'is_featured': False,
                'description': '240 GSM long-staple Supima cotton for superior drape and longevity. Pre-shrunk with a clean ribbed collar that retains shape.',
                'images': [
                    'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['S', 'M', 'L', 'XL', 'XXL'],
                'colors': ['Pure White', 'Pitch Black', 'Sand Beige', 'Sage Green'],
                'stock': 35
            },
            {
                'name': 'Pleated Wide-Leg Wool Trousers',
                'slug': 'pleated-wide-leg-wool-trousers',
                'category': 'women',
                'brand': 'StyleSphere Studio',
                'price': 3899.00,
                'discount_price': 3199.00,
                'sku': 'SS-WN-TRS-007',
                'is_featured': False,
                'description': 'High-waisted trousers with sharp double front pleats and a relaxed wide leg. Tailored from crease-resistant wool blend fabric.',
                'images': [
                    'https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['XS', 'S', 'M', 'L'],
                'colors': ['Dark Charcoal', 'Beige Melange', 'Black'],
                'stock': 10
            },
            {
                'name': 'Relaxed Oxford Cotton Button-Down Shirt',
                'slug': 'relaxed-oxford-cotton-button-down-shirt',
                'category': 'men',
                'brand': 'StyleSphere Atelier',
                'price': 2799.00,
                'discount_price': 2299.00,
                'sku': 'SS-MN-SHT-008',
                'is_featured': True,
                'description': 'Classic Oxford cloth weave washed for immediate softness. Features mother-of-pearl buttons, a chest patch pocket, and a box pleat.',
                'images': [
                    'https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['S', 'M', 'L', 'XL'],
                'colors': ['Sky Blue', 'Crisp White', 'Pinstripe Blue'],
                'stock': 22
            },
            {
                'name': 'Handcrafted Full-Grain Leather Chelsea Boots',
                'slug': 'handcrafted-full-grain-leather-chelsea-boots',
                'category': 'accessories',
                'brand': 'StyleSphere Footwear',
                'price': 6499.00,
                'discount_price': 5499.00,
                'sku': 'SS-AC-BOT-009',
                'is_featured': True,
                'description': 'Blake-stitched Italian calfskin leather with elastic side goring and durable Dainite rubber soles. Built to last a lifetime.',
                'images': [
                    'https://images.unsplash.com/photo-1608256246200-53e635b5b65f?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['7', '8', '9', '10', '11'],
                'colors': ['Chestnut Brown', 'Deep Black'],
                'stock': 15
            },
            {
                'name': 'Sculpted Rib Knit Midi Dress',
                'slug': 'sculpted-rib-knit-midi-dress',
                'category': 'women',
                'brand': 'StyleSphere Studio',
                'price': 3699.00,
                'discount_price': 2999.00,
                'sku': 'SS-WN-DRS-010',
                'is_featured': True,
                'description': 'Flattering ribbed knit hugs your contours comfortably while offering flexibility. Square neckline with long sleeves and midi-length hem.',
                'images': [
                    'https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?w=800&auto=format&fit=crop&q=80'
                ],
                'sizes': ['XS', 'S', 'M', 'L'],
                'colors': ['Terracotta', 'Black', 'Ecru Cream'],
                'stock': 16
            }
        ]

        created_products = []
        for pdata in products_data:
            prod = Product.query.filter_by(slug=pdata['slug']).first()
            if not prod:
                cat = cat_objs.get(pdata['category'], list(cat_objs.values())[0])
                prod = Product(
                    name=pdata['name'],
                    slug=pdata['slug'],
                    description=pdata['description'],
                    category_id=cat.id,
                    brand=pdata['brand'],
                    price=pdata['price'],
                    discount_price=pdata['discount_price'],
                    sku=pdata['sku'],
                    is_featured=pdata['is_featured'],
                    is_active=True,
                    is_deleted=False
                )
                db.session.add(prod)
                db.session.flush()

                for idx, img_url in enumerate(pdata['images']):
                    img = ProductImage(
                        product_id=prod.id,
                        image_url=img_url,
                        is_primary=(idx == 0),
                        display_order=idx
                    )
                    db.session.add(img)

                for size in pdata['sizes']:
                    for color in pdata['colors']:
                        v_sku = f"{prod.sku}-{size}-{color.split()[0][:3].upper()}"
                        variant = ProductVariant(
                            product_id=prod.id,
                            size=size,
                            color=color,
                            sku=v_sku,
                            stock_quantity=pdata['stock'],
                            is_active=True
                        )
                        db.session.add(variant)

            created_products.append(prod)

        print("[5/6] Seeding Coupons...")
        coupons = [
            {'code': 'WELCOME10', 'type': 'percentage', 'val': 10.0, 'min_order': 0.0, 'max_disc': 500.0},
            {'code': 'STYLE20', 'type': 'percentage', 'val': 20.0, 'min_order': 1999.0, 'max_disc': 1000.0},
            {'code': 'FLAT500', 'type': 'fixed', 'val': 500.0, 'min_order': 3000.0, 'max_disc': None}
        ]
        for c in coupons:
            if not Coupon.query.filter_by(code=c['code']).first():
                db.session.add(Coupon(
                    code=c['code'],
                    discount_type=c['type'],
                    discount_value=c['val'],
                    min_order_amount=c['min_order'],
                    max_discount_amount=c['max_disc'],
                    is_active=True
                ))

        print("[6/6] Seeding Sample Orders for Analytics...")
        if Order.query.count() == 0 and customer:
            sample_dates = [
                now - timedelta(days=6),
                now - timedelta(days=4),
                now - timedelta(days=2),
                now - timedelta(days=1),
                now - timedelta(hours=3)
            ]
            for idx, o_date in enumerate(sample_dates):
                ord_num = f"SS-SAMPLE-00{idx + 1}"
                p = created_products[idx % len(created_products)]
                v = p.variants[0] if p.variants else None

                unit_p = p.effective_price
                qty = 1 + (idx % 2)
                subtot = unit_p * qty
                total = subtot

                order = Order(
                    order_number=ord_num,
                    user_id=customer.id,
                    address_id=customer.addresses[0].id if customer.addresses else None,
                    subtotal=subtot,
                    shipping_fee=0.00,
                    discount_amount=0.00,
                    tax_amount=round(subtot * 0.05, 2),
                    total_amount=total,
                    payment_status='paid',
                    fulfillment_status='delivered' if idx < 3 else 'processing',
                    shipping_address_snapshot=customer.addresses[0].to_dict() if customer.addresses else {},
                    created_at=o_date,
                    updated_at=o_date
                )
                db.session.add(order)
                db.session.flush()

                if v:
                    db.session.add(OrderItem(
                        order_id=order.id,
                        product_id=p.id,
                        variant_id=v.id,
                        product_name=p.name,
                        size=v.size,
                        color=v.color,
                        sku=v.sku,
                        unit_price=unit_p,
                        quantity=qty,
                        subtotal=subtot,
                        created_at=o_date
                    ))

                db.session.add(PaymentTransaction(
                    order_id=order.id,
                    gateway='razorpay',
                    transaction_id=f"pay_mock_{idx+1}",
                    payment_order_id=f"order_mock_{idx+1}",
                    signature=f"mock_sig_pay_mock_{idx+1}",
                    amount=total,
                    currency='INR',
                    status='captured',
                    created_at=o_date
                ))

        db.session.commit()
        print("\n>>> Seeding completed successfully! <<<")
        print("Admin user: admin@stylesphere.com / Admin@12345")
        print("Demo customer: customer@example.com / 9876543210\n")


if __name__ == '__main__':
    run_seed()
