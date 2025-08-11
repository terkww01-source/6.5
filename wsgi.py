# wsgi.py (FINAL)
import importlib

mod = importlib.import_module("server_dashboard")

flask_app = None
socketio = getattr(mod, "socketio", None)

# 1) تلاش برای یافتن شیء اپ با نام‌های رایج
for name in ("app", "application", "flask_app"):
    if hasattr(mod, name):
        flask_app = getattr(mod, name)
        break

# 2) اگر نبود، کارخانه‌های متداول را صدا بزن
if flask_app is None:
    for factory in ("create_app", "make_app"):
        if hasattr(mod, factory):
            flask_app = getattr(mod, factory)()
            break

# 3) اگر هنوز نیافتی و socketio موجود است، از اپ داخلی‌اش بردار
if flask_app is None and socketio is not None and hasattr(socketio, "app"):
    flask_app = socketio.app

# 4) اگر باز هم نبود، خطای شفاف
if flask_app is None:
    raise RuntimeError(
        "در server_dashboard نه app/application تعریف شده، نه create_app/make_app. "
        "یکی از این‌ها را اضافه کن یا نام فعلی را به app تغییر بده."
    )

# WSGI callable نهایی برای Gunicorn:
app = socketio.wsgi_app if (socketio is not None and hasattr(socketio, "wsgi_app")) else flask_app.wsgi_app
application = app  # برای سازگاری
