from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path

import pandas as pd

from dosimetry_app.config import SEED_DIR, SUPPORTED_DATASET_TYPES, UPLOAD_DIR
from dosimetry_app.database import dump_json, execute, execute_transaction, query_all, query_one
from dosimetry_app.validators import validate_dataset

DEFAULT_AFRICA_LOCATION = "Harare, Zimbabwe"


def _normalize_location_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower())
    return " ".join(normalized.split())


def _read_file_to_dataframe(file_name: str, raw_bytes: bytes) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(pd.io.common.BytesIO(raw_bytes))
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(pd.io.common.BytesIO(raw_bytes))
    raise ValueError("Only CSV and XLSX/XLS files are supported.")


def _next_dataset_version(dataset_type: str) -> int:
    row = query_one(
        """
        SELECT COALESCE(MAX(version), 0) AS max_version
        FROM datasets
        WHERE dataset_type = ?
        """,
        (dataset_type,),
    )
    return int(row["max_version"]) + 1 if row else 1


def _persist_csv(frame: pd.DataFrame, dataset_type: str, version: int) -> tuple[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    file_name = f"{dataset_type}_v{version}_{timestamp}.csv"
    target = UPLOAD_DIR / file_name
    frame.to_csv(target, index=False)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    return str(target), checksum


def _register_dataset(
    dataset_type: str,
    frame: pd.DataFrame,
    uploaded_by: str,
    notes: str | None = None,
    activate: bool = False,
) -> tuple[int, list[str]]:
    version = _next_dataset_version(dataset_type)
    errors = validate_dataset(dataset_type, frame)
    file_path, checksum = _persist_csv(frame, dataset_type, version)

    if errors:
        status = "invalid"
        validation_status = "failed"
    else:
        status = "active" if activate else "inactive"
        validation_status = "passed"

    dataset_id = execute(
        """
        INSERT INTO datasets (
            dataset_type, version, status, validation_status, validation_errors_json,
            file_path, checksum, notes, uploaded_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_type,
            version,
            status,
            validation_status,
            dump_json(errors),
            file_path,
            checksum,
            notes,
            uploaded_by,
        ),
    )

    if activate and not errors:
        activate_dataset(dataset_id)

    return dataset_id, errors


def save_uploaded_dataset(
    dataset_type: str,
    uploaded_file,
    uploaded_by: str,
    notes: str | None = None,
) -> tuple[int, list[str]]:
    raw_bytes = uploaded_file.getvalue()
    frame = _read_file_to_dataframe(uploaded_file.name, raw_bytes)
    return _register_dataset(dataset_type, frame, uploaded_by, notes=notes, activate=False)


def import_dataset_from_path(
    dataset_type: str,
    file_path: Path,
    uploaded_by: str = "system",
    notes: str | None = "Seed dataset",
    activate: bool = True,
) -> tuple[int, list[str]]:
    frame = pd.read_csv(file_path)
    return _register_dataset(dataset_type, frame, uploaded_by, notes=notes, activate=activate)


def list_datasets(dataset_type: str | None = None) -> list[dict]:
    if dataset_type:
        return query_all(
            """
            SELECT *
            FROM datasets
            WHERE dataset_type = ?
            ORDER BY dataset_type, version DESC
            """,
            (dataset_type,),
        )
    return query_all(
        """
        SELECT *
        FROM datasets
        ORDER BY dataset_type, version DESC
        """
    )


def activate_dataset(dataset_id: int) -> None:
    dataset = query_one("SELECT * FROM datasets WHERE id = ?", (dataset_id,))
    if not dataset:
        raise ValueError("Dataset not found.")
    if dataset["validation_status"] != "passed":
        raise ValueError("Only validation-passed datasets can be activated.")

    execute_transaction(
        [
            (
                "UPDATE datasets SET status = 'inactive' WHERE dataset_type = ?",
                (dataset["dataset_type"],),
            ),
            ("UPDATE datasets SET status = 'active' WHERE id = ?", (dataset_id,)),
        ]
    )


def get_active_dataset(dataset_type: str) -> tuple[dict | None, pd.DataFrame | None]:
    metadata = query_one(
        """
        SELECT *
        FROM datasets
        WHERE dataset_type = ? AND status = 'active'
        ORDER BY version DESC
        LIMIT 1
        """,
        (dataset_type,),
    )
    if not metadata:
        return None, None
    frame = pd.read_csv(metadata["file_path"])
    return metadata, frame


def get_active_dataset_versions() -> dict[str, int]:
    versions: dict[str, int] = {}
    rows = query_all(
        """
        SELECT dataset_type, version
        FROM datasets
        WHERE status = 'active'
        """
    )
    for row in rows:
        versions[row["dataset_type"]] = int(row["version"])
    return versions


def get_supported_dataset_types() -> tuple[str, ...]:
    return SUPPORTED_DATASET_TYPES


def list_available_chambers() -> list[str]:
    _, frame = get_active_dataset("chamber_defaults")
    if frame is None or frame.empty:
        return []
    values = frame["chamber_type"].astype(str).str.strip().tolist()
    return sorted(set(values))


def get_chamber_defaults(chamber_type: str) -> dict | None:
    _, frame = get_active_dataset("chamber_defaults")
    if frame is None or frame.empty:
        return None
    matched = frame[frame["chamber_type"].astype(str) == chamber_type]
    if matched.empty:
        return None
    row = matched.iloc[0].to_dict()
    return {
        "ndw_60co": float(row["ndw_60co"]),
        "rcav_cm": float(row["rcav_cm"]),
        "reference_polarity": str(row["reference_polarity"]),
    }


def list_environment_locations() -> list[str]:
    _, frame = get_active_dataset("environmental_data")
    if frame is None or frame.empty:
        return []
    values = frame["location"].astype(str).str.strip().tolist()
    unique = sorted(set(value for value in values if value), key=lambda value: value.lower())

    harare_match = [value for value in unique if _normalize_location_name(value) == _normalize_location_name(DEFAULT_AFRICA_LOCATION)]
    if harare_match:
        selected = harare_match[0]
        unique = [selected] + [value for value in unique if value != selected]
    return unique


def get_environment_from_dataset(location: str | None = None) -> dict | None:
    _, frame = get_active_dataset("environmental_data")
    if frame is None or frame.empty:
        return None

    frame = frame.copy()
    frame["location"] = frame["location"].astype(str).str.strip()
    frame["_normalized_location"] = frame["location"].map(_normalize_location_name)

    selected = None
    if location:
        input_name = str(location).strip()
        input_normalized = _normalize_location_name(input_name)

        exact = frame[frame["location"].str.casefold() == input_name.casefold()]
        if not exact.empty:
            selected = exact.iloc[0]

        if selected is None:
            normalized_exact = frame[frame["_normalized_location"] == input_normalized]
            if not normalized_exact.empty:
                selected = normalized_exact.iloc[0]

        if selected is None:
            partial = frame[frame["_normalized_location"].str.contains(input_normalized, na=False)]
            if not partial.empty:
                selected = partial.iloc[0]

        if selected is None:
            candidates = frame["_normalized_location"].dropna().tolist()
            best = get_close_matches(input_normalized, candidates, n=1, cutoff=0.72)
            if best:
                matched = frame[frame["_normalized_location"] == best[0]]
                if not matched.empty:
                    selected = matched.iloc[0]

        if selected is None:
            available = ", ".join(list_environment_locations()[:12])
            raise ValueError(
                f"Location '{location}' not found in active environmental_data dataset. "
                f"Available examples: {available}"
            )

    if selected is None:
        default_match = frame[
            frame["_normalized_location"] == _normalize_location_name(DEFAULT_AFRICA_LOCATION)
        ]
        selected = default_match.iloc[0] if not default_match.empty else frame.iloc[0]

    result = {
        "location": str(selected["location"]),
        "temperature_c": float(selected["temperature_c"]),
        "pressure_kpa": float(selected["pressure_kpa"]),
    }
    for optional_key in ("city", "country", "country_code", "latitude", "longitude", "timezone"):
        if optional_key in selected and pd.notna(selected[optional_key]):
            value = selected[optional_key]
            result[optional_key] = float(value) if optional_key in {"latitude", "longitude"} else str(value)
    return result


def ensure_africa_environment_dataset() -> None:
    seed_file = SEED_DIR / "environmental_data.csv"
    if not seed_file.exists():
        return

    metadata, frame = get_active_dataset("environmental_data")
    if metadata is None or frame is None or frame.empty:
        import_dataset_from_path(
            "environmental_data",
            seed_file,
            uploaded_by="system",
            notes="African environmental baseline seed dataset",
            activate=True,
        )
        return

    has_harare = not frame[
        frame["location"].astype(str).map(_normalize_location_name)
        == _normalize_location_name(DEFAULT_AFRICA_LOCATION)
    ].empty
    if has_harare:
        return

    if str(metadata.get("uploaded_by", "")) != "system":
        return

    import_dataset_from_path(
        "environmental_data",
        seed_file,
        uploaded_by="system",
        notes="African environmental baseline seed dataset refresh",
        activate=True,
    )


def seed_builtin_datasets() -> None:
    for dataset_type in SUPPORTED_DATASET_TYPES:
        existing = query_one(
            "SELECT id FROM datasets WHERE dataset_type = ? LIMIT 1",
            (dataset_type,),
        )
        if existing:
            continue

        seed_file = SEED_DIR / f"{dataset_type}.csv"
        if not seed_file.exists():
            continue
        import_dataset_from_path(dataset_type, seed_file, activate=True)
