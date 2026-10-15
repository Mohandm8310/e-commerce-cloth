import os
import hashlib
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship('User', back_populates='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(191), unique=True, nullable=True, index=True)
    mobile_number = db.Column(db.String(20), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False, default=1)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    role = db.relationship('Role', back_populates='users')
    profile = db.relationship('CustomerProfile', back_populates='user', uselist=False, cascade='all, delete-orphan')
    sessions = db.relationship('UserSession', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    login_events = db.relationship('LoginEvent', back_populates='user', lazy='dynamic')
    addresses = db.relationship('Address', back_populates='user', cascade='all, delete-orphan')
    orders = db.relationship('Order', back_populates='user', lazy='dynamic')
    cart = db.relationship('Cart', back_populates='user', uselist=False, cascade='all, delete-orphan')
    wishlist = db.relationship('Wishlist', back_populates='user', uselist=False, cascade='all, delete-orphan')
    audit_logs = db.relationship('AdminAuditLog', back_populates='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role and self.role.name in ('admin', 'superadmin')

    @property
    def display_name(self):
        if self.profile and (self.profile.first_name or self.profile.last_name):
            first = self.profile.first_name or ''
            last = self.profile.last_name or ''
            full = f"{first} {last}".strip()
            if full:
                return full
        if self.email:
            return self.email.split('@')[0]
        if self.mobile_number:
            return self.mobile_number
        return f"Customer #{self.id}"

    def __repr__(self):
        return f'<User {self.email or self.mobile_number} role={self.role.name if self.role else None}>'


class CustomerProfile(db.Model):
    __tablename__ = 'customer_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='profile')

    def __repr__(self):
        return f'<CustomerProfile user_id={self.user_id}>'


class OTPChallenge(db.Model):
    __tablename__ = 'otp_challenges'

    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(191), nullable=False, index=True)
    otp_hash = db.Column(db.String(255), nullable=False)
    salt = db.Column(db.String(64), nullable=False)
    purpose = db.Column(db.String(50), nullable=False, default='login')
    attempts = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=5, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @classmethod
    def generate(cls, identifier, purpose='login', expiry_minutes=10, max_attempts=5):
        # 6-digit cryptographically secure OTP
        otp_plain = f"{secrets.randbelow(900000) + 100000:06d}"
        salt = secrets.token_hex(16)
        salted_otp = f"{otp_plain}{salt}".encode('utf-8')
        otp_hash = hashlib.sha256(salted_otp).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)

        challenge = cls(
            identifier=identifier.strip().lower(),
            otp_hash=otp_hash,
            salt=salt,
            purpose=purpose,
            attempts=0,
            max_attempts=max_attempts,
            is_used=False,
            expires_at=expires_at
        )
        return challenge, otp_plain

    def verify(self, plain_otp):
        if self.is_used:
            return False, "OTP has already been used."
        if datetime.utcnow() > self.expires_at:
            return False, "OTP has expired. Please request a new one."
        if self.attempts >= self.max_attempts:
            return False, "Maximum verification attempts exceeded. Please request a new OTP."

        self.attempts += 1
        salted_input = f"{plain_otp.strip()}{self.salt}".encode('utf-8')
        input_hash = hashlib.sha256(salted_input).hexdigest()

        if secrets.compare_digest(input_hash, self.otp_hash):
            self.is_used = True
            return True, "OTP verified successfully."
        else:
            remaining = self.max_attempts - self.attempts
            if remaining > 0:
                return False, f"Invalid OTP. {remaining} attempt(s) remaining."
            else:
                return False, "Invalid OTP. Maximum attempts reached."

    def __repr__(self):
        return f'<OTPChallenge identifier={self.identifier} used={self.is_used}>'


class UserSession(db.Model):
    __tablename__ = 'user_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_token = db.Column(db.String(128), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='sessions')

    @classmethod
    def start_session(cls, user_id, ip_address=None, user_agent=None, lifetime_days=14):
        token = secrets.token_urlsafe(48)
        now = datetime.utcnow()
        session = cls(
            user_id=user_id,
            session_token=token,
            ip_address=ip_address,
            user_agent=(user_agent[:250] if user_agent else None),
            is_active=True,
            last_activity_at=now,
            expires_at=now + timedelta(days=lifetime_days)
        )
        db.session.add(session)
        return session

    def touch(self):
        self.last_activity_at = datetime.utcnow()

    def terminate(self):
        self.is_active = False

    def __repr__(self):
        return f'<UserSession user_id={self.user_id} active={self.is_active}>'


class LoginEvent(db.Model):
    __tablename__ = 'login_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    identifier = db.Column(db.String(191), nullable=False)
    event_type = db.Column(db.String(50), default='otp_login', nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success, failed, blocked
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', back_populates='login_events')

    def __repr__(self):
        return f'<LoginEvent user_id={self.user_id} status={self.status} at={self.created_at}>'


class Address(db.Model):
    __tablename__ = 'addresses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    mobile_number = db.Column(db.String(20), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    landmark = db.Column(db.String(150), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(50), default='India', nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    address_type = db.Column(db.String(20), default='home', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='addresses')
    orders = db.relationship('Order', back_populates='address')

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'mobile_number': self.mobile_number,
            'street_address': self.street_address,
            'landmark': self.landmark,
            'city': self.city,
            'state': self.state,
            'postal_code': self.postal_code,
            'country': self.country,
            'address_type': self.address_type,
            'is_default': self.is_default
        }

    def __repr__(self):
        return f'<Address id={self.id} user_id={self.user_id} city={self.city}>'
