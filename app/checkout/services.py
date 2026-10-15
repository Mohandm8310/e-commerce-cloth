import hmac
import hashlib
import json
import razorpay
from flask import current_app
from app.extensions import db
from app.models.payment import PaymentTransaction, PaymentWebhookEvent
from app.models.order import Order


def get_razorpay_client():
    key_id = current_app.config.get('RAZORPAY_KEY_ID')
    key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(amount_in_rupees, receipt_id, currency='INR'):
    """
    Creates an official Razorpay order on the server.
    Amount in paise (1 INR = 100 paise).
    """
    amount_in_paise = int(round(amount_in_rupees * 100))
    key_id = current_app.config.get('RAZORPAY_KEY_ID')
    key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')

    # If mock mode enabled or placeholder keys
    if current_app.config.get('MOCK_RAZORPAY') or 'test_stylesphere' in key_id:
        # Generate predictable test order ID
        fake_order_id = f"order_mock_{receipt_id}_{int(amount_in_paise)}"
        return {
            'id': fake_order_id,
            'entity': 'order',
            'amount': amount_in_paise,
            'amount_paid': 0,
            'amount_due': amount_in_paise,
            'currency': currency,
            'receipt': receipt_id,
            'status': 'created',
            'attempts': 0
        }

    client = get_razorpay_client()
    order_data = {
        'amount': amount_in_paise,
        'currency': currency,
        'receipt': str(receipt_id),
        'payment_capture': 1
    }
    return client.order.create(data=order_data)


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verifies payment signature using HMAC SHA256 of order_id|payment_id with secret key.
    """
    secret = current_app.config.get('RAZORPAY_KEY_SECRET', '').encode('utf-8')
    data = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    expected_signature = hmac.new(secret, data, hashlib.sha256).hexdigest()

    # In mock test mode, also allow mock signature if generated accordingly
    if current_app.config.get('MOCK_RAZORPAY') and razorpay_signature == f"mock_sig_{razorpay_payment_id}":
        return True

    return hmac.compare_digest(expected_signature, razorpay_signature)


def verify_webhook_signature(payload_body, signature):
    """
    Verifies Razorpay webhook X-Razorpay-Signature using webhook secret.
    """
    webhook_secret = current_app.config.get('RAZORPAY_WEBHOOK_SECRET', '').encode('utf-8')
    if isinstance(payload_body, str):
        payload_body = payload_body.encode('utf-8')

    expected = hmac.new(webhook_secret, payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def record_payment_transaction(order, gateway_order_id, payment_id, signature, amount, status='captured', raw_data=None):
    txn = PaymentTransaction(
        order_id=order.id,
        gateway='razorpay',
        transaction_id=payment_id,
        payment_order_id=gateway_order_id,
        signature=signature,
        amount=amount,
        currency='INR',
        status=status,
        raw_response=raw_data or {}
    )
    db.session.add(txn)
    return txn
