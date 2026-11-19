
-- =====================================
-- 1. Employees
-- =====================================

CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    begin_date DATE,
    employee_phone VARCHAR(11) NOT NULL UNIQUE,
    employee_email VARCHAR(56) NOT NULL,
    primary_meeting_link VARCHAR,
    backup_meeting_link VARCHAR,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);


-- =====================================
-- 2. Clients
-- =====================================

CREATE TABLE clients (
    client_id SERIAL PRIMARY KEY,
    client_name VARCHAR(100) NOT NULL,
    client_phone VARCHAR(11) NOT NULL UNIQUE,
    password_hash VARCHAR,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =====================================
-- 3. Fields
-- =====================================

CREATE TABLE fields (
    field_id SERIAL PRIMARY KEY,
    field_name VARCHAR(100) NOT NULL UNIQUE,
    field_price INTEGER NOT NULL
        CHECK (field_price >= 0)
);


-- =====================================
-- 4. Employee Fields
-- Many-to-Many
-- =====================================

CREATE TABLE employee_fields (
    employee_id INTEGER REFERENCES employees(employee_id),
    field_id INTEGER REFERENCES fields(field_id),

    PRIMARY KEY (employee_id, field_id)
);


-- =====================================
-- 5. Set Times
-- Admin manages available slots
-- =====================================

CREATE TABLE set_times (
    set_time_id SERIAL PRIMARY KEY,

    employee_id INTEGER NOT NULL
        REFERENCES employees(employee_id),

    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,

    UNIQUE (employee_id, appointment_date, start_time)
);


-- =====================================
-- 6. Payments
-- Offline payments / Session packages
-- =====================================

CREATE TABLE payments (
    pay_id SERIAL PRIMARY KEY,

    employee_id INTEGER NOT NULL
        REFERENCES employees(employee_id),

    client_id INTEGER NOT NULL
        REFERENCES clients(client_id),

    count_meet INTEGER NOT NULL
        CHECK (count_meet > 0),

    sale_off INTEGER DEFAULT 0
        CHECK (sale_off >= 0),

    total_price INTEGER NOT NULL
        CHECK (total_price >= 0),

    payment_status INTEGER DEFAULT 0
        CHECK (payment_status IN (0, 1, 2)),

    transfer_tracking_code VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP

    -- 0 = Pending
    -- 1 = Confirmed
    -- 2 = Rejected
);


-- =====================================
-- 7. Meets
-- =====================================

CREATE TABLE meets (
    meet_id SERIAL PRIMARY KEY,

    payment_id INTEGER NOT NULL
        REFERENCES payments(pay_id),

    set_time_id INTEGER NOT NULL
        REFERENCES set_times(set_time_id),

    meet_report TEXT,

    meet_done INTEGER DEFAULT 0
        CHECK (meet_done IN (0, 1, 2))

    -- 0 = Not Done
    -- 1 = Done
    -- 2 = Cancelled
);


-- =====================================
-- 8. Tickets
-- =====================================

CREATE TABLE tickets (
    ticket_id SERIAL PRIMARY KEY,

    sender_name VARCHAR(100) NOT NULL,
    sender_callback VARCHAR(255) NOT NULL,
    title VARCHAR(200) NOT NULL,

    client_text TEXT NOT NULL,
    status_response TEXT,

    ticket_status INTEGER DEFAULT 0
        CHECK (ticket_status IN (0, 1, 2))

    -- 0 = Pending
    -- 1 = Answered
    -- 2 = Closed
);


-- =====================================
-- 9. Indexes
-- =====================================

CREATE INDEX idx_employee_fields_field
ON employee_fields(field_id);

CREATE INDEX idx_payments_client
ON payments(client_id);

CREATE INDEX idx_payments_employee
ON payments(employee_id);

CREATE INDEX idx_meets_payment
ON meets(payment_id);


-- A time slot can have only one active reservation.
-- Cancelled reservations do not block the slot.

CREATE UNIQUE INDEX idx_meets_active_slot
ON meets(set_time_id)
WHERE meet_done <> 2;


-- =====================================
-- 10. Admins
-- Create the initial password with the `flask create-admin` CLI command.
-- =====================================

CREATE TABLE admins (
    admin_id SERIAL PRIMARY KEY,
    admin_name VARCHAR(100) NOT NULL,
    admin_username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =====================================
-- 11. Articles
-- =====================================

CREATE TABLE articles (
    article_id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(220) UNIQUE,
    topic VARCHAR(100) NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    meta_description VARCHAR(300),
    content TEXT NOT NULL,
    author_name VARCHAR(150) NOT NULL,
    created_by_admin_id INTEGER NOT NULL REFERENCES admins(admin_id),
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_articles_topic ON articles(topic);
CREATE INDEX idx_articles_created_at ON articles(created_at);


-- =====================================
-- 12. Anonymous page-view analytics
-- No IP address or visitor identity is stored.
-- =====================================

CREATE TABLE page_views (
    page_view_id SERIAL PRIMARY KEY,
    path VARCHAR(500) NOT NULL,
    viewed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_page_views_viewed_at ON page_views(viewed_at);
CREATE INDEX ix_page_views_path ON page_views(path);
