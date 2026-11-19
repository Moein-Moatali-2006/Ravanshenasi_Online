from datetime import date, datetime, time
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Text,
    text,
)
from sqlmodel import SQLModel, Field, Relationship


# =====================================
# 1. Employee Fields (Many-to-Many)
# =====================================

class EmployeeField(SQLModel, table=True):
    __tablename__ = "employee_fields"

    employee_id: int = Field(
        foreign_key="employees.employee_id",
        primary_key=True
    )

    field_id: int = Field(
        foreign_key="fields.field_id",
        primary_key=True
    )

    __table_args__ = (
        Index("idx_employee_fields_field", "field_id"),
    )


# =====================================
# 2. Employees
# =====================================

class Employee(SQLModel, table=True):
    __tablename__ = "employees"

    employee_id: int | None = Field(default=None, primary_key=True)

    employee_name: str = Field(max_length=100)
    begin_date: date | None = None

    employee_phone: str = Field(
        max_length=11,
        unique=True
    )

    employee_email: str = Field(max_length=56)

    primary_meeting_link: str | None = None
    backup_meeting_link: str | None = None
    is_active: bool = Field(default=True)

    fields: list["ServiceField"] = Relationship(
        back_populates="employees",
        link_model=EmployeeField
    )

    set_times: list["SetTime"] = Relationship(
        back_populates="employee"
    )

    payments: list["Payment"] = Relationship(
        back_populates="employee"
    )


# =====================================
# 3. Clients
# =====================================

class Client(SQLModel, table=True):
    __tablename__ = "clients"

    client_id: int | None = Field(default=None, primary_key=True)

    client_name: str = Field(max_length=100)

    client_phone: str = Field(
        max_length=11,
        unique=True
    )

    password_hash: str | None = None
    is_active: bool = Field(default=True)
    created_at: datetime | None = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime,
            server_default=text("CURRENT_TIMESTAMP")
        )
    )

    payments: list["Payment"] = Relationship(
        back_populates="client"
    )


# =====================================
# 4. Fields
# =====================================

class ServiceField(SQLModel, table=True):
    __tablename__ = "fields"

    __table_args__ = (
        CheckConstraint(
            "field_price >= 0",
            name="ck_fields_price_nonnegative"
        ),
    )

    field_id: int | None = Field(default=None, primary_key=True)

    field_name: str = Field(
        max_length=100,
        unique=True
    )

    field_price: int

    employees: list[Employee] = Relationship(
        back_populates="fields",
        link_model=EmployeeField
    )


# =====================================
# 5. Set Times
# =====================================

class SetTime(SQLModel, table=True):
    __tablename__ = "set_times"

    __table_args__ = (
        Index(
            "uq_employee_date_time",
            "employee_id",
            "appointment_date",
            "start_time",
            unique=True
        ),
    )

    set_time_id: int | None = Field(default=None, primary_key=True)

    employee_id: int = Field(
        foreign_key="employees.employee_id"
    )

    appointment_date: date
    start_time: time

    employee: Employee = Relationship(
        back_populates="set_times"
    )

    meets: list["Meet"] = Relationship(
        back_populates="set_time"
    )


# =====================================
# 6. Payments
# =====================================

class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint(
            "count_meet > 0",
            name="ck_payments_count_positive"
        ),
        CheckConstraint(
            "sale_off >= 0",
            name="ck_payments_sale_off_nonnegative"
        ),
        CheckConstraint(
            "total_price >= 0",
            name="ck_payments_total_price_nonnegative"
        ),
        CheckConstraint(
            "payment_status IN (0, 1, 2)",
            name="ck_payments_status"
        ),
        Index("idx_payments_client", "client_id"),
        Index("idx_payments_employee", "employee_id"),
    )

    pay_id: int | None = Field(default=None, primary_key=True)

    employee_id: int = Field(
        foreign_key="employees.employee_id"
    )

    client_id: int = Field(
        foreign_key="clients.client_id"
    )

    count_meet: int
    sale_off: int = Field(default=0)
    total_price: int
    payment_status: int = Field(default=0)

    transfer_tracking_code: str | None = Field(
        default=None,
        max_length=50
    )

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime,
            server_default=text("CURRENT_TIMESTAMP")
        )
    )

    confirmed_at: datetime | None = None

    employee: Employee = Relationship(
        back_populates="payments"
    )

    client: Client = Relationship(
        back_populates="payments"
    )

    meets: list["Meet"] = Relationship(
        back_populates="payment"
    )


# =====================================
# 7. Meets
# =====================================

class Meet(SQLModel, table=True):
    __tablename__ = "meets"

    __table_args__ = (
        CheckConstraint(
            "meet_done IN (0, 1, 2)",
            name="ck_meets_status"
        ),

        Index("idx_meets_payment", "payment_id"),

        Index(
            "idx_meets_active_slot",
            "set_time_id",
            unique=True,
            sqlite_where=text("meet_done <> 2"),
            postgresql_where=text("meet_done <> 2")
        ),
    )

    meet_id: int | None = Field(default=None, primary_key=True)

    payment_id: int = Field(
        foreign_key="payments.pay_id"
    )

    set_time_id: int = Field(
        foreign_key="set_times.set_time_id"
    )

    meet_report: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )

    meet_done: int = Field(default=0)

    payment: Payment = Relationship(
        back_populates="meets"
    )

    set_time: SetTime = Relationship(
        back_populates="meets"
    )


# =====================================
# 8. Tickets
# =====================================

class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"

    __table_args__ = (
        CheckConstraint(
            "ticket_status IN (0, 1, 2)",
            name="ck_tickets_status"
        ),
    )

    ticket_id: int | None = Field(default=None, primary_key=True)

    sender_name: str = Field(max_length=100)
    sender_callback: str = Field(max_length=255)
    title: str = Field(max_length=200)

    client_text: str = Field(
        sa_column=Column(Text, nullable=False)
    )

    status_response: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )

    ticket_status: int = Field(default=0)


# =====================================
# 9. Admins
# =====================================

class Admin(SQLModel, table=True):
    __tablename__ = "admins"

    admin_id: int | None = Field(default=None, primary_key=True)

    admin_name: str = Field(max_length=100)

    admin_username: str = Field(
        max_length=100,
        unique=True
    )

    password_hash: str

    is_active: bool = Field(default=True)

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime,
            server_default=text("CURRENT_TIMESTAMP")
        )
    )

    articles: list["Article"] = Relationship(
        back_populates="admin"
    )


# =====================================
# 10. Articles
# =====================================

class Article(SQLModel, table=True):
    __tablename__ = "articles"

    __table_args__ = (
        Index("idx_articles_topic", "topic"),
        Index("idx_articles_created_at", "created_at"),
        Index("uq_articles_slug", "slug", unique=True),
    )

    article_id: int | None = Field(default=None, primary_key=True)

    title: str = Field(max_length=200)

    slug: str | None = Field(default=None, max_length=220)

    topic: str = Field(max_length=100)

    # Image path or filename, not image binary
    image_path: str = Field(max_length=500)

    meta_description: str | None = Field(default=None, max_length=300)

    content: str = Field(
        sa_column=Column(Text, nullable=False)
    )

    author_name: str = Field(max_length=150)

    # Admin who created this article
    created_by_admin_id: int = Field(
        foreign_key="admins.admin_id"
    )

    is_published: bool = Field(default=False)

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime,
            server_default=text("CURRENT_TIMESTAMP")
        )
    )

    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=datetime.utcnow
        )
    )

    admin: Admin = Relationship(
        back_populates="articles"
    )


class PageView(SQLModel, table=True):
    __tablename__ = "page_views"

    __table_args__ = (
        Index("idx_page_views_viewed_at", "viewed_at"),
    )

    page_view_id: int | None = Field(default=None, primary_key=True)

    path: str = Field(max_length=500, index=True)

    viewed_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
