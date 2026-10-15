import os
import sys
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from config import TestConfig
from app.models.user import Role, User, CustomerProfile, Address
from app.models.product import Category, Product, ProductVariant
from app.models.cart import Coupon


@pytest.fixture(scope='session')
def app():
    test_app = create_app(TestConfig)
    return test_app


@pytest.fixture(autouse=True)
def app_context(app):
    with app.app_context():
        db.create_all()

        # Seed roles
        cust_role = Role.query.filter_by(name='customer').first()
        if not cust_role:
            cust_role = Role(name='customer', description='Customer')
            db.session.add(cust_role)

        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Admin')
            db.session.add(admin_role)

        db.session.commit()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def admin_user(app):
    admin_role = Role.query.filter_by(name='admin').first()
    admin = User(
        email='admin_test@stylesphere.com',
        role_id=admin_role.id,
        is_active=True,
        is_verified=True
    )
    admin.set_password('AdminTest@123')
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def customer_user(app):
    cust_role = Role.query.filter_by(name='customer').first()
    cust = User(
        email='customer_test@example.com',
        mobile_number='9876543211',
        role_id=cust_role.id,
        is_active=True,
        is_verified=True
    )
    cust.set_password('CustTest@123')
    db.session.add(cust)
    db.session.flush()

    profile = CustomerProfile(user_id=cust.id, first_name='Test', last_name='Customer')
    db.session.add(profile)

    addr = Address(
        user_id=cust.id,
        full_name='Test Customer',
        mobile_number='9876543211',
        street_address='123 Fashion Blvd',
        city='Mumbai',
        state='Maharashtra',
        postal_code='400001',
        country='India',
        is_default=True
    )
    db.session.add(addr)
    db.session.commit()
    return cust


@pytest.fixture
def sample_product(app):
    cat = Category(name='Formalwear', slug='formalwear')
    db.session.add(cat)
    db.session.flush()

    prod = Product(
        name='Bespoke Tuxedo Jacket',
        slug='bespoke-tuxedo-jacket',
        description='Silk satin lapel dinner jacket.',
        category_id=cat.id,
        brand='StyleSphere Black Label',
        price=9999.00,
        discount_price=7999.00,
        sku='SS-TST-TUX-001',
        is_active=True,
        is_deleted=False
    )
    db.session.add(prod)
    db.session.flush()

    v1 = ProductVariant(
        product_id=prod.id,
        size='M',
        color='Midnight Black',
        sku='SS-TST-TUX-001-M-BLK',
        stock_quantity=5,
        is_active=True
    )
    v2 = ProductVariant(
        product_id=prod.id,
        size='L',
        color='Midnight Black',
        sku='SS-TST-TUX-001-L-BLK',
        stock_quantity=0,  # Out of stock variant
        is_active=True
    )
    db.session.add_all([v1, v2])
    db.session.commit()
    return prod
