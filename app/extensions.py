from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in with OTP to access this page.'
login_manager.login_message_category = 'warning'

csrf = CSRFProtect()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
