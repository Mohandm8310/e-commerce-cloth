import os
from app import create_app
from app.extensions import socketio, db

app = create_app()

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')
    print(f"\n========================================================")
    print(f" StyleSphere — Fashion E-Commerce Platform")
    print(f" Server running at: http://127.0.0.1:{port}")
    print(f" Admin Portal at:   http://127.0.0.1:{port}/admin/login")
    print(f"========================================================\n")
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=True)
