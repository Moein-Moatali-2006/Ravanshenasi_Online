import unittest
import uuid
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime

from app import create_app
from database.connection import engine
from database.models import (
    Admin,
    Article,
    Client,
    Employee,
    Meet,
    Payment,
    ServiceField,
    SetTime,
)
from sqlmodel import Session, select
from werkzeug.security import check_password_hash, generate_password_hash


class TestPageRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def csrf_token(self):
        with self.client.session_transaction() as browser_session:
            return browser_session["csrf_token"]

    def test_existing_pages_render(self):
        pages = (
            "/",
            "/about/",
            "/support/",
            "/register/",
            "/login/",
        )

        for path in pages:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_only_page_stylesheet_is_included(self):
        page_styles = {
            "/": "home.css",
            "/about/": "about.css",
            "/support/": "support.css",
            "/register/": "register.css",
            "/login/": "login.css",
        }

        for path, stylesheet in page_styles.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                html = response.get_data(as_text=True)
                self.assertIn(f"css/{stylesheet}", html)

                for other_stylesheet in set(page_styles.values()) - {stylesheet}:
                    self.assertNotIn(f"css/{other_stylesheet}", html)

    def test_page_stylesheet_is_served(self):
        response = self.client.get("/static/css/home.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(".home-page", response.get_data(as_text=True))
        response.close()
        profile_stylesheet = self.client.get("/static/css/profile.css")
        self.assertEqual(profile_stylesheet.status_code, 200)
        self.assertIn(".profile-page", profile_stylesheet.get_data(as_text=True))
        profile_stylesheet.close()

    def test_service_pages_have_separate_content_and_support_links(self):
        services = {
            "couples": "زوج‌درمانی",
            "individual": "مشاوره فردی",
            "educational": "مشاوره تحصیلی",
            "mental-disorders": "مشکلات و اختلالات روان‌شناختی",
            "sex-therapy": "سکس‌تراپی",
        }

        for slug, title in services.items():
            with self.subTest(service=slug):
                response = self.client.get(f"/services/{slug}/")
                html = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(title, html)
                self.assertIn('href="/support/#support-form"', html)
                self.assertGreaterEqual(html.count("<img "), 3)
                self.assertIn("css/service-detail.css", html)

        self.assertEqual(self.client.get("/services/unknown/").status_code, 404)
        services_index = self.client.get("/services/")
        self.assertEqual(services_index.status_code, 200)
        self.assertIn("خدمات روان‌شناختی", services_index.get_data(as_text=True))

    def test_registration_and_remembered_login(self):
        phone = f"09{uuid.uuid4().int % 1_000_000_000:09d}"
        self.addCleanup(self.delete_client, phone)

        self.client.get("/register/")
        registration = self.client.post(
            "/register/",
            data={
                "csrf_token": self.csrf_token(),
                "full_name": "کاربر آزمایشی",
                "phone": phone,
                "password": "12345678",
                "confirm_password": "12345678",
            },
        )
        self.assertEqual(registration.status_code, 302)
        self.assertTrue(registration.headers["Location"].endswith("/login/"))

        with Session(engine) as db_session:
            client = db_session.exec(
                select(Client).where(Client.client_phone == phone)
            ).first()
            self.assertIsNotNone(client)
            self.assertNotEqual(client.password_hash, "12345678")
            self.assertTrue(check_password_hash(client.password_hash, "12345678"))

        login = self.client.post(
            "/login/",
            data={
                "csrf_token": self.csrf_token(),
                "login_method": "password",
                "phone": phone,
                "password": "12345678",
                "remember_me": "on",
            },
        )
        self.assertEqual(login.status_code, 302)
        self.assertTrue(login.headers["Location"].endswith("/"))
        expires = parsedate_to_datetime(
            login.headers["Set-Cookie"].split("Expires=", 1)[1].split(";", 1)[0]
        )
        remaining = expires - datetime.now(timezone.utc)
        self.assertGreater(remaining.total_seconds(), 14 * 24 * 60 * 60)
        self.assertLessEqual(remaining.total_seconds(), 15 * 24 * 60 * 60)

        with self.client.session_transaction() as browser_session:
            self.assertTrue(browser_session.permanent)
            self.assertEqual(browser_session["client_name"], "کاربر آزمایشی")

        home = self.client.get("/")
        home_html = home.get_data(as_text=True)
        self.assertIn("پروفایل کاربری", home_html)
        self.assertIn("خروج از حساب", home_html)
        self.assertNotIn('class="btn btn-login"', home_html)
        self.assertNotIn('class="btn btn-register"', home_html)

        profile = self.client.get("/profile/")
        self.assertEqual(profile.status_code, 200)
        self.assertIn("css/profile.css", profile.get_data(as_text=True))
        self.assertIn("کاربر آزمایشی", profile.get_data(as_text=True))

        self.client.get("/")
        logout = self.client.post(
            "/logout/", data={"csrf_token": self.csrf_token()}
        )
        self.assertEqual(logout.status_code, 302)
        with self.client.session_transaction() as browser_session:
            self.assertNotIn("client_id", browser_session)

        anonymous_home = self.client.get("/").get_data(as_text=True)
        self.assertIn('class="btn btn-login"', anonymous_home)
        self.assertIn('class="btn btn-register"', anonymous_home)
        self.assertNotIn("پروفایل کاربری", anonymous_home)
        self.assertNotIn("خروج از حساب", anonymous_home)

    def test_profile_requires_login(self):
        response = self.client.get("/profile/")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login/"))

    def test_profile_updates_contact_info_and_password(self):
        phone = f"09{uuid.uuid4().int % 1_000_000_000:09d}"
        self.addCleanup(self.delete_client, phone)

        with Session(engine) as db_session:
            client = Client(
                client_name="کاربر پروفایل",
                client_phone=phone,
                password_hash=generate_password_hash("old-password"),
            )
            db_session.add(client)
            db_session.commit()
            client_id = client.client_id
        self.addCleanup(self.delete_profile_client, client_id)

        with self.client.session_transaction() as browser_session:
            browser_session["client_id"] = client_id
            browser_session["client_name"] = "کاربر پروفایل"

        profile = self.client.get("/profile/")
        self.assertEqual(profile.status_code, 200)
        with self.client.session_transaction() as browser_session:
            csrf_token = browser_session["csrf_token"]

        changed_phone = f"09{(uuid.uuid4().int + 1) % 1_000_000_000:09d}"
        update = self.client.post(
            "/profile/",
            data={
                "csrf_token": csrf_token,
                "action": "update_profile",
                "full_name": "نام به‌روز",
                "phone": changed_phone,
            },
        )
        self.assertEqual(update.status_code, 302)
        with Session(engine) as db_session:
            updated_client = db_session.get(Client, client_id)
            self.assertEqual(updated_client.client_name, "نام به‌روز")
            self.assertEqual(updated_client.client_phone, changed_phone)

        password_update = self.client.post(
            "/profile/",
            data={
                "csrf_token": csrf_token,
                "action": "change_password",
                "current_password": "old-password",
                "new_password": "new-password",
                "confirm_password": "new-password",
            },
        )
        self.assertEqual(password_update.status_code, 302)
        with Session(engine) as db_session:
            updated_client = db_session.get(Client, client_id)
            self.assertTrue(
                check_password_hash(updated_client.password_hash, "new-password")
            )
            self.assertFalse(
                check_password_hash(updated_client.password_hash, "old-password")
            )

        invalid_csrf = self.client.post(
            "/profile/",
            data={
                "csrf_token": "invalid",
                "action": "update_profile",
                "full_name": "نباید ذخیره شود",
                "phone": changed_phone,
            },
        )
        self.assertEqual(invalid_csrf.status_code, 400)
        with Session(engine) as db_session:
            unchanged_client = db_session.get(Client, client_id)
            self.assertEqual(unchanged_client.client_name, "نام به‌روز")

    def test_profile_displays_upcoming_sessions_and_payment_history(self):
        phone = f"09{uuid.uuid4().int % 1_000_000_000:09d}"
        employee_phone = f"09{(uuid.uuid4().int + 1) % 1_000_000_000:09d}"
        with Session(engine) as db_session:
            client = Client(
                client_name="کاربر دارای جلسه",
                client_phone=phone,
                password_hash=generate_password_hash("test-password"),
            )
            employee = Employee(
                employee_name="مشاور آزمایشی",
                employee_phone=employee_phone,
                employee_email="profile-test@example.com",
            )
            db_session.add(client)
            db_session.add(employee)
            db_session.commit()
            client_id = client.client_id
            employee_id = employee.employee_id

            payment = Payment(
                employee_id=employee_id,
                client_id=client_id,
                count_meet=3,
                total_price=120000,
                payment_status=1,
            )
            set_time = SetTime(
                employee_id=employee_id,
                appointment_date=date.today() + timedelta(days=7),
                start_time=time(10, 30),
            )
            db_session.add(payment)
            db_session.add(set_time)
            db_session.commit()

            db_session.add(
                Meet(
                    payment_id=payment.pay_id,
                    set_time_id=set_time.set_time_id,
                    meet_done=0,
                )
            )
            db_session.commit()

        self.addCleanup(self.delete_profile_activity, client_id, employee_id)
        with self.client.session_transaction() as browser_session:
            browser_session["client_id"] = client_id

        response = self.client.get("/profile/")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("مشاوره با مشاور آزمایشی", html)
        self.assertIn("بستهٔ 3 جلسه‌ای", html)
        self.assertIn("تأییدشده", html)

    def test_registration_rejects_password_shorter_than_eight_characters(self):
        self.client.get("/register/")
        response = self.client.post(
            "/register/",
            data={
                "csrf_token": self.csrf_token(),
                "full_name": "کاربر آزمایشی",
                "phone": "09123456789",
                "password": "1234567",
                "confirm_password": "1234567",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("حداقل ۸ کاراکتر", response.get_data(as_text=True))

    @staticmethod
    def delete_client(phone):
        with Session(engine) as db_session:
            client = db_session.exec(
                select(Client).where(Client.client_phone == phone)
            ).first()
            if client is not None:
                db_session.delete(client)
                db_session.commit()

    @staticmethod
    def delete_profile_client(client_id):
        with Session(engine) as db_session:
            client = db_session.get(Client, client_id)
            if client is not None:
                db_session.delete(client)
                db_session.commit()

    @staticmethod
    def delete_profile_activity(client_id, employee_id):
        with Session(engine) as db_session:
            payments = db_session.exec(
                select(Payment).where(Payment.client_id == client_id)
            ).all()
            payment_ids = [payment.pay_id for payment in payments]
            if payment_ids:
                meets = db_session.exec(
                    select(Meet).where(Meet.payment_id.in_(payment_ids))
                ).all()
                for meet in meets:
                    db_session.delete(meet)
                for payment in payments:
                    db_session.delete(payment)

            set_times = db_session.exec(
                select(SetTime).where(SetTime.employee_id == employee_id)
            ).all()
            for set_time in set_times:
                db_session.delete(set_time)

            employee = db_session.get(Employee, employee_id)
            client = db_session.get(Client, client_id)
            if employee is not None:
                db_session.delete(employee)
            if client is not None:
                db_session.delete(client)
            db_session.commit()


class TestAdminRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()
        self.username = f"test-admin-{uuid.uuid4().hex[:12]}"
        with Session(engine) as db_session:
            admin = Admin(
                admin_name="مدیر آزمایشی",
                admin_username=self.username,
                password_hash=generate_password_hash("test-admin-password"),
            )
            db_session.add(admin)
            db_session.commit()
            self.admin_id = admin.admin_id
        self.addCleanup(self.delete_admin, self.admin_id)

    def csrf_token(self):
        with self.client.session_transaction() as browser_session:
            return browser_session["csrf_token"]

    def login_admin(self):
        self.client.get("/admin/login/")
        response = self.client.post(
            "/admin/login/",
            data={
                "csrf_token": self.csrf_token(),
                "username": self.username,
                "password": "test-admin-password",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_pages_require_authentication_and_render(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/login/"))

        self.login_admin()
        for path in (
            "/admin/",
            "/admin/clients/",
            "/admin/employees/",
            "/admin/availability/",
            "/admin/appointments/",
            "/admin/payments/",
            "/admin/tickets/",
            "/admin/articles/",
            "/admin/articles/new/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_create_admin_cli_requires_password_and_stores_hash(self):
        username = f"bootstrap-{uuid.uuid4().hex[:12]}"
        runner = self.app.test_cli_runner()
        missing_password = runner.invoke(
            args=["create-admin", "--username", username],
            env={"ADMIN_INITIAL_PASSWORD": ""},
        )
        self.assertNotEqual(missing_password.exit_code, 0)

        password = "bootstrap-test-password"
        result = runner.invoke(
            args=["create-admin", "--username", username],
            env={"ADMIN_INITIAL_PASSWORD": password},
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.addCleanup(self.delete_admin_by_username, username)
        with Session(engine) as db_session:
            admin = db_session.exec(
                select(Admin).where(Admin.admin_username == username)
            ).first()
            self.assertIsNotNone(admin)
            self.assertNotEqual(admin.password_hash, password)
            self.assertTrue(check_password_hash(admin.password_hash, password))

    def test_published_article_appears_in_blog_and_sitemap(self):
        self.login_admin()
        slug = f"admin-test-{uuid.uuid4().hex[:12]}"
        response = self.client.post(
            "/admin/articles/new/",
            data={
                "csrf_token": self.csrf_token(),
                "title": "مقالهٔ آزمایشی",
                "slug": slug,
                "topic": "آزمایش",
                "image_path": "images/test-article.jpg",
                "meta_description": "توضیحات کوتاه برای موتورهای جست‌وجو",
                "content": "متن مقالهٔ آزمایشی برای بررسی انتشار.",
                "author_name": "نویسندهٔ آزمایشی",
                "is_published": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.addCleanup(self.delete_test_article, slug)

        article_response = self.client.get(f"/blog/{slug}/")
        article_html = article_response.get_data(as_text=True)
        self.assertEqual(article_response.status_code, 200)
        self.assertIn("توضیحات کوتاه برای موتورهای جست‌وجو", article_html)
        self.assertIn("application/ld+json", article_html)

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(slug, sitemap.get_data(as_text=True))

    def test_employee_can_be_edited_and_deactivated(self):
        self.login_admin()
        suffix = uuid.uuid4().int % 1_000_000_000
        phone = f"09{suffix:09d}"
        with Session(engine) as db_session:
            service_field = ServiceField(
                field_name=f"حوزه آزمایشی {uuid.uuid4().hex[:8]}",
                field_price=1000,
            )
            employee = Employee(
                employee_name="متخصص اولیه",
                employee_phone=phone,
                employee_email=f"{uuid.uuid4().hex[:8]}@example.com",
                fields=[service_field],
            )
            db_session.add(employee)
            db_session.commit()
            employee_id = employee.employee_id
            field_id = service_field.field_id
        self.addCleanup(self.delete_test_employee, employee_id, field_id)

        edit = self.client.post(
            f"/admin/employees/{employee_id}/edit/",
            data={
                "csrf_token": self.csrf_token(),
                "employee_name": "متخصص ویرایش‌شده",
                "employee_phone": phone,
                "employee_email": "updated@example.com",
                "field_ids": str(field_id),
            },
        )
        self.assertEqual(edit.status_code, 302)

        toggle = self.client.post(
            f"/admin/employees/{employee_id}/toggle/",
            data={"csrf_token": self.csrf_token()},
        )
        self.assertEqual(toggle.status_code, 302)
        with Session(engine) as db_session:
            employee = db_session.get(Employee, employee_id)
            self.assertEqual(employee.employee_name, "متخصص ویرایش‌شده")
            self.assertFalse(employee.is_active)

    def test_admin_booking_does_not_double_book_a_slot(self):
        self.login_admin()
        suffix = uuid.uuid4().int % 1_000_000_000
        client_phone = f"09{suffix:09d}"
        employee_phone = f"09{(suffix + 1) % 1_000_000_000:09d}"
        with Session(engine) as db_session:
            client = Client(
                client_name="کاربر رزرو آزمایشی",
                client_phone=client_phone,
            )
            employee = Employee(
                employee_name="متخصص رزرو آزمایشی",
                employee_phone=employee_phone,
                employee_email=f"{uuid.uuid4().hex[:8]}@example.com",
            )
            db_session.add(client)
            db_session.add(employee)
            db_session.commit()
            slot = SetTime(
                employee_id=employee.employee_id,
                appointment_date=date.today() + timedelta(days=1),
                start_time=time(10, 0),
            )
            db_session.add(slot)
            db_session.commit()
            client_id = client.client_id
            employee_id = employee.employee_id
            slot_id = slot.set_time_id
        self.addCleanup(self.delete_test_booking, client_id, employee_id, slot_id)

        form_data = {
            "csrf_token": self.csrf_token(),
            "client_id": str(client_id),
            "set_time_id": str(slot_id),
            "count_meet": "1",
            "total_price": "100000",
            "payment_status": "0",
        }
        first = self.client.post("/admin/appointments/", data=form_data)
        second = self.client.post("/admin/appointments/", data=form_data)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)

        with Session(engine) as db_session:
            bookings = db_session.exec(
                select(Meet).where(Meet.set_time_id == slot_id)
            ).all()
        self.assertEqual(len(bookings), 1)

    @staticmethod
    def delete_admin(admin_id):
        with Session(engine) as db_session:
            articles = db_session.exec(
                select(Article).where(Article.created_by_admin_id == admin_id)
            ).all()
            for article in articles:
                db_session.delete(article)
            admin = db_session.get(Admin, admin_id)
            if admin is not None:
                db_session.delete(admin)
            db_session.commit()

    @staticmethod
    def delete_admin_by_username(username):
        with Session(engine) as db_session:
            admin = db_session.exec(
                select(Admin).where(Admin.admin_username == username)
            ).first()
            if admin is not None:
                db_session.delete(admin)
                db_session.commit()

    @staticmethod
    def delete_test_article(slug):
        with Session(engine) as db_session:
            article = db_session.exec(
                select(Article).where(Article.slug == slug)
            ).first()
            if article is not None:
                db_session.delete(article)
                db_session.commit()

    @staticmethod
    def delete_test_booking(client_id, employee_id, slot_id):
        with Session(engine) as db_session:
            payments = db_session.exec(
                select(Payment).where(Payment.client_id == client_id)
            ).all()
            payment_ids = [payment.pay_id for payment in payments]
            if payment_ids:
                for meet in db_session.exec(
                    select(Meet).where(Meet.payment_id.in_(payment_ids))
                ).all():
                    db_session.delete(meet)
                for payment in payments:
                    db_session.delete(payment)
            slot = db_session.get(SetTime, slot_id)
            client = db_session.get(Client, client_id)
            employee = db_session.get(Employee, employee_id)
            if slot is not None:
                db_session.delete(slot)
            if client is not None:
                db_session.delete(client)
            if employee is not None:
                db_session.delete(employee)
            db_session.commit()

    @staticmethod
    def delete_test_employee(employee_id, field_id):
        with Session(engine) as db_session:
            employee = db_session.get(Employee, employee_id)
            if employee is not None:
                employee.fields = []
                db_session.delete(employee)
            service_field = db_session.get(ServiceField, field_id)
            if service_field is not None:
                db_session.delete(service_field)
            db_session.commit()


if __name__ == "__main__":
    unittest.main()
