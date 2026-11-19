import re
import secrets
from datetime import date, datetime, time, timedelta
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlmodel import Session, select
from werkzeug.security import check_password_hash

from database.connection import engine
from database.models import (
    Admin,
    Article,
    Client,
    Employee,
    Meet,
    PageView,
    Payment,
    ServiceField,
    SetTime,
    Ticket,
)


admin = Blueprint("admin", __name__, url_prefix="/admin")
_dummy_password_hash = None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        admin_id = session.get("admin_id")
        if admin_id is None:
            flash("برای ورود به پنل، ابتدا وارد حساب ادمین شوید.", "info")
            return redirect(url_for("admin.login"))

        with Session(engine) as db_session:
            current_admin = db_session.get(Admin, admin_id)

        if current_admin is None or not current_admin.is_active:
            session.pop("admin_id", None)
            flash("حساب ادمین غیرفعال است؛ لطفاً با مدیر سیستم تماس بگیرید.", "error")
            return redirect(url_for("admin.login"))

        g.current_admin = current_admin
        return view(*args, **kwargs)

    return wrapped


def _count(db_session, statement) -> int:
    return int(db_session.exec(statement).one())


def _page_number(value: str | None) -> int:
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


def _phone_is_valid(phone: str) -> bool:
    return re.fullmatch(r"09[0-9]{9}", phone) is not None


def _selected_fields(db_session: Session, field_ids: list[str]):
    if any(not field_id.isdigit() for field_id in field_ids):
        return None
    requested_ids = {int(field_id) for field_id in field_ids}
    if not requested_ids:
        return []
    fields = db_session.exec(
        select(ServiceField).where(ServiceField.field_id.in_(requested_ids))
    ).all()
    if len(fields) != len(requested_ids):
        return None
    return fields


def _is_slot_conflict(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return (
        "idx_meets_active_slot" in message
        or "meets.set_time_id" in message
    )


def _is_availability_conflict(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return (
        "uq_employee_date_time" in message
        or (
            "set_times.employee_id" in message
            and "set_times.appointment_date" in message
            and "set_times.start_time" in message
        )
    )


def _article_form_data(form):
    title = form.get("title", "").strip()
    slug = re.sub(r"\s+", "-", form.get("slug", "").strip().lower())
    topic = form.get("topic", "").strip()
    image_path = form.get("image_path", "").strip().replace("\\", "/")
    content = form.get("content", "").strip()
    meta_description = form.get("meta_description", "").strip()
    author_name = form.get("author_name", "").strip()

    if not title or len(title) > 200:
        return None, "عنوان مقاله را به‌درستی وارد کنید."
    if not slug or len(slug) > 220 or re.fullmatch(r"[\w-]+", slug) is None:
        return None, "نشانی مقاله فقط می‌تواند شامل حروف، عدد و خط تیره باشد."
    if not topic or len(topic) > 100:
        return None, "موضوع مقاله را به‌درستی وارد کنید."
    if (
        not image_path.startswith("images/")
        or ".." in image_path
        or len(image_path) > 500
    ):
        return None, "مسیر تصویر باید به پوشهٔ images/ در فایل‌های سایت اشاره کند."
    if not content:
        return None, "متن مقاله را وارد کنید."
    if not author_name or len(author_name) > 150:
        return None, "نام نویسنده را به‌درستی وارد کنید."

    if not meta_description:
        meta_description = re.sub(r"\s+", " ", content)[:290].strip()
    if len(meta_description) > 300:
        return None, "توضیحات SEO حداکثر ۳۰۰ نویسه باشد."

    return {
        "title": title,
        "slug": slug,
        "topic": topic,
        "image_path": image_path,
        "content": content,
        "meta_description": meta_description,
        "author_name": author_name,
        "is_published": form.get("is_published") == "on",
    }, None


@admin.get("/login/")
def login():
    if session.get("admin_id") is not None:
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html")


@admin.post("/login/")
def login_submit():
    global _dummy_password_hash

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    with Session(engine) as db_session:
        current_admin = db_session.exec(
            select(Admin).where(Admin.admin_username == username)
        ).first()

    if _dummy_password_hash is None:
        from werkzeug.security import generate_password_hash

        _dummy_password_hash = generate_password_hash(secrets.token_urlsafe(32))

    password_matches = check_password_hash(
        current_admin.password_hash if current_admin else _dummy_password_hash,
        password,
    )
    if current_admin is None or not current_admin.is_active or not password_matches:
        flash("نام کاربری یا رمز عبور ادمین نادرست است.", "error")
        return redirect(url_for("admin.login"))

    session.clear()
    session["admin_id"] = current_admin.admin_id
    session["csrf_token"] = secrets.token_urlsafe(32)
    return redirect(url_for("admin.dashboard"))


@admin.post("/logout/")
@admin_required
def logout():
    session.clear()
    flash("از پنل مدیریت خارج شدید.", "success")
    return redirect(url_for("admin.login"))


@admin.get("/")
@admin_required
def dashboard():
    today = date.today()
    start_of_day = datetime.combine(today, time.min)
    start_of_week = datetime.combine(
        today - timedelta(days=today.weekday()), time.min
    )
    start_of_month = datetime.combine(today.replace(day=1), time.min)
    next_day = start_of_day + timedelta(days=1)
    next_week = start_of_week + timedelta(days=7)
    next_month = (
        datetime.combine(
            (today.replace(day=28) + timedelta(days=4)).replace(day=1), time.min
        )
    )

    with Session(engine) as db_session:
        totals = {
            "clients": _count(db_session, select(func.count(Client.client_id))),
            "active_clients": _count(
                db_session,
                select(func.count(Client.client_id)).where(Client.is_active.is_(True)),
            ),
            "employees": _count(
                db_session,
                select(func.count(Employee.employee_id)).where(
                    Employee.is_active.is_(True)
                ),
            ),
            "appointments": _count(db_session, select(func.count(Meet.meet_id))),
            "payments_pending": _count(
                db_session,
                select(func.count(Payment.pay_id)).where(
                    Payment.payment_status == 0
                ),
            ),
            "articles_published": _count(
                db_session,
                select(func.count(Article.article_id)).where(
                    Article.is_published.is_(True)
                ),
            ),
            "tickets_open": _count(
                db_session,
                select(func.count(Ticket.ticket_id)).where(Ticket.ticket_status == 0),
            ),
        }

        visits = {
            "today": _count(
                db_session,
                select(func.count(PageView.page_view_id)).where(
                    PageView.viewed_at >= start_of_day,
                    PageView.viewed_at < next_day,
                ),
            ),
            "week": _count(
                db_session,
                select(func.count(PageView.page_view_id)).where(
                    PageView.viewed_at >= start_of_week,
                    PageView.viewed_at < next_week,
                ),
            ),
            "month": _count(
                db_session,
                select(func.count(PageView.page_view_id)).where(
                    PageView.viewed_at >= start_of_month,
                    PageView.viewed_at < next_month,
                ),
            ),
        }
        registrations = {
            "today": _count(
                db_session,
                select(func.count(Client.client_id)).where(
                    Client.created_at >= start_of_day,
                    Client.created_at < next_day,
                ),
            ),
            "week": _count(
                db_session,
                select(func.count(Client.client_id)).where(
                    Client.created_at >= start_of_week,
                    Client.created_at < next_week,
                ),
            ),
            "month": _count(
                db_session,
                select(func.count(Client.client_id)).where(
                    Client.created_at >= start_of_month,
                    Client.created_at < next_month,
                ),
            ),
        }

        meetings = {}
        for period, start, end in (
            ("today", today, today + timedelta(days=1)),
            ("week", start_of_week.date(), next_week.date()),
            ("month", today.replace(day=1), next_month.date()),
        ):
            meetings[period] = _count(
                db_session,
                select(func.count(Meet.meet_id))
                .join(Payment, Meet.payment_id == Payment.pay_id)
                .join(SetTime, Meet.set_time_id == SetTime.set_time_id)
                .where(
                    Meet.meet_done == 1,
                    SetTime.appointment_date >= start,
                    SetTime.appointment_date < end,
                ),
            )

        top_pages = db_session.exec(
            select(PageView.path, func.count(PageView.page_view_id))
            .where(PageView.viewed_at >= start_of_month)
            .group_by(PageView.path)
            .order_by(func.count(PageView.page_view_id).desc())
            .limit(10)
        ).all()
        recent_clients = db_session.exec(
            select(Client).order_by(Client.client_id.desc()).limit(6)
        ).all()
        recent_appointments = db_session.exec(
            select(Meet, SetTime, Employee, Client)
            .join(Payment, Meet.payment_id == Payment.pay_id)
            .join(Client, Payment.client_id == Client.client_id)
            .join(SetTime, Meet.set_time_id == SetTime.set_time_id)
            .join(Employee, SetTime.employee_id == Employee.employee_id)
            .order_by(SetTime.appointment_date.desc(), SetTime.start_time.desc())
            .limit(6)
        ).all()

    return render_template(
        "admin/dashboard.html",
        totals=totals,
        visits=visits,
        registrations=registrations,
        meetings=meetings,
        top_pages=top_pages,
        recent_clients=recent_clients,
        recent_appointments=recent_appointments,
        today=today,
    )


@admin.get("/clients/")
@admin_required
def clients():
    page_number = _page_number(request.args.get("page"))
    search = request.args.get("q", "").strip()
    statement = select(Client)
    count_statement = select(func.count(Client.client_id))
    if search:
        condition = Client.client_name.ilike(f"%{search}%") | Client.client_phone.ilike(
            f"%{search}%"
        )
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)

    with Session(engine) as db_session:
        client_rows = db_session.exec(
            statement.order_by(Client.client_id.desc())
            .offset((page_number - 1) * 50)
            .limit(50)
        ).all()
        total = _count(db_session, count_statement)

    return render_template(
        "admin/clients.html",
        clients=client_rows,
        search=search,
        page=page_number,
        total_pages=max(1, (total + 49) // 50),
        total=total,
    )


@admin.get("/clients/<int:client_id>/")
@admin_required
def client_detail(client_id: int):
    with Session(engine) as db_session:
        client = db_session.get(Client, client_id)
        if client is None:
            abort(404)
        payments = db_session.exec(
            select(Payment)
            .where(Payment.client_id == client_id)
            .order_by(Payment.pay_id.desc())
        ).all()
        appointments = db_session.exec(
            select(Meet, SetTime, Employee, Payment)
            .join(Payment, Meet.payment_id == Payment.pay_id)
            .join(SetTime, Meet.set_time_id == SetTime.set_time_id)
            .join(Employee, SetTime.employee_id == Employee.employee_id)
            .where(Payment.client_id == client_id)
            .order_by(SetTime.appointment_date.desc(), SetTime.start_time.desc())
        ).all()

    return render_template(
        "admin/client_detail.html",
        client=client,
        payments=payments,
        appointments=appointments,
    )


@admin.post("/clients/<int:client_id>/edit/")
@admin_required
def client_edit(client_id: int):
    name = request.form.get("client_name", "").strip()
    phone = request.form.get("client_phone", "").strip()
    new_password = request.form.get("new_password", "")
    with Session(engine) as db_session:
        client = db_session.get(Client, client_id)
        if client is None:
            abort(404)
        if not name or len(name) > 100:
            flash("نام کاربر را به‌درستی وارد کنید.", "error")
        elif not _phone_is_valid(phone):
            flash("شماره تلفن باید ۱۱ رقم و با ۰۹ شروع شود.", "error")
        elif new_password and len(new_password) < 8:
            flash("رمز جدید باید حداقل ۸ کاراکتر باشد.", "error")
        else:
            client.client_name = name
            client.client_phone = phone
            client.is_active = request.form.get("is_active") == "on"
            if new_password:
                from werkzeug.security import generate_password_hash

                client.password_hash = generate_password_hash(new_password)
            try:
                db_session.commit()
            except IntegrityError as error:
                db_session.rollback()
                if "client_phone" not in str(error.orig):
                    raise
                flash("این شماره تلفن متعلق به کاربر دیگری است.", "error")
            else:
                flash("مشخصات کاربر ذخیره شد.", "success")
                return redirect(url_for("admin.client_detail", client_id=client_id))

    return redirect(url_for("admin.client_detail", client_id=client_id))


@admin.get("/employees/")
@admin_required
def employees():
    with Session(engine) as db_session:
        employee_rows = db_session.exec(
            select(Employee).order_by(Employee.is_active.desc(), Employee.employee_name)
        ).all()
        service_fields = db_session.exec(
            select(ServiceField).order_by(ServiceField.field_name)
        ).all()
        employee_fields = {
            employee.employee_id: [field.field_name for field in employee.fields]
            for employee in employee_rows
        }

    return render_template(
        "admin/employees.html",
        employees=employee_rows,
        service_fields=service_fields,
        employee_fields=employee_fields,
    )


@admin.post("/employees/")
@admin_required
def employee_create():
    name = request.form.get("employee_name", "").strip()
    phone = request.form.get("employee_phone", "").strip()
    email = request.form.get("employee_email", "").strip()
    field_ids = request.form.getlist("field_ids")
    if (
        not name
        or len(name) > 100
        or not _phone_is_valid(phone)
        or not email
        or len(email) > 56
        or "@" not in email
    ):
        flash("نام، شماره و ایمیل متخصص را به‌درستی وارد کنید.", "error")
        return redirect(url_for("admin.employees"))

    with Session(engine) as db_session:
        fields = _selected_fields(db_session, field_ids)
        if fields is None:
            flash("حوزهٔ تخصصی انتخاب‌شده معتبر نیست.", "error")
            return redirect(url_for("admin.employees"))
        employee = Employee(
            employee_name=name,
            employee_phone=phone,
            employee_email=email,
            is_active=True,
        )
        db_session.add(employee)
        try:
            db_session.flush()
            employee.fields = fields
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if "employee_phone" not in str(error.orig):
                raise
            flash("این شماره تلفن برای متخصص دیگری ثبت شده است.", "error")
            return redirect(url_for("admin.employees"))

    flash("متخصص جدید اضافه شد.", "success")
    return redirect(url_for("admin.employees"))


@admin.post("/employees/<int:employee_id>/edit/")
@admin_required
def employee_edit(employee_id: int):
    name = request.form.get("employee_name", "").strip()
    phone = request.form.get("employee_phone", "").strip()
    email = request.form.get("employee_email", "").strip()
    field_ids = request.form.getlist("field_ids")
    if (
        not name
        or len(name) > 100
        or not _phone_is_valid(phone)
        or not email
        or len(email) > 56
        or "@" not in email
    ):
        flash("مشخصات متخصص را به‌درستی وارد کنید.", "error")
        return redirect(url_for("admin.employees"))

    with Session(engine) as db_session:
        employee = db_session.get(Employee, employee_id)
        if employee is None:
            abort(404)
        employee.employee_name = name
        employee.employee_phone = phone
        employee.employee_email = email
        fields = _selected_fields(db_session, field_ids)
        if fields is None:
            flash("حوزهٔ تخصصی انتخاب‌شده معتبر نیست.", "error")
            return redirect(url_for("admin.employees"))
        employee.fields = fields
        try:
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if "employee_phone" not in str(error.orig):
                raise
            flash("این شماره تلفن برای متخصص دیگری ثبت شده است.", "error")
            return redirect(url_for("admin.employees"))

    flash("مشخصات متخصص به‌روز شد.", "success")
    return redirect(url_for("admin.employees"))


@admin.post("/employees/<int:employee_id>/toggle/")
@admin_required
def employee_toggle(employee_id: int):
    with Session(engine) as db_session:
        employee = db_session.get(Employee, employee_id)
        if employee is None:
            abort(404)
        employee.is_active = not employee.is_active
        db_session.add(employee)
        db_session.commit()

    flash("وضعیت فعالیت متخصص به‌روز شد.", "success")
    return redirect(url_for("admin.employees"))


@admin.post("/service-fields/")
@admin_required
def service_field_create():
    name = request.form.get("field_name", "").strip()
    price_value = request.form.get("field_price", "").strip()
    try:
        price = int(price_value)
    except ValueError:
        price = -1

    if not name or len(name) > 100 or price < 0:
        flash("عنوان تخصص و مبلغ معتبر وارد کنید.", "error")
        return redirect(url_for("admin.employees"))

    with Session(engine) as db_session:
        db_session.add(ServiceField(field_name=name, field_price=price))
        try:
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if "field_name" not in str(error.orig):
                raise
            flash("این تخصص قبلاً ثبت شده است.", "error")
            return redirect(url_for("admin.employees"))

    flash("حوزهٔ تخصصی اضافه شد.", "success")
    return redirect(url_for("admin.employees"))


@admin.get("/availability/")
@admin_required
def availability():
    with Session(engine) as db_session:
        employees = db_session.exec(
            select(Employee)
            .where(Employee.is_active.is_(True))
            .order_by(Employee.employee_name)
        ).all()
        slots = db_session.exec(
            select(SetTime, Employee)
            .join(Employee, SetTime.employee_id == Employee.employee_id)
            .where(SetTime.appointment_date >= date.today())
            .order_by(SetTime.appointment_date, SetTime.start_time)
            .limit(250)
        ).all()
        booked_slot_ids = set(
            db_session.exec(
                select(Meet.set_time_id).where(Meet.meet_done != 2)
            ).all()
        )

    return render_template(
        "admin/availability.html",
        employees=employees,
        slots=slots,
        booked_slot_ids=booked_slot_ids,
        today=date.today(),
    )


@admin.post("/availability/")
@admin_required
def availability_create():
    return _save_availability_slot()


@admin.post("/availability/<int:slot_id>/edit/")
@admin_required
def availability_edit(slot_id: int):
    return _save_availability_slot(slot_id)


def _save_availability_slot(slot_id: int | None = None):
    try:
        employee_id = int(request.form.get("employee_id", ""))
        slot_date = date.fromisoformat(request.form.get("appointment_date", ""))
        slot_time = time.fromisoformat(request.form.get("start_time", ""))
    except ValueError:
        flash("متخصص، تاریخ و ساعت را به‌درستی انتخاب کنید.", "error")
        return redirect(url_for("admin.availability"))

    if slot_date < date.today() or (
        slot_date == date.today() and slot_time <= datetime.now().time()
    ):
        flash("برای زمان گذشته نمی‌توان نوبت جدید ثبت کرد.", "error")
        return redirect(url_for("admin.availability"))

    with Session(engine) as db_session:
        employee = db_session.get(Employee, employee_id)
        if employee is None or not employee.is_active:
            flash("متخصص انتخاب‌شده فعال نیست.", "error")
            return redirect(url_for("admin.availability"))

        if slot_id is None:
            slot = SetTime(
                employee_id=employee_id,
                appointment_date=slot_date,
                start_time=slot_time,
            )
            db_session.add(slot)
        else:
            slot = db_session.get(SetTime, slot_id)
            if slot is None:
                abort(404)
            has_appointments = db_session.exec(
                select(Meet.meet_id).where(Meet.set_time_id == slot_id)
            ).first()
            if has_appointments is not None:
                flash("زمان دارای سابقهٔ رزرو را نمی‌توان ویرایش کرد.", "error")
                return redirect(url_for("admin.availability"))
            slot.employee_id = employee_id
            slot.appointment_date = slot_date
            slot.start_time = slot_time

        try:
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if not _is_availability_conflict(error):
                raise
            flash("این زمان برای متخصص انتخاب‌شده قبلاً ثبت شده است.", "error")
            return redirect(url_for("admin.availability"))

    flash("زمان در دسترس ذخیره شد.", "success")
    return redirect(url_for("admin.availability"))


@admin.post("/availability/<int:slot_id>/delete/")
@admin_required
def availability_delete(slot_id: int):
    with Session(engine) as db_session:
        slot = db_session.get(SetTime, slot_id)
        if slot is None:
            abort(404)
        has_appointments = db_session.exec(
            select(Meet.meet_id).where(Meet.set_time_id == slot_id)
        ).first()
        if has_appointments is not None:
            flash("زمانی که سابقهٔ رزرو دارد قابل حذف نیست.", "error")
        else:
            db_session.delete(slot)
            db_session.commit()
            flash("زمان در دسترس حذف شد.", "success")

    return redirect(url_for("admin.availability"))


@admin.get("/appointments/")
@admin_required
def appointments():
    with Session(engine) as db_session:
        clients = db_session.exec(
            select(Client)
            .where(Client.is_active.is_(True))
            .order_by(Client.client_name)
        ).all()
        employees = db_session.exec(
            select(Employee)
            .where(Employee.is_active.is_(True))
            .order_by(Employee.employee_name)
        ).all()
        slots = db_session.exec(
            select(SetTime, Employee)
            .join(Employee, SetTime.employee_id == Employee.employee_id)
            .where(
                SetTime.appointment_date >= date.today(),
                Employee.is_active.is_(True),
            )
            .order_by(SetTime.appointment_date, SetTime.start_time)
            .limit(300)
        ).all()
        current_time = datetime.now().time()
        slots = [
            row
            for row in slots
            if row[0].appointment_date > date.today()
            or (
                row[0].appointment_date == date.today()
                and row[0].start_time > current_time
            )
        ]
        booked_slot_ids = set(
            db_session.exec(
                select(Meet.set_time_id).where(Meet.meet_done != 2)
            ).all()
        )
        available_slots = [
            row for row in slots if row[0].set_time_id not in booked_slot_ids
        ]
        appointment_rows = db_session.exec(
            select(Meet, SetTime, Employee, Client, Payment)
            .join(Payment, Meet.payment_id == Payment.pay_id)
            .join(Client, Payment.client_id == Client.client_id)
            .join(SetTime, Meet.set_time_id == SetTime.set_time_id)
            .join(Employee, SetTime.employee_id == Employee.employee_id)
            .order_by(SetTime.appointment_date.desc(), SetTime.start_time.desc())
            .limit(250)
        ).all()

    return render_template(
        "admin/appointments.html",
        clients=clients,
        slots=slots,
        available_slots=available_slots,
        booked_slot_ids=booked_slot_ids,
        appointment_rows=appointment_rows,
    )


@admin.post("/appointments/")
@admin_required
def appointment_create():
    try:
        client_id = int(request.form.get("client_id", ""))
        slot_id = int(request.form.get("set_time_id", ""))
        count_meet = int(request.form.get("count_meet", "1"))
        total_price = int(request.form.get("total_price", ""))
        payment_status = int(request.form.get("payment_status", "0"))
    except ValueError:
        flash("اطلاعات رزرو را کامل و معتبر وارد کنید.", "error")
        return redirect(url_for("admin.appointments"))

    if count_meet < 1 or total_price < 0 or payment_status not in {0, 1}:
        flash("تعداد جلسه، مبلغ یا وضعیت پرداخت معتبر نیست.", "error")
        return redirect(url_for("admin.appointments"))

    with Session(engine) as db_session:
        client = db_session.get(Client, client_id)
        slot = db_session.get(SetTime, slot_id)
        if client is None or not client.is_active:
            flash("کاربر انتخاب‌شده فعال نیست.", "error")
            return redirect(url_for("admin.appointments"))
        if slot is None or slot.appointment_date < date.today() or (
            slot.appointment_date == date.today()
            and slot.start_time <= datetime.now().time()
        ):
            flash("زمان جلسه در دسترس نیست.", "error")
            return redirect(url_for("admin.appointments"))
        employee = db_session.get(Employee, slot.employee_id)
        if employee is None or not employee.is_active:
            flash("متخصص این زمان فعال نیست.", "error")
            return redirect(url_for("admin.appointments"))
        existing_booking = db_session.exec(
            select(Meet.meet_id).where(
                Meet.set_time_id == slot_id,
                Meet.meet_done != 2,
            )
        ).first()
        if existing_booking is not None:
            flash("این زمان قبلاً رزرو شده است.", "error")
            return redirect(url_for("admin.appointments"))

        payment = Payment(
            employee_id=employee.employee_id,
            client_id=client.client_id,
            count_meet=count_meet,
            total_price=total_price,
            payment_status=payment_status,
            confirmed_at=datetime.utcnow() if payment_status == 1 else None,
        )
        db_session.add(payment)
        db_session.flush()
        db_session.add(
            Meet(
                payment_id=payment.pay_id,
                set_time_id=slot.set_time_id,
                meet_done=0,
            )
        )
        try:
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if not _is_slot_conflict(error):
                raise
            flash("رزرو انجام نشد؛ ممکن است این زمان هم‌زمان رزرو شده باشد.", "error")
            return redirect(url_for("admin.appointments"))

    flash("جلسه با موفقیت رزرو شد.", "success")
    return redirect(url_for("admin.appointments"))


@admin.post("/appointments/<int:meet_id>/edit/")
@admin_required
def appointment_edit(meet_id: int):
    try:
        status = int(request.form.get("meet_done", ""))
    except ValueError:
        flash("وضعیت جلسه معتبر نیست.", "error")
        return redirect(url_for("admin.appointments"))
    if status not in {0, 1, 2}:
        flash("وضعیت جلسه معتبر نیست.", "error")
        return redirect(url_for("admin.appointments"))

    new_slot_value = request.form.get("set_time_id", "").strip()
    with Session(engine) as db_session:
        meet = db_session.get(Meet, meet_id)
        if meet is None:
            abort(404)
        if new_slot_value:
            try:
                new_slot_id = int(new_slot_value)
            except ValueError:
                flash("زمان جدید معتبر نیست.", "error")
                return redirect(url_for("admin.appointments"))
            slot = db_session.get(SetTime, new_slot_id)
            if slot is None:
                flash("زمان جدید پیدا نشد.", "error")
                return redirect(url_for("admin.appointments"))
            if status != 2:
                employee = db_session.get(Employee, slot.employee_id)
                if (
                    employee is None
                    or not employee.is_active
                    or slot.appointment_date < date.today()
                    or (
                        slot.appointment_date == date.today()
                        and slot.start_time <= datetime.now().time()
                    )
                ):
                    flash("زمان جدید باید آینده و متعلق به متخصص فعال باشد.", "error")
                    return redirect(url_for("admin.appointments"))
                existing_booking = db_session.exec(
                    select(Meet.meet_id).where(
                        Meet.set_time_id == new_slot_id,
                        Meet.meet_done != 2,
                        Meet.meet_id != meet_id,
                    )
                ).first()
                if existing_booking is not None:
                    flash("زمان انتخاب‌شده قبلاً رزرو شده است.", "error")
                    return redirect(url_for("admin.appointments"))
            meet.set_time_id = new_slot_id
        elif status == 0:
            current_slot = db_session.get(SetTime, meet.set_time_id)
            if current_slot is None or current_slot.appointment_date < date.today() or (
                current_slot.appointment_date == date.today()
                and current_slot.start_time <= datetime.now().time()
            ):
                flash("برای فعال‌کردن دوبارهٔ رزرو، زمان آینده انتخاب کنید.", "error")
                return redirect(url_for("admin.appointments"))
        meet.meet_done = status
        try:
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if not _is_slot_conflict(error):
                raise
            flash("تغییر جلسه ذخیره نشد؛ زمان انتخاب‌شده رزرو شده است.", "error")
            return redirect(url_for("admin.appointments"))

    flash("اطلاعات جلسه به‌روز شد.", "success")
    return redirect(url_for("admin.appointments"))


@admin.get("/payments/")
@admin_required
def payments():
    with Session(engine) as db_session:
        payment_rows = db_session.exec(
            select(Payment, Client, Employee)
            .join(Client, Payment.client_id == Client.client_id)
            .join(Employee, Payment.employee_id == Employee.employee_id)
            .order_by(Payment.pay_id.desc())
            .limit(250)
        ).all()

    return render_template("admin/payments.html", payment_rows=payment_rows)


@admin.post("/payments/<int:payment_id>/")
@admin_required
def payment_update(payment_id: int):
    try:
        status = int(request.form.get("payment_status", ""))
        amount = int(request.form.get("total_price", ""))
    except ValueError:
        flash("وضعیت یا مبلغ پرداخت معتبر نیست.", "error")
        return redirect(url_for("admin.payments"))
    if status not in {0, 1, 2} or amount < 0:
        flash("وضعیت یا مبلغ پرداخت معتبر نیست.", "error")
        return redirect(url_for("admin.payments"))

    tracking_code = request.form.get("tracking_code", "").strip()
    if len(tracking_code) > 50:
        flash("کد پیگیری حداکثر ۵۰ نویسه است.", "error")
        return redirect(url_for("admin.payments"))

    with Session(engine) as db_session:
        payment = db_session.get(Payment, payment_id)
        if payment is None:
            abort(404)
        payment.payment_status = status
        payment.total_price = amount
        payment.transfer_tracking_code = tracking_code or None
        if status == 1 and payment.confirmed_at is None:
            payment.confirmed_at = datetime.utcnow()
        elif status != 1:
            payment.confirmed_at = None
        db_session.add(payment)
        db_session.commit()

    flash("اطلاعات پرداخت به‌روز شد.", "success")
    return redirect(url_for("admin.payments"))


@admin.get("/tickets/")
@admin_required
def tickets():
    with Session(engine) as db_session:
        ticket_rows = db_session.exec(
            select(Ticket).order_by(Ticket.ticket_id.desc()).limit(250)
        ).all()

    return render_template("admin/tickets.html", tickets=ticket_rows)


@admin.post("/tickets/<int:ticket_id>/")
@admin_required
def ticket_update(ticket_id: int):
    try:
        status = int(request.form.get("ticket_status", ""))
    except ValueError:
        flash("وضعیت تیکت معتبر نیست.", "error")
        return redirect(url_for("admin.tickets"))
    if status not in {0, 1, 2}:
        flash("وضعیت تیکت معتبر نیست.", "error")
        return redirect(url_for("admin.tickets"))

    response_text = request.form.get("status_response", "").strip()
    with Session(engine) as db_session:
        ticket = db_session.get(Ticket, ticket_id)
        if ticket is None:
            abort(404)
        ticket.ticket_status = status
        ticket.status_response = response_text or None
        db_session.add(ticket)
        db_session.commit()

    flash("وضعیت تیکت به‌روز شد.", "success")
    return redirect(url_for("admin.tickets"))


@admin.get("/articles/")
@admin_required
def articles():
    with Session(engine) as db_session:
        article_rows = db_session.exec(
            select(Article).order_by(Article.article_id.desc()).limit(250)
        ).all()

    return render_template("admin/articles.html", articles=article_rows)


@admin.route("/articles/new/", methods=["GET", "POST"])
@admin_required
def article_create():
    if request.method == "GET":
        return render_template(
            "admin/article_form.html",
            article=None,
            form_values={"author_name": g.current_admin.admin_name},
        )

    values, error = _article_form_data(request.form)
    if error:
        flash(error, "error")
        return render_template(
            "admin/article_form.html",
            article=None,
            form_values=request.form,
        ), 400

    with Session(engine) as db_session:
        slug_exists = db_session.exec(
            select(Article.article_id).where(Article.slug == values["slug"])
        ).first()
        if slug_exists is not None:
            flash("این نشانی مقاله قبلاً استفاده شده است.", "error")
            return render_template(
                "admin/article_form.html",
                article=None,
                form_values=request.form,
            ), 400

        db_session.add(
            Article(
                **values,
                created_by_admin_id=g.current_admin.admin_id,
            )
        )
        try:
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if "slug" not in str(error.orig):
                raise
            flash("این نشانی مقاله قبلاً استفاده شده است.", "error")
            return render_template(
                "admin/article_form.html",
                article=None,
                form_values=request.form,
            ), 400

    flash("مقاله ذخیره شد.", "success")
    return redirect(url_for("admin.articles"))


@admin.route("/articles/<int:article_id>/edit/", methods=["GET", "POST"])
@admin_required
def article_edit(article_id: int):
    with Session(engine) as db_session:
        article = db_session.get(Article, article_id)
        if article is None:
            abort(404)

        if request.method == "GET":
            return render_template(
                "admin/article_form.html",
                article=article,
                form_values={},
            )

        values, error = _article_form_data(request.form)
        if error:
            flash(error, "error")
            return render_template(
                "admin/article_form.html",
                article=article,
                form_values=request.form,
            ), 400

        slug_exists = db_session.exec(
            select(Article.article_id).where(
                Article.slug == values["slug"],
                Article.article_id != article_id,
            )
        ).first()
        if slug_exists is not None:
            flash("این نشانی مقاله قبلاً استفاده شده است.", "error")
            return render_template(
                "admin/article_form.html",
                article=article,
                form_values=request.form,
            ), 400

        for field_name, value in values.items():
            setattr(article, field_name, value)
        try:
            db_session.commit()
        except IntegrityError as error:
            db_session.rollback()
            if "slug" not in str(error.orig):
                raise
            flash("این نشانی مقاله قبلاً استفاده شده است.", "error")
            return redirect(url_for("admin.article_edit", article_id=article_id))

    flash("مقاله به‌روز شد.", "success")
    return redirect(url_for("admin.articles"))


@admin.post("/articles/<int:article_id>/delete/")
@admin_required
def article_delete(article_id: int):
    with Session(engine) as db_session:
        article = db_session.get(Article, article_id)
        if article is None:
            abort(404)
        db_session.delete(article)
        db_session.commit()

    flash("مقاله حذف شد.", "success")
    return redirect(url_for("admin.articles"))
