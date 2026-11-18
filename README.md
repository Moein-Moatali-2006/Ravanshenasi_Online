# روان‌شناسی آنلاین

پروژهٔ وب‌سایت فارسی روان‌شناسی آنلاین با Flask، Jinja و SQLModel.

## راه‌اندازی

از ریشهٔ مخزن اجرا کنید:

```powershell
py -m pip install -r requirements.txt
py run.py
```

برنامه به‌صورت پیش‌فرض روی `http://127.0.0.1:5000` اجرا می‌شود. کلید
جلسه را با متغیر محیطی `SECRET_KEY` تنظیم کنید؛ اگر تنظیم نشود، کلیدی
تصادفی برای همان اجرای برنامه ساخته می‌شود و جلسه‌ها پس از راه‌اندازی
مجدد معتبر نخواهند بود.

برای فعال‌کردن حالت توسعه، متغیر محیطی `FLASK_DEBUG=1` را تنظیم کنید.

## آزمون‌ها

```powershell
py -m unittest discover -s tests
```

## ساختار پروژه

```text
app/
    __init__.py          # Application factory و ثبت Blueprintها
    routes.py            # مسیرهای صفحات وب
database/
    connection.py        # اتصال SQLite و مدیریت session
    models.py            # مدل‌های SQLModel
    database-structure.sql
templates/               # قالب‌های Jinja و اجزای مشترک
static/
    css/                 # CSS مشترک و stylesheetهای صفحه‌ای
    images/
tests/                   # آزمون‌های برنامه
config.py                # تنظیمات برنامه و OpenAPI
main.py                  # نقطهٔ ورود سازگار با WSGI
run.py                   # اجرای محلی برنامه
```

قالب پایه فقط CSS مشترک را بارگذاری می‌کند و stylesheet هر صفحه از طریق
بلوک `page_css` همان قالب اضافه می‌شود. جدول‌های پایگاه داده در زمان
ساخت برنامه با SQLModel ایجاد می‌شوند.
