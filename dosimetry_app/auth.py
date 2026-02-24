from dosimetry_app.database import execute, query_one
from dosimetry_app.security import hash_password, verify_password

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def ensure_default_admin() -> None:
    existing = query_one("SELECT id FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,))
    if existing:
        return
    execute(
        """
        INSERT INTO users (username, password_hash, role)
        VALUES (?, ?, ?)
        """,
        (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD), "admin"),
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

