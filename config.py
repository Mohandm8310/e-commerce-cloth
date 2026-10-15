import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'stylesphere-dev-secret-key-fashion-2026')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(basedir, 'stylesphere.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True
    }

    # Uploads
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

    # Authentication & OTP
    MOCK_OTP = os.getenv('MOCK_OTP', 'True').lower() in ('true', '1', 'yes')
    OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', 10))
    OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv('OTP_RESEND_COOLDOWN_SECONDS', 60))
    OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', 5))

    # Email
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'StyleSphere Fashion <noreply@stylesphere.com>')

    # SMS
    SMS_PROVIDER = os.getenv('SMS_PROVIDER', 'mock')
    SMS_API_KEY = os.getenv('SMS_API_KEY', '')
    SMS_SENDER_ID = os.getenv('SMS_SENDER_ID', 'STYLES')

    # Razorpay
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_stylesphere1234')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'stylesphere_test_secret_5678')
    RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', 'stylesphere_webhook_secret_9999')
    MOCK_RAZORPAY = os.getenv('MOCK_RAZORPAY', 'True').lower() in ('true', '1', 'yes')

    # App Policies
    PRODUCT_UNDO_RETENTION_SECONDS = int(os.getenv('PRODUCT_UNDO_RETENTION_SECONDS', 30))
    CUSTOMER_SESSION_LIFETIME = timedelta(days=int(os.getenv('CUSTOMER_SESSION_LIFETIME_DAYS', 14)))
    ADMIN_SESSION_LIFETIME = timedelta(minutes=int(os.getenv('ADMIN_SESSION_LIFETIME_MINUTES', 120)))
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_TIME_LIMIT = None


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    MOCK_OTP = True
    MOCK_RAZORPAY = True
