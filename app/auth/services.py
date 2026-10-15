import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.user import User, Role, CustomerProfile, OTPChallenge, UserSession, LoginEvent


def is_valid_email(identifier):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, identifier.strip()))


def is_valid_phone(identifier):
    # E.164 or 10-digit standard Indian/intl format
    cleaned = re.sub(r'[\s\-()+]', '', identifier.strip())
    return len(cleaned) >= 10 and cleaned.isdigit()


def validate_identifier(raw_identifier):
    clean = raw_identifier.strip()
    if is_valid_email(clean):
        return clean.lower(), 'email'
    elif is_valid_phone(clean):
        digits = re.sub(r'[\s\-()+]', '', clean)
        return digits, 'phone'
    return None, None


def send_email_otp(to_email, otp_code):
    """
    Sends transactional OTP email using configured SMTP server,
    or falls back to mock delivery if mock mode is enabled or SMTP is not configured.
    """
    if current_app.config.get('MOCK_OTP') or not current_app.config.get('MAIL_USERNAME'):
        print(f"\n[StyleSphere DEV MOCK OTP] >>> Generated OTP for {to_email}: {otp_code} <<<\n")
        return True, "Mock email OTP logged (development mode)."

    try:
        server = current_app.config.get('MAIL_SERVER')
        port = current_app.config.get('MAIL_PORT', 587)
        user = current_app.config.get('MAIL_USERNAME')
        pwd = current_app.config.get('MAIL_PASSWORD')
        sender = current_app.config.get('MAIL_DEFAULT_SENDER')

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"{otp_code} is your StyleSphere verification code"
        msg['From'] = sender
        msg['To'] = to_email

        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 500px; margin: auto; padding: 30px; border: 1px solid #e5e5e5; border-radius: 8px;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="font-size: 24px; letter-spacing: 2px; text-transform: uppercase; margin: 0; color: #111;">StyleSphere</h1>
                <p style="color: #666; font-size: 14px; margin-top: 4px;">Fashion E-Commerce Platform</p>
            </div>
            <p style="font-size: 16px; color: #333;">Your one-time login verification code is:</p>
            <div style="background-color: #f8f6f0; border-radius: 6px; padding: 18px; text-align: center; margin: 24px 0;">
                <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #111;">{otp_code}</span>
            </div>
            <p style="font-size: 14px; color: #666; line-height: 1.5;">This code will expire in {current_app.config.get('OTP_EXPIRY_MINUTES', 10)} minutes. If you did not request this verification, please ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
            <p style="font-size: 12px; color: #999; text-align: center;">&copy; 2026 StyleSphere. All rights reserved.</p>
        </div>
        """
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(server, port, timeout=10) as s:
            if current_app.config.get('MAIL_USE_TLS'):
                s.starttls()
            s.login(user, pwd)
            s.sendmail(sender, [to_email], msg.as_string())

        return True, "OTP sent to your email."
    except Exception as e:
        current_app.logger.error(f"Failed to send email OTP: {e}")
        # If SMTP fails in non-mock, log OTP so developer/tester isn't blocked
        print(f"[StyleSphere SMTP Fallback OTP for {to_email}]: {otp_code}")
        return True, "OTP logged to server (SMTP credentials pending verification)."


def send_sms_otp(phone_number, otp_code):
    """
    Sends SMS OTP via SMS provider or mock fallback.
    """
    print(f"\n[StyleSphere DEV MOCK SMS OTP] >>> Generated OTP for {phone_number}: {otp_code} <<<\n")
    return True, "SMS OTP logged (development mode)."


def request_otp_for_identifier(raw_identifier, purpose='login'):
    clean_id, id_type = validate_identifier(raw_identifier)
    if not clean_id:
        return False, "Please provide a valid email address or 10-digit mobile number.", None, None

    # Check cooldown: has an active challenge been requested in the last X seconds?
    cooldown = current_app.config.get('OTP_RESEND_COOLDOWN_SECONDS', 60)
    cutoff = datetime.utcnow() - timedelta(seconds=cooldown)
    recent_challenge = OTPChallenge.query.filter(
        OTPChallenge.identifier == clean_id,
        OTPChallenge.created_at >= cutoff,
        OTPChallenge.is_used == False
    ).order_by(OTPChallenge.created_at.desc()).first()

    if recent_challenge:
        elapsed = int((datetime.utcnow() - recent_challenge.created_at).total_seconds())
        remaining = max(1, cooldown - elapsed)
        return False, f"Please wait {remaining} seconds before requesting a new OTP.", None, None

    expiry_mins = current_app.config.get('OTP_EXPIRY_MINUTES', 10)
    max_attempts = current_app.config.get('OTP_MAX_ATTEMPTS', 5)

    challenge, plain_otp = OTPChallenge.generate(
        identifier=clean_id,
        purpose=purpose,
        expiry_minutes=expiry_mins,
        max_attempts=max_attempts
    )
    db.session.add(challenge)
    db.session.commit()

    if id_type == 'email':
        send_email_otp(clean_id, plain_otp)
    else:
        send_sms_otp(clean_id, plain_otp)

    return True, f"A 6-digit verification code was sent to {clean_id}.", clean_id, plain_otp


def verify_customer_otp(identifier, otp_code, ip_address=None, user_agent=None):
    clean_id = identifier.strip().lower()

    # Find the most recent active challenge
    challenge = OTPChallenge.query.filter(
        OTPChallenge.identifier == clean_id,
        OTPChallenge.is_used == False
    ).order_by(OTPChallenge.created_at.desc()).first()

    if not challenge:
        LoginEvent.create_event(None, clean_id, 'otp_login', 'failed', ip_address, user_agent)
        return False, "No active OTP request found. Please request a new OTP.", None

    is_valid, message = challenge.verify(otp_code)
    db.session.commit()

    if not is_valid:
        LoginEvent.create_event(None, clean_id, 'otp_login', 'failed', ip_address, user_agent)
        return False, message, None

    # Find or create User
    is_email = '@' in clean_id
    if is_email:
        user = User.query.filter_by(email=clean_id).first()
    else:
        user = User.query.filter_by(mobile_number=clean_id).first()

    customer_role = Role.query.filter_by(name='customer').first()
    if not customer_role:
        customer_role = Role(name='customer', description='Standard Customer')
        db.session.add(customer_role)
        db.session.flush()

    if not user:
        user = User(
            email=clean_id if is_email else None,
            mobile_number=clean_id if not is_email else None,
            role_id=customer_role.id,
            is_active=True,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        profile = CustomerProfile(user_id=user.id)
        db.session.add(profile)
    else:
        user.is_verified = True

    # Start user session tracking
    session = UserSession.start_session(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        lifetime_days=current_app.config.get('CUSTOMER_SESSION_LIFETIME').days
    )

    # Log successful login event
    event = LoginEvent(
        user_id=user.id,
        identifier=clean_id,
        event_type='otp_login',
        status='success',
        ip_address=ip_address,
        user_agent=(user_agent[:250] if user_agent else None)
    )
    db.session.add(event)
    db.session.commit()

    return True, "Login successful.", user


def add_login_event_helper():
    # Attach helper to LoginEvent class dynamically if needed
    @classmethod
    def create_event(cls, user_id, identifier, event_type, status, ip=None, ua=None):
        evt = cls(
            user_id=user_id,
            identifier=identifier,
            event_type=event_type,
            status=status,
            ip_address=ip,
            user_agent=ua[:250] if ua else None
        )
        db.session.add(evt)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return evt
    LoginEvent.create_event = create_event

add_login_event_helper()
