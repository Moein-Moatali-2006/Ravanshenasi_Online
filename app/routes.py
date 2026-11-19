import re
from datetime import date
from xml.etree import ElementTree

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from werkzeug.security import check_password_hash, generate_password_hash

from database.connection import engine
from database.models import Article, Client, Employee, Meet, Payment, SetTime, Ticket
from app.services import SERVICE_PAGES


pages = Blueprint("pages", __name__)


@pages.get("/")
def home():
    return render_template("home.html")


@pages.get("/about/")
def about():
    return render_template("about.html")


@pages.route("/support/", methods=["GET", "POST"])
def support():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        subject = request.form.get("subject", "")
        message = request.form.get("message", "").strip()
        subject_labels = {
            "service": "پرسش درباره خدمات",
            "appointment": "ثبت یا پیگیری درخواست مشاوره",
            "technical": "مشکل فنی سایت",
            "feedback": "پیشنهاد یا انتقاد",
            "other": "سایر موارد",
        }
        if not name or len(name) > 100:
            flash("نام خود را به‌درستی وارد کنید.", "error")
        elif not contact or len(contact) > 255:
            flash("ایمیل یا شمارهٔ تماس را به‌درستی وارد کنید.", "error")
        elif subject not in subject_labels:
            flash("موضوع پیام را انتخاب کنید.", "error")
        elif not message or len(message) > 10000:
            flash("متن پیام را وارد کنید (حداکثر ۱۰۰۰۰ نویسه).", "error")
        else:
            with Session(engine) as db_session:
                db_session.add(
                    Ticket(
                        sender_name=name,
                        sender_callback=contact,
                        title=subject_labels[subject],
                        client_text=message,
                    )
                )
                db_session.commit()
            flash("درخواست شما ثبت شد؛ پشتیبانی آن را پیگیری می‌کند.", "success")
            return redirect(url_for("pages.support") + "#support-form")
    return render_template("support.html")


@pages.get("/blog/")
def blog_index():
    with Session(engine) as db_session:
        articles = db_session.exec(
            select(Article)
            .where(Article.is_published.is_(True), Article.slug.is_not(None))
            .order_by(Article.created_at.desc(), Article.article_id.desc())
            .limit(50)
        ).all()
    return render_template("blog.html", articles=articles)


@pages.get("/blog/<slug>/")
def blog_article(slug: str):
    with Session(engine) as db_session:
        article = db_session.exec(
            select(Article).where(
                Article.slug == slug,
                Article.is_published.is_(True),
            )
        ).first()
    if article is None:
        abort(404)
    return render_template("blog_article.html", article=article)


@pages.get("/sitemap.xml")
def sitemap():
    with Session(engine) as db_session:
        articles = db_session.exec(
            select(Article.slug, Article.updated_at, Article.created_at).where(
                Article.is_published.is_(True),
                Article.slug.is_not(None),
            )
        ).all()
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ElementTree.register_namespace("", namespace)
    root = ElementTree.Element(f"{{{namespace}}}urlset")
    base_url = current_app.config["PUBLIC_BASE_URL"] or request.url_root.rstrip("/")
    public_paths = [
        "/",
        "/about/",
        "/support/",
        "/services/",
        "/blog/",
        *(f"/services/{slug}/" for slug in SERVICE_PAGES),
    ]
    for path in public_paths:
        ElementTree.SubElement(
            ElementTree.SubElement(root, f"{{{namespace}}}url"),
            f"{{{namespace}}}loc",
        ).text = f"{base_url}{path}"
    for slug, updated_at, created_at in articles:
        url_node = ElementTree.SubElement(root, f"{{{namespace}}}url")
        ElementTree.SubElement(url_node, f"{{{namespace}}}loc").text = (
            f"{base_url}{url_for('pages.blog_article', slug=slug)}"
        )
        last_modified = updated_at or created_at
        if last_modified is not None:
            ElementTree.SubElement(
                url_node, f"{{{namespace}}}lastmod"
            ).text = last_modified.date().isoformat()

    return Response(
        ElementTree.tostring(root, encoding="utf-8", xml_declaration=True),
        mimetype="application/xml",
    )


@pages.get("/robots.txt")
def robots_txt():
    base_url = current_app.config["PUBLIC_BASE_URL"] or request.url_root.rstrip("/")
    return Response(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /profile/\n"
        f"Sitemap: {base_url}{url_for('pages.sitemap')}\n",
        mimetype="text/plain",
    )


@pages.get("/services/")
def services_index():
    return render_template("services.html", services=SERVICE_PAGES)


@pages.get("/services/<service_slug>/")
def service_detail(service_slug: str):
    service = SERVICE_PAGES.get(service_slug)
    if service is None:
        abort(404)

    return render_template(
        "service_detail.html",
        service=service,
        service_slug=service_slug,
        service_slugs=SERVICE_PAGES,
    )


@pages.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or len(full_name) > 100:
            flash("نام و نام خانوادگی را به‌درستی وارد کنید.", "error")
        elif not re.fullmatch(r"09[0-9]{9}", phone):
            flash("شماره تلفن باید ۱۱ رقم و با ۰۹ شروع شود.", "error")
        elif len(password) < 8:
            flash("رمز عبور باید حداقل ۸ کاراکتر باشد.", "error")
        elif password != confirm_password:
            flash("رمز عبور و تکرار آن یکسان نیستند.", "error")
        else:
            with Session(engine) as db_session:
                existing_client = db_session.exec(
                    select(Client).where(Client.client_phone == phone)
                ).first()
                if existing_client:
                    flash("این شماره تلفن قبلاً ثبت‌نام کرده است.", "error")
                else:
                    client = Client(
                        client_name=full_name,
                        client_phone=phone,
                        password_hash=generate_password_hash(password),
                    )
                    db_session.add(client)
                    try:
                        db_session.commit()
                    except IntegrityError as error:
                        db_session.rollback()
                        if "client_phone" not in str(error.orig):
                            raise
                        flash("این شماره تلفن قبلاً ثبت‌نام کرده است.", "error")
                    else:
                        flash("ثبت‌نام با موفقیت انجام شد؛ حالا وارد شوید.", "success")
                        return redirect(url_for("pages.login"))

    return render_template("register.html")


@pages.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("login_method") != "password":
            flash("ورود پیامکی هنوز فعال نشده است.", "warning")
            return redirect(url_for("pages.login"))

        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        with Session(engine) as db_session:
            client = db_session.exec(
                select(Client).where(Client.client_phone == phone)
            ).first()

        if (
            client is None
            or not client.is_active
            or client.password_hash is None
            or not check_password_hash(client.password_hash, password)
        ):
            flash("شماره تلفن یا رمز عبور نادرست است.", "error")
            return redirect(url_for("pages.login"))

        session.clear()
        session["client_id"] = client.client_id
        session["client_name"] = client.client_name
        session.permanent = request.form.get("remember_me") == "on"
        return redirect(url_for("pages.home"))

    return render_template("login.html")


@pages.route("/profile/", methods=["GET", "POST"])
def profile():
    client_id = session.get("client_id")
    if client_id is None:
        flash("برای مشاهده پروفایل ابتدا وارد حساب کاربری شوید.", "info")
        return redirect(url_for("pages.login"))

    if request.method == "POST":
        action = request.form.get("action")
        with Session(engine) as db_session:
            client = db_session.get(Client, client_id)
            if client is None or not client.is_active:
                session.clear()
                flash("حساب کاربری فعال نیست؛ لطفاً با پشتیبانی تماس بگیرید.", "error")
                return redirect(url_for("pages.login"))

            if action == "update_profile":
                full_name = request.form.get("full_name", "").strip()
                phone = request.form.get("phone", "").strip()
                if not full_name or len(full_name) > 100:
                    flash("نام و نام خانوادگی را به‌درستی وارد کنید.", "error")
                elif not re.fullmatch(r"09[0-9]{9}", phone):
                    flash("شماره تلفن باید ۱۱ رقم و با ۰۹ شروع شود.", "error")
                else:
                    client.client_name = full_name
                    client.client_phone = phone
                    try:
                        db_session.commit()
                    except IntegrityError as error:
                        db_session.rollback()
                        if "client_phone" not in str(error.orig):
                            raise
                        flash("این شماره تلفن قبلاً برای حساب دیگری ثبت شده است.", "error")
                    else:
                        session["client_name"] = full_name
                        flash("اطلاعات حساب با موفقیت به‌روز شد.", "success")
                        return redirect(url_for("pages.profile") + "#personal-info")
            elif action == "change_password":
                current_password = request.form.get("current_password", "")
                new_password = request.form.get("new_password", "")
                confirm_password = request.form.get("confirm_password", "")
                if client.password_hash is None or not check_password_hash(
                    client.password_hash, current_password
                ):
                    flash("رمز عبور فعلی درست نیست.", "error")
                elif len(new_password) < 8:
                    flash("رمز عبور جدید باید حداقل ۸ کاراکتر باشد.", "error")
                elif new_password != confirm_password:
                    flash("رمز عبور جدید و تکرار آن یکسان نیستند.", "error")
                else:
                    client.password_hash = generate_password_hash(new_password)
                    db_session.add(client)
                    db_session.commit()
                    flash("رمز عبور با موفقیت تغییر کرد.", "success")
                    return redirect(url_for("pages.profile") + "#account-security")
            else:
                flash("عملیات درخواستی معتبر نیست.", "error")

        return redirect(url_for("pages.profile"))

    with Session(engine) as db_session:
        client = db_session.get(Client, client_id)
        if client is None or not client.is_active:
            session.clear()
            flash("حساب کاربری فعال نیست؛ لطفاً با پشتیبانی تماس بگیرید.", "error")
            return redirect(url_for("pages.login"))

        payments = db_session.exec(
            select(Payment)
            .where(Payment.client_id == client_id)
            .order_by(Payment.pay_id.desc())
        ).all()
        upcoming_rows = db_session.exec(
            select(Meet, SetTime, Employee)
            .join(Payment, Meet.payment_id == Payment.pay_id)
            .join(SetTime, Meet.set_time_id == SetTime.set_time_id)
            .join(Employee, SetTime.employee_id == Employee.employee_id)
            .where(
                Payment.client_id == client_id,
                Meet.meet_done == 0,
                SetTime.appointment_date >= date.today(),
            )
            .order_by(SetTime.appointment_date, SetTime.start_time)
        ).all()
        completed_session_count = len(
            db_session.exec(
                select(Meet.meet_id)
                .join(Payment, Meet.payment_id == Payment.pay_id)
                .where(Payment.client_id == client_id, Meet.meet_done == 1)
            ).all()
        )

        payment_history = [
            {
                "count": payment.count_meet,
                "amount": payment.total_price,
                "status": payment.payment_status,
                "tracking_code": payment.transfer_tracking_code,
            }
            for payment in payments
        ]
        upcoming_appointments = [
            {
                "date": appointment.appointment_date,
                "time": appointment.start_time,
                "employee_name": employee.employee_name,
            }
            for _, appointment, employee in upcoming_rows
        ]
        client_name = client.client_name
        client_phone = client.client_phone

    return render_template(
        "profile.html",
        client_name=client_name,
        client_phone=client_phone,
        payment_history=payment_history,
        upcoming_appointments=upcoming_appointments,
        completed_session_count=completed_session_count,
    )


@pages.post("/logout/")
def logout():
    session.clear()
    flash("با موفقیت از حساب خارج شدید.", "success")
    return redirect(url_for("pages.home"))
