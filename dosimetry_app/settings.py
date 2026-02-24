from __future__ import annotations

from dosimetry_app.database import execute_transaction, query_all, query_one

ENV_SOURCE_MANUAL = "Manual"
ENV_SOURCE_DATASET = "Dataset"
ENV_SOURCE_AUTO = "Auto (IP + Weather API)"
HARARE_LOCATION = "Harare, Zimbabwe"

DEFAULT_SETTINGS = {
    "env_source": ENV_SOURCE_AUTO,
    "env_manual_temperature_c": "22.0",
    "env_manual_pressure_kpa": "85.9",
    "env_dataset_location": "",
}

LEGACY_DEFAULT_SETTINGS = {
    "env_source": ENV_SOURCE_MANUAL,
    "env_manual_temperature_c": "20.6",
    "env_manual_pressure_kpa": "98.18",
    "env_dataset_location": "",
}

LEGACY_HARARE_DEFAULT_SETTINGS = {
    "env_source": ENV_SOURCE_DATASET,
    "env_manual_temperature_c": "22.0",
    "env_manual_pressure_kpa": "85.9",
    "env_dataset_location": HARARE_LOCATION,
}


def _safe_float(value: str | None, fallback: float) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def ensure_default_settings() -> None:
    commands: list[tuple[str, tuple[str, str]]] = []
    for key, value in DEFAULT_SETTINGS.items():
        existing = query_one("SELECT key FROM app_settings WHERE key = ?", (key,))
        if existing:
            continue
        commands.append(
            (
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                """,
                (key, value),
            )
        )
    if commands:
        execute_transaction(commands)


def apply_live_detection_defaults_for_legacy_installations() -> None:
    current_source = get_setting("env_source")
    current_location = get_setting("env_dataset_location")
    current_temp = _safe_float(get_setting("env_manual_temperature_c"), 20.6)
    current_pressure = _safe_float(get_setting("env_manual_pressure_kpa"), 98.18)

    legacy_manual_match = (
        current_source in {None, LEGACY_DEFAULT_SETTINGS["env_source"]}
        and (current_location or "").strip() == LEGACY_DEFAULT_SETTINGS["env_dataset_location"]
        and abs(current_temp - float(LEGACY_DEFAULT_SETTINGS["env_manual_temperature_c"])) < 0.0001
        and abs(current_pressure - float(LEGACY_DEFAULT_SETTINGS["env_manual_pressure_kpa"])) < 0.0001
    )

    legacy_harare_match = (
        current_source == LEGACY_HARARE_DEFAULT_SETTINGS["env_source"]
        and (current_location or "").strip() == LEGACY_HARARE_DEFAULT_SETTINGS["env_dataset_location"]
        and abs(current_temp - float(LEGACY_HARARE_DEFAULT_SETTINGS["env_manual_temperature_c"])) < 0.0001
        and abs(current_pressure - float(LEGACY_HARARE_DEFAULT_SETTINGS["env_manual_pressure_kpa"])) < 0.0001
    )

    if legacy_manual_match or legacy_harare_match:
        save_environment_settings(
            env_source=DEFAULT_SETTINGS["env_source"],
            env_manual_temperature_c=float(DEFAULT_SETTINGS["env_manual_temperature_c"]),
            env_manual_pressure_kpa=float(DEFAULT_SETTINGS["env_manual_pressure_kpa"]),
            env_dataset_location=DEFAULT_SETTINGS["env_dataset_location"],
        )


def get_setting(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM app_settings WHERE key = ?", (key,))
    if row:
        return str(row["value"])
    return default


def set_setting(key: str, value: str) -> None:
    execute_transaction(
        [
            (
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
        ]
    )


def list_settings() -> dict[str, str]:
    rows = query_all("SELECT key, value FROM app_settings")
    return {str(row["key"]): str(row["value"]) for row in rows}


def get_environment_settings() -> dict[str, str | float]:
    source = get_setting("env_source", DEFAULT_SETTINGS["env_source"]) or DEFAULT_SETTINGS["env_source"]
    manual_t = float(
        get_setting("env_manual_temperature_c", DEFAULT_SETTINGS["env_manual_temperature_c"])
        or DEFAULT_SETTINGS["env_manual_temperature_c"]
    )
    manual_p = float(
        get_setting("env_manual_pressure_kpa", DEFAULT_SETTINGS["env_manual_pressure_kpa"])
        or DEFAULT_SETTINGS["env_manual_pressure_kpa"]
    )
    dataset_location = get_setting("env_dataset_location", DEFAULT_SETTINGS["env_dataset_location"]) or ""

    return {
        "env_source": source,
        "env_manual_temperature_c": manual_t,
        "env_manual_pressure_kpa": manual_p,
        "env_dataset_location": dataset_location,
    }


def save_environment_settings(
    env_source: str,
    env_manual_temperature_c: float,
    env_manual_pressure_kpa: float,
    env_dataset_location: str,
) -> None:
    commands = [
        (
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("env_source", str(env_source)),
        ),
        (
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("env_manual_temperature_c", str(env_manual_temperature_c)),
        ),
        (
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("env_manual_pressure_kpa", str(env_manual_pressure_kpa)),
        ),
        (
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("env_dataset_location", env_dataset_location),
        ),
    ]
    execute_transaction(commands)
