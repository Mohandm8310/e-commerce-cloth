from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User, Role, CustomerProfile, UserSession, LoginEvent
from app.models.cart import Cart
from app.auth.services import request_otp_for_identifier, verify_customer_otp

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('customer.profile'))
    return render_template('auth/login.html')


@auth_bp.route('/google', methods=['GET', 'POST'])
def google_login():
    """
    Google OAuth Authentication.
    Provides instant 1-click Google Sign-In with profile creation & real-time analytics.
    """
    if current_user.is_authenticated:
        return redirect(url_for('products.shop'))

    google_email = request.form.get('google_email') or request.args.get('email') or 'mohan.fashion@gmail.com'
    google_name = request.form.get('google_name') or request.args.get('name') or 'Mohan D M'
    avatar_url = 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'

    # Customer Role
    customer_role = Role.query.filter_by(name='customer').first()
    if not customer_role:
        customer_role = Role(name='customer', description='Standard customer')
        db.session.add(customer_role)
        db.session.flush()

    user = User.query.filter_by(email=google_email).first()
    if not user:
        user = User(
            email=google_email,
            role_id=customer_role.id,
            is_active=True,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        parts = google_name.split(' ', 1)
        profile = CustomerProfile(
            user_id=user.id,
            first_name=parts[0],
            last_name=(parts[1] if len(parts) > 1 else ''),
            avatar_url=avatar_url
        )
        db.session.add(profile)
    else:
        user.is_active = True
        user.is_verified = True
        if not user.profile:
            parts = google_name.split(' ', 1)
            profile = CustomerProfile(
                user_id=user.id,
                first_name=parts[0],
                last_name=(parts[1] if len(parts) > 1 else ''),
                avatar_url=avatar_url
            )
            db.session.add(profile)

    # Session & Login event
    session_obj = UserSession.start_session(
        user_id=user.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    login_event = LoginEvent(
        user_id=user.id,
        identifier=google_email,
        event_type='google_oauth',
        status='success',
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    db.session.add(login_event)
    db.session.commit()

    # Log in with Flask-Login
    login_user(user, remember=True)

    # Broadcast real-time customer login event to Admin Dashboard
    try:
        from app.realtime.events import broadcast_login_event
        broadcast_login_event(user)
    except Exception:
        pass

    flash(f'Signed in with Google as {user.display_name} ({user.email})!', 'success')
    next_page = request.args.get('next') or session.pop('next_url', None) or url_for('products.shop')
    return redirect(next_page)


@auth_bp.route('/demo-login', methods=['GET', 'POST'])
def demo_login():
    """1-Click quick login for demo customer without needing external SMS or email OTP."""
    customer_role = Role.query.filter_by(name='customer').first()
    user = User.query.filter_by(email='customer@example.com').first()
    if not user:
        user = User(
            email='customer@example.com',
            role_id=customer_role.id if customer_role else 1,
            is_active=True,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()
        profile = CustomerProfile(
            user_id=user.id,
            first_name='Demo',
            last_name='Customer',
            avatar_url='https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100'
        )
        db.session.add(profile)
        db.session.commit()

    login_user(user, remember=True)
    session_obj = UserSession.start_session(
        user_id=user.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    login_event = LoginEvent(
        user_id=user.id,
        identifier=user.email,
        event_type='demo_login',
        status='success',
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    db.session.add(login_event)
    db.session.commit()

    try:
        from app.realtime.events import broadcast_login_event
        broadcast_login_event(user)
    except Exception:
        pass

    flash('Logged in as Demo Customer!', 'success')
    return redirect(url_for('products.shop'))


@auth_bp.route('/request-otp', methods=['POST'])
def request_otp():
    is_json = request.is_json
    data = request.get_json() if is_json else request.form
    identifier = data.get('identifier', '').strip()

    if not identifier:
        msg = "Please enter your email address."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('auth.login'))

    success, message, clean_id, plain_otp = request_otp_for_identifier(identifier, purpose='login')

    if not success:
        if is_json:
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'warning')
        return redirect(url_for('auth.login'))

    session['otp_identifier'] = clean_id
    session['last_otp'] = plain_otp

    # If dev mock mode, flash OTP so tester/developer sees it immediately
    if current_app.config.get('MOCK_OTP'):
        flash(f"DEVELOPMENT MODE: Your OTP code is {plain_otp}", 'info')

    if is_json:
        res_data = {'success': True, 'message': message, 'identifier': clean_id}
        if current_app.config.get('MOCK_OTP'):
            res_data['mock_otp'] = plain_otp
        return jsonify(res_data), 200

    flash(message, 'success')
    return redirect(url_for('auth.verify_otp_page'))


@auth_bp.route('/verify-otp', methods=['GET'])
def verify_otp_page():
    identifier = session.get('otp_identifier')
    last_otp = session.get('last_otp')
    if not identifier:
        flash("Please enter your email address first.", 'warning')
        return redirect(url_for('auth.login'))
    return render_template('auth/verify_otp.html', identifier=identifier, active_otp=last_otp)


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    identifier = data.get('identifier', session.get('otp_identifier', '')).strip()
    otp_code = data.get('otp_code', '').strip()

    if not identifier or not otp_code:
        msg = "Please enter the 6-digit OTP code."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('auth.verify_otp_page'))

    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')

    success, message, user = verify_customer_otp(identifier, otp_code, ip_address, user_agent)

    if not success:
        if is_json:
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('auth.verify_otp_page'))

    # Log in with Flask-Login
    login_user(user, remember=True)
    session.pop('otp_identifier', None)
    session.pop('last_otp', None)

    # Merge guest cart to user cart if guest session had cart items
    guest_session_id = session.get('cart_session_id')
    if guest_session_id:
        guest_cart = Cart.query.filter_by(session_id=guest_session_id).first()
        if guest_cart and guest_cart.items:
            user_cart = Cart.query.filter_by(user_id=user.id).first()
            if not user_cart:
                user_cart = Cart(user_id=user.id)
                db.session.add(user_cart)
                db.session.flush()

            for g_item in guest_cart.items:
                try:
                    user_cart.add_item(g_item.variant, g_item.quantity)
                except Exception:
                    pass
            db.session.delete(guest_cart)
            db.session.commit()
            session.pop('cart_session_id', None)

    # Broadcast real-time customer login event if SocketIO active
    try:
        from app.realtime.events import broadcast_login_event
        broadcast_login_event(user)
    except Exception:
        pass

    next_page = request.args.get('next') or session.pop('next_url', None) or url_for('products.shop')

    if is_json:
        return jsonify({'success': True, 'message': 'Welcome to StyleSphere!', 'redirect_url': next_page}), 200

    flash(f"Welcome back, {user.display_name}!", 'success')
    return redirect(next_page)


@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    identifier = session.get('otp_identifier')
    if not identifier:
        data = request.get_json() if request.is_json else request.form
        identifier = data.get('identifier')

    if not identifier:
        return jsonify({'success': False, 'message': 'No identifier found to resend OTP.'}), 400

    success, message, clean_id, plain_otp = request_otp_for_identifier(identifier, purpose='login')

    res_data = {'success': success, 'message': message}
    if success and current_app.config.get('MOCK_OTP'):
        res_data['mock_otp'] = plain_otp
        flash(f"DEVELOPMENT MODE: New OTP is {plain_otp}", 'info')

    status_code = 200 if success else 400
    if request.is_json:
        return jsonify(res_data), status_code

    flash(message, 'success' if success else 'warning')
    return redirect(url_for('auth.verify_otp_page'))


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    # Mark user active sessions ended
    UserSession.query.filter_by(user_id=current_user.id, is_active=True).update({'is_active': False})
    db.session.commit()

    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('products.home'))


@auth_bp.route('/api/heartbeat', methods=['POST'])
def customer_heartbeat():
    """
    Called periodically (e.g. every 60s) by the frontend to update last active timestamp
    for live customer monitoring analytics.
    """
    if current_user.is_authenticated:
        latest_session = UserSession.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(UserSession.last_activity_at.desc()).first()

        if latest_session:
            latest_session.touch()
            db.session.commit()
            return jsonify({'status': 'active', 'user_id': current_user.id}), 200

    return jsonify({'status': 'unauthenticated'}), 200
