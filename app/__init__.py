from collections.abc import Mapping
from pathlib import Path

from flask import Flask
from flask_smorest import Api

from config import Config
from database import create_db_and_tables


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

    app.register_blueprint(pages)
    create_db_and_tables()

    return app
