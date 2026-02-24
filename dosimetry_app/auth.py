import os

from dosimetry_app.database import execute, query_one
from dosimetry_app.security import hash_password, verify_password

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def _read_streamlit_secret(key: str) -> str | None:
    try:
        import streamlit as st
    except Exception:
        return None

    try:
        raw = st.secrets.get(key)
    except Exception:
        return None

    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _read_admin_value(
    env_key: str,
    secret_keys: tuple[str, ...],
    default: str,
) -> str:
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value

    for secret_key in secret_keys:
        secret_value = _read_streamlit_secret(secret_key)
        if secret_value:
            return secret_value
    return default


def get_bootstrap_admin_credentials() -> tuple[str, str]:
    username = _read_admin_value(
        env_key="DOSIMETRY_ADMIN_USERNAME",
        secret_keys=("admin_username", "ADMIN_USERNAME"),
        default=DEFAULT_ADMIN_USERNAME,
    )
    password = _read_admin_value(
        env_key="DOSIMETRY_ADMIN_PASSWORD",
        secret_keys=("admin_password", "ADMIN_PASSWORD"),
        default=DEFAULT_ADMIN_PASSWORD,
    )
    return username, password


def ensure_default_admin() -> None:
    username, password = get_bootstrap_admin_credentials()
    existing = query_one("SELECT id FROM users WHERE username = ?", (username,))
    if existing:
        return
    execute(
        """
        INSERT INTO users (username, password_hash, role)
        VALUES (?, ?, ?)
        """,
        (username, hash_password(password), "admin"),
    )


def create_user(username: str, password: str, role: str) -> int:
    return execute(
        """
        INSERT INTO users (username, password_hash, role)
        VALUES (?, ?, ?)
        """,
        (username, hash_password(password), role),
    )


def authenticate(username: str, password: str) -> dict | None:
    user = query_one(
        """
        SELECT id, username, password_hash, role
        FROM users
        WHERE username = ?
        """,
        (username,),
    )
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
    }
