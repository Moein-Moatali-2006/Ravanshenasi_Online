import os

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event, inspect


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///DBRO.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

engine_options = {"echo": False, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_options)


# Enable SQLite foreign keys
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_db_and_tables():
    from database import models

    SQLModel.metadata.create_all(engine)
    migrations = {
        "clients": {
            "password_hash": "VARCHAR",
            "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
            "created_at": "TIMESTAMP",
        },
        "employees": {
            "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
        },
        "articles": {
            "slug": "VARCHAR(220)",
            "meta_description": "VARCHAR(300)",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, columns in migrations.items():
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, column_definition in columns.items():
                if column_name not in existing_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN "
                        f"{column_name} {column_definition}"
                    )
        if engine.dialect.name == "postgresql":
            ticket_columns = {
                column["name"]: column["type"]
                for column in inspector.get_columns("tickets")
            }
            if "sender_callback" in ticket_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE tickets ALTER COLUMN sender_callback "
                    "TYPE VARCHAR(255)"
                )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_articles_slug "
            "ON articles (slug)"
        )


def get_session():
    with Session(engine) as session:
        yield session
