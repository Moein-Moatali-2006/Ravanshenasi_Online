from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event


DATABASE_URL = "sqlite:///DBRO.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)


# Enable SQLite foreign keys
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_and_tables():
    from database import models

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
