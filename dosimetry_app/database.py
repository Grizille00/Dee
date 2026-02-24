import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dosimetry_app.config import DB_PATH


@contextmanager
def get_connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError:
        # Keep defaults when WAL mode is unavailable on the host filesystem.
        pass
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'physicist', 'viewer')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_type TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active', 'inactive', 'invalid')),
                validation_status TEXT NOT NULL CHECK(validation_status IN ('passed', 'failed')),
                validation_errors_json TEXT NOT NULL DEFAULT '[]',
                file_path TEXT NOT NULL,
                checksum TEXT NOT NULL,
                notes TEXT,
                uploaded_by TEXT NOT NULL,
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(dataset_type, version)
            );

            CREATE INDEX IF NOT EXISTS idx_datasets_type_status
            ON datasets(dataset_type, status);

            CREATE TABLE IF NOT EXISTS formulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                beam_type TEXT NOT NULL CHECK(beam_type IN ('photon', 'electron')),
                expression TEXT NOT NULL,
                variables_json TEXT NOT NULL,
                units_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL CHECK(status IN ('active', 'inactive', 'invalid')),
                validation_errors_json TEXT NOT NULL DEFAULT '[]',
                version INTEGER NOT NULL,
                notes TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, beam_type, version)
            );

            CREATE INDEX IF NOT EXISTS idx_formulas_beam_status
            ON formulas(beam_type, status);

            CREATE TABLE IF NOT EXISTS calculator_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                username TEXT NOT NULL,
                beam_type TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                outputs_json TEXT NOT NULL,
                formula_name TEXT NOT NULL,
                formula_version INTEGER NOT NULL,
                dataset_versions_json TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    with get_connection() as conn:
        cursor = conn.execute(sql, params)
        return int(cursor.lastrowid)


def execute_transaction(commands: list[tuple[str, tuple[Any, ...]]]) -> None:
    with get_connection() as conn:
        for sql, params in commands:
            conn.execute(sql, params)


def query_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True)


def load_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    return json.loads(raw)
