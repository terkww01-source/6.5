# wsgi.py
import importlib

mod = importlib.import_module("server_dashboard")

# اول دنبال شیء اپ با نام‌های رایج می‌گردیم:
for name in ("app", "application", "flask_app"):
    if hasattr(mod, name):
        app = getattr(mod, name)
        break
else:
    # اگر کارخانهٔ ساخت اپ داری، صدا می‌زنیم:
    for factory in ("create_app", "make_app"):
        if hasattr(mod, factory):
            app = getattr(mod, factory)()
            break
    else:
        raise RuntimeError(
            "در server_dashboard نه شیء app/application هست، نه create_app/make_app. "
            "یک شیء Flask با نام app را اکسپورت کن یا یکی از این فانکشن‌ها را اضافه کن."
        )

# بعضی پلتفرم‌ها متغیر application می‌خواهند:
application = app
