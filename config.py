import os
import secrets
from datetime import timedelta


class Config:
    API_TITLE = "Ravanshenasi Online API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"

    OPENAPI_URL_PREFIX = "/"
    OPENAPI_SWAGGER_UI_PATH = "/swagger-ui"
    OPENAPI_SWAGGER_UI_URL = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    )

    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    PERMANENT_SESSION_LIFETIME = timedelta(days=15)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", ""
    ).lower() in {"1", "true", "yes"}
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")