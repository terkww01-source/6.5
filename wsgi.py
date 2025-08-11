# wsgi.py  (نسخه نهایی)
from server_dashboard import app as flask_app  # Flask instance

try:
    from server_dashboard import socketio  # Flask-SocketIO instance
except Exception:
    socketio = None

# WSGI callable برای Gunicorn (اولویت با Socket.IO)
app = socketio.wsgi_app if socketio is not None else flask_app.wsgi_app

# برخی پلتفرم‌ها متغیر application را هم می‌خوانند
application = app
