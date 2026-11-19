# روان‌شناسی آنلاین

وب‌سایت فارسی مشاورهٔ آنلاین با Flask، Jinja و SQLModel؛ شامل حساب کاربری،
رزرو جلسه، پشتیبانی، وبلاگ عمومی و پنل مدیریت.

## راه‌اندازی محلی

از ریشهٔ مخزن در PowerShell اجرا کنید:

```powershell
py -m pip install -r requirements.txt
py run.py
```

بدون تنظیم اضافه، برنامه از پایگاه دادهٔ SQLite در فایل `DBRO.db` استفاده
می‌کند و جداول/تغییرات افزایشی شناخته‌شده را هنگام راه‌اندازی اعمال می‌کند.
برای اجرای پایگاه دادهٔ دیگر، متغیر `DATABASE_URL` را پیش از شروع برنامه تنظیم
کنید.

## PostgreSQL

یک پایگاه داده و کاربر PostgreSQL بسازید، سپس نشانی اتصال را تنظیم کنید. در
صورت وجود کاراکترهای ویژه در گذرواژه، آن‌ها را در URL کدگذاری کنید:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
py run.py
```

وابستگی `psycopg` در `requirements.txt` قرار دارد. جداول جدید با SQLModel ساخته
می‌شوند و مهاجرت‌های افزایشی نسخهٔ فعلی به‌صورت idempotent در زمان راه‌اندازی
اعمال می‌شوند. فایل [`database/database-structure.sql`](database/database-structure.sql)
طرح پایهٔ PostgreSQL را برای نصب تازه مستند می‌کند؛ پیش از اجرای دستی آن روی
پایگاه دادهٔ موجود، از داده‌ها پشتیبان بگیرید و از اجرای دوبارهٔ دستورات
`CREATE TABLE` خودداری کنید.

## تنظیمات امنیتی و مدیر اولیه

در محیط عملیاتی حتماً یک `SECRET_KEY` پایدار و محرمانه تنظیم کنید. مقدار
تصادفی پیش‌فرض فقط برای توسعه است و با راه‌اندازی مجدد تغییر می‌کند. همچنین
در استقرار HTTPS، کوکی امن را فعال و نشانی عمومی ثابت سایت را برای canonical،
Open Graph و sitemap تنظیم کنید:

```powershell
$env:SECRET_KEY = "<یک مقدار تصادفی و محرمانه>"
$env:PUBLIC_BASE_URL = "https://example.com"
$env:SESSION_COOKIE_SECURE = "1"
```

پس از تنظیم `DATABASE_URL` و سایر متغیرهای پایگاه داده، مدیر اولیه را با رمز
حداقل ۱۲ نویسه‌ای بسازید. رمز از ورودی مخفی PowerShell خوانده می‌شود و به
عنوان آرگومان خط فرمان یا متن ثابت در کد ذخیره نمی‌شود:

```powershell
$adminPassword = Read-Host "رمز مدیر اولیه" -AsSecureString
$env:ADMIN_INITIAL_PASSWORD = (New-Object System.Net.NetworkCredential("", $adminPassword)).Password
py -m flask --app run create-admin --username admin --name "مدیر سایت"
Remove-Item Env:ADMIN_INITIAL_PASSWORD
Remove-Variable adminPassword
```

این فرمان رمز را با الگوریتم امن Werkzeug هش می‌کند و فقط در صورت تنظیم
`ADMIN_INITIAL_PASSWORD` اجرا می‌شود. در محیط عملیاتی، رمز منحصربه‌فرد انتخاب
کنید و متغیرهای محرمانه را از secret manager محیط استقرار تزریق کنید. پنل در
مسیر `/admin/login/` در دسترس است.

تمام فرم‌های POST با CSRF محافظت می‌شوند؛ کوکی نشست HttpOnly و SameSite=Lax
است و در صورت فعال بودن HTTPS، `SESSION_COOKIE_SECURE=1` آن را فقط به HTTPS
محدود می‌کند. دسترسی پنل به حساب فعال مدیر نیاز دارد. آمار بازدید فقط مسیر و
زمان درخواست‌های عمومی را ذخیره می‌کند و IP یا هویت بازدیدکننده ثبت نمی‌شود.

## وبلاگ و SEO

مقاله‌ها از پنل مدیریت ساخته و منتشر می‌شوند. برای هر مقاله عنوان، slug،
توضیحات متا و تصویر قابل تنظیم است. صفحات عمومی دارای canonical و Open Graph
هستند؛ مقالات دادهٔ ساختاریافتهٔ Article دارند و مسیرهای عمومی و مقاله‌های
منتشرشده در `/sitemap.xml` فهرست می‌شوند. `/robots.txt` نیز sitemap را معرفی
و مسیر مدیریت را از خزنده‌ها مستثنا می‌کند. در استقرار عملیاتی `PUBLIC_BASE_URL`
را به دامنهٔ canonical سایت تنظیم کنید.

## آزمون‌ها

```powershell
py -m unittest discover -s tests -v
```

## ساختار پروژه

```text
app/
    __init__.py          # Application factory، CSRF و آمار ناشناس
    admin.py             # ورود و عملیات پنل مدیریت
    cli.py               # ساخت مدیر اولیه
    routes.py            # صفحات عمومی، حساب کاربری، وبلاگ و sitemap
    services.py          # محتوای صفحات خدمات
database/
    connection.py        # اتصال SQLite/PostgreSQL و مهاجرت‌ها
    models.py            # مدل‌های SQLModel
    database-structure.sql
templates/               # قالب‌های Jinja، از جمله پنل و وبلاگ
static/
    css/                 # stylesheetهای صفحه‌ای
tests/                   # آزمون‌های برنامه
config.py                # تنظیمات Flask و نشست
run.py                   # نقطهٔ ورود Flask
```
