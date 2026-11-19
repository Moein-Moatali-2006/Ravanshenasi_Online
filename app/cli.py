import os

import click
from flask import Flask
from sqlmodel import Session, select
from werkzeug.security import generate_password_hash

from database.connection import engine
from database.models import Admin


def register_admin_commands(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.option("--username", envvar="ADMIN_USERNAME", default="admin")
    @click.option("--name", envvar="ADMIN_NAME", default="مدیر سایت")
    def create_admin(username: str, name: str) -> None:
        """Create the first administrator using ADMIN_INITIAL_PASSWORD."""
        password = os.environ.get("ADMIN_INITIAL_PASSWORD")
        if not password or len(password) < 12:
            raise click.ClickException(
                "ADMIN_INITIAL_PASSWORD must be set to at least 12 characters."
            )

        with Session(engine) as db_session:
            existing_admin = db_session.exec(
                select(Admin).where(Admin.admin_username == username)
            ).first()
            if existing_admin is not None:
                raise click.ClickException(
                    f"Administrator '{username}' already exists."
                )

            db_session.add(
                Admin(
                    admin_name=name,
                    admin_username=username,
                    password_hash=generate_password_hash(password),
                    is_active=True,
                )
            )
            db_session.commit()

        click.echo(f"Administrator '{username}' created.")
