import pytest
from app.extensions import db
from app.models.cart import Cart, Coupon
from app.models.order import Order, OrderItem
from app.models.product import ProductVariant
from app.checkout.services import verify_razorpay_signature


def test_cart_operations_and_stock_limits(app, customer_user, sample_product):
    with app.app_context():
        in_stock_variant = db.session.get(ProductVariant, sample_product.variants[0].id)
        out_of_stock_variant = db.session.get(ProductVariant, sample_product.variants[1].id)

        user = db.session.get(customer_user.__class__, customer_user.id)
        cart = Cart(user_id=user.id)
        db.session.add(cart)
        db.session.commit()

        # Add in-stock variant
        item = cart.add_item(in_stock_variant, quantity=2)
        assert item.quantity == 2
        assert cart.total_items == 2
        assert float(cart.subtotal) == float(in_stock_variant.price) * 2

        # Adding beyond available stock must raise ValueError
        with pytest.raises(ValueError) as exc:
            cart.add_item(in_stock_variant, quantity=10)
        assert "available in stock" in str(exc.value) or "exceeds" in str(exc.value) or "Cannot add" in str(exc.value)

        # Adding out-of-stock variant must raise ValueError
        with pytest.raises(ValueError) as exc2:
            cart.add_item(out_of_stock_variant, quantity=1)
        assert "available in stock" in str(exc2.value)


def test_coupon_discount_calculation(app):
    with app.app_context():
        # 10% off
        c1 = Coupon(code='TEST10', discount_type='percentage', discount_value=10.0, is_active=True)
        # ₹500 fixed off min ₹2000
        c2 = Coupon(code='TEST500', discount_type='fixed', discount_value=500.0, min_order_amount=2000.0, is_active=True)
        db.session.add_all([c1, c2])
        db.session.commit()

        disc1, msg1 = c1.calculate_discount(5000.0)
        assert disc1 == 500.0

        # Below min order
        disc2_fail, msg2_fail = c2.calculate_discount(1500.0)
        assert disc2_fail == 0.0
        assert "Minimum order amount" in msg2_fail

        # Above min order
        disc2_ok, _ = c2.calculate_discount(3000.0)
        assert disc2_ok == 500.0


def test_order_status_state_machine(app, customer_user):
    with app.app_context():
        order = Order(
            order_number=Order.generate_order_number(),
            user_id=customer_user.id,
            subtotal=5000.0,
            shipping_fee=0.0,
            total_amount=5000.0,
            payment_status='pending',
            fulfillment_status='pending_payment'
        )
        db.session.add(order)
        db.session.commit()

        # Valid transition: pending_payment -> paid
        assert order.can_transition_to('paid') is True
        order.transition_to('paid')
        assert order.fulfillment_status == 'paid'
        assert order.payment_status == 'paid'

        # Valid transition: paid -> confirmed
        assert order.can_transition_to('confirmed') is True
        order.transition_to('confirmed')
        assert order.fulfillment_status == 'confirmed'

        # Invalid transition: confirmed cannot jump to delivered directly!
        assert order.can_transition_to('delivered') is False
        with pytest.raises(ValueError):
            order.transition_to('delivered')


def test_razorpay_mock_signature_verification(app):
    with app.app_context():
        order_id = "order_mock_test_123"
        payment_id = "pay_mock_test_456"
        signature = f"mock_sig_{payment_id}"

        # In mock test mode, signature verifies correctly
        is_valid = verify_razorpay_signature(order_id, payment_id, signature)
        assert is_valid is True

        # Malformed signature fails
        bad_sig = verify_razorpay_signature(order_id, payment_id, "bad_invalid_signature")
        assert bad_sig is False
