from datetime import datetime, timedelta
from app.extensions import db
from app.models.user import User, OTPChallenge, UserSession, LoginEvent
from app.auth.services import request_otp_for_identifier, verify_customer_otp


def test_otp_generation_and_verification(app):
    with app.app_context():
        email = "shopper@stylesphere.com"
        success, msg, clean_id, plain_otp = request_otp_for_identifier(email)
        assert success is True
        assert len(plain_otp) == 6
        assert plain_otp.isdigit()

        # Check DB challenge
        challenge = OTPChallenge.query.filter_by(identifier=clean_id).first()
        assert challenge is not None
        assert challenge.is_used is False
        assert challenge.otp_hash != plain_otp  # Must be salted & hashed

        # Verify correct OTP
        ver_success, ver_msg, user = verify_customer_otp(clean_id, plain_otp)
        assert ver_success is True
        assert user is not None
        assert user.email == email
        assert user.is_verified is True

        # Check challenge is now marked used
        db.session.refresh(challenge)
        assert challenge.is_used is True

        # Check login event recorded
        event = LoginEvent.query.filter_by(user_id=user.id, status='success').first()
        assert event is not None

        # Check active session created
        session = UserSession.query.filter_by(user_id=user.id, is_active=True).first()
        assert session is not None


def test_invalid_otp_rejection(app):
    with app.app_context():
        email = "wrong_code@stylesphere.com"
        request_otp_for_identifier(email)

        # Attempt verification with wrong OTP
        ver_success, ver_msg, user = verify_customer_otp(email, "000000")
        assert ver_success is False
        assert "Invalid OTP" in ver_msg
        assert user is None

        # Check challenge attempt count incremented
        challenge = OTPChallenge.query.filter_by(identifier=email).first()
        assert challenge.attempts == 1


def test_reused_otp_rejection(app):
    with app.app_context():
        email = "reuse_test@stylesphere.com"
        _, _, _, plain_otp = request_otp_for_identifier(email)

        # First verification succeeds
        ok1, _, user1 = verify_customer_otp(email, plain_otp)
        assert ok1 is True

        # Second verification with same OTP must fail
        ok2, msg2, user2 = verify_customer_otp(email, plain_otp)
        assert ok2 is False
        assert "already been used" in msg2 or "No active OTP" in msg2


def test_expired_otp_rejection(app):
    with app.app_context():
        email = "expired_test@stylesphere.com"
        challenge, plain_otp = OTPChallenge.generate(email, expiry_minutes=-5)
        db.session.add(challenge)
        db.session.commit()

        # Attempt verification on expired OTP
        ok, msg = challenge.verify(plain_otp)
        assert ok is False
        assert "expired" in msg.lower()


def test_otp_resend_cooldown(app):
    with app.app_context():
        email = "cooldown_test@stylesphere.com"
        ok1, _, _, _ = request_otp_for_identifier(email)
        assert ok1 is True

        # Immediate second request must trigger cooldown warning
        ok2, msg2, _, _ = request_otp_for_identifier(email)
        assert ok2 is False
        assert "Please wait" in msg2
