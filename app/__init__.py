import os
from flask import Flask, send_from_directory, render_template
from config import Config
from app.extensions import db, login_manager, csrf, socketio
from app.models.user import User, Role
from app.models.product import Category
from app.models.cart import Cart


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure uploads directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Serve uploaded product files
    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # Context processors for global template access
    @app.context_processor
    def inject_global_data():
        nav_categories = []
        try:
            nav_categories = Category.query.filter_by(is_active=True).all()
        except Exception:
            pass

        return {
            'nav_categories': nav_categories,
            'app_name': 'StyleSphere'
        }

    # Template filters
    @app.template_filter('currency')
    def currency_filter(amount):
        try:
            val = float(amount or 0)
            return f"₹{val:,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"

    @app.template_filter('date_format')
    def date_format_filter(dt, fmt='%b %d, %Y'):
        if not dt:
            return ''
        return dt.strftime(fmt)

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.products.routes import products_bp
    from app.cart.routes import cart_bp
    from app.checkout.routes import checkout_bp
    from app.customer.routes import customer_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(customer_bp)

    # Import real-time events
    from app.realtime import events as realtime_events

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('pages/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('pages/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('pages/500.html'), 500

    # CLI command: create-admin
    @app.cli.command("create-admin")
    def create_admin():
        """Creates a new administrator account securely."""
        import click
        from werkzeug.security import generate_password_hash
        from app.models.user import Role, User

        email = click.prompt("Admin Email", type=str)
        password = click.prompt("Admin Password", type=str, hide_input=True, confirmation_prompt=True)

        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrator with full privileges')
            db.session.add(admin_role)
            db.session.commit()

        existing = User.query.filter_by(email=email).first()
        if existing:
            existing.role_id = admin_role.id
            existing.set_password(password)
            existing.is_active = True
            db.session.commit()
            click.echo(f"Admin account updated for: {email}")
        else:
            admin = User(
                email=email,
                role_id=admin_role.id,
                is_active=True,
                is_verified=True
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            click.echo(f"Admin account created successfully for: {email}")

    # CLI command: seed-db
    @app.cli.command("seed-db")
    def seed_db():
        """Populates database with initial categories, products, coupons and demo accounts."""
        import click
        from scripts.seed_data import run_seed
        run_seed()
        click.echo("Database seeding completed.")

    return app
