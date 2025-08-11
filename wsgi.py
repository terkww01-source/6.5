# wsgi.py (FINAL, handles tuple/app/factory)
import importlib

mod = importlib.import_module("server_dashboard")

flask_app = None
socketio = getattr(mod, "socketio", None)

# 1) اگر app/application/flask_app موجود است، بردار
for name in ("app", "application", "flask_app"):
    if hasattr(mod, name):
        flask_app = getattr(mod, name)
        break

# 2) اگر شیء یافت‌شده تاپل بود، اجزایش را تشخیص بده
if isinstance(flask_app, tuple):
    tmp_flask, tmp_sock = None, None
    for item in flask_app:
        if hasattr(item, "wsgi_app"):         # Flask app
            tmp_flask = item
        elif hasattr(item, "emit") and hasattr(item, "on"):
            tmp_sock = item                    # Socket.IO
    flask_app = tmp_flask or flask_app        # اگر نشناخت، همون تاپل می‌مونه
    socketio = socketio or tmp_sock

# 3) اگر هنوز Flask app پیدا نشد، دنبال کارخانه‌ها بگرد
if flask_app is None:
    for factory in ("create_app", "make_app"):
        if hasattr(mod, factory):
            out = getattr(mod, factory)()
            if isinstance(out, tuple):
                tmp_flask, tmp_sock = None, None
                for item in out:
                    if hasattr(item, "wsgi_app"):
                        tmp_flask = item
                    elif hasattr(item, "emit") and hasattr(item, "on"):
                        tmp_sock = item
                flask_app = tmp_flask
                socketio = socketio or tmp_sock
            else:
                flask_app = out
            break

# 4) تضمین کنیم Flask app واقعاً داریم
if flask_app is None or not hasattr(flask_app, "wsgi_app"):
    raise RuntimeError(
        "در server_dashboard باید یک Flask app بدهی (app/application) یا کارخانه create_app/make_app. "
        "اگر تاپل برمی‌گردانی، یکی از اعضا باید Flask app و دیگری SocketIO باشد."
    )

# 5) WSGI callable برای Gunicorn
app = socketio.wsgi_app if (socketio is not None and hasattr(socketio, "wsgi_app")) else flask_app.wsgi_app
application = app
