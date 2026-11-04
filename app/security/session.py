import os
from collections.abc import Mapping


_DEVELOPMENT_SECRET = "ecoinsumos-local-only-development-secret"
_SESSION_MAX_AGE = 12 * 60 * 60


def session_settings(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    values = os.environ if environment is None else environment
    app_environment = values.get("APP_ENV", "development").strip().lower()
    if app_environment not in {"development", "production"}:
        raise RuntimeError("APP_ENV debe ser 'development' o 'production'.")

    secret_key = values.get("SESSION_SECRET", "").strip()
    if not secret_key:
        if app_environment == "production":
            raise RuntimeError("SESSION_SECRET es obligatorio en producción.")
        secret_key = _DEVELOPMENT_SECRET
    if len(secret_key) < 32:
        raise RuntimeError("SESSION_SECRET debe tener al menos 32 caracteres.")

    return {
        "secret_key": secret_key,
        "https_only": app_environment == "production",
        "same_site": "lax",
        "max_age": _SESSION_MAX_AGE,
    }
