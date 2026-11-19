from collections.abc import Mapping
import logging
from pathlib import Path
import secrets

from flask import Flask, abort, request, session
from flask_smorest import Api
from hmac import compare_digest
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from database import create_db_and_tables
from database.connection import engine
from database.models import PageView
from sqlmodel import Session


logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config: Mapping[str, object] | None = None) -> Flask:
    app = Flask(
        __name__,
        root_path=str(PROJECT_ROOT),
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(Config)
    if test_config is not None:
        app.config.update(test_config)

    Api(app)

    from app.routes import pages
    from app.admin import admin

    app.register_blueprint(pages)
    app.register_blueprint(admin)
    create_db_and_tables()

    @app.before_request
    def protect_post_requests():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        if request.method == "POST":
            expected_token = session.get("csrf_token", "")
            submitted_token = request.form.get("csrf_token", "")
            if not isinstance(expected_token, str) or not compare_digest(
                expected_token, submitted_token
            ):
                abort(400, description="درخواست نامعتبر است؛ صفحه را تازه‌سازی کنید.")

    @app.context_processor
    def inject_csrf_token():
        return {
            "csrf_token": lambda: session["csrf_token"],
            "public_base_url": (
                app.config["PUBLIC_BASE_URL"] or request.url_root.rstrip("/")
            ),
        }

    @app.after_request
    def record_public_page_view(response):
        if (
            request.method == "GET"
            and response.status_code < 400
            and request.endpoint is not None
            and request.endpoint.startswith("pages.")
        ):
            try:
                with Session(engine) as db_session:
                    db_session.add(PageView(path=request.path))
                    db_session.commit()
            except SQLAlchemyError:
                logger.exception("Could not record page view for %s", request.path)
        return response

    from app.cli import register_admin_commands

    register_admin_commands(app)
    return app
