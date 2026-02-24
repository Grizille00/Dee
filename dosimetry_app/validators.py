from __future__ import annotations

import pandas as pd

from dosimetry_app.config import SUPPORTED_DATASET_TYPES

DATASET_SCHEMAS: dict[str, list[str]] = {
    "kq_table": ["chamber_type", "beam_quality", "kq"],
    "pdd_table": ["energy_mv", "field_size_cm", "depth_cm", "value"],
    "tpr_table": ["energy_mv", "field_size_cm", "depth_cm", "value"],
    "chamber_defaults": ["chamber_type", "ndw_60co", "rcav_cm", "reference_polarity"],
    "environmental_data": ["location", "temperature_c", "pressure_kpa"],
}

NUMERIC_COLUMNS: dict[str, list[str]] = {
    "kq_table": ["beam_quality", "kq"],
    "pdd_table": ["energy_mv", "field_size_cm", "depth_cm", "value"],
    "tpr_table": ["energy_mv", "field_size_cm", "depth_cm", "value"],
    "chamber_defaults": ["ndw_60co", "rcav_cm"],
    "environmental_data": ["temperature_c", "pressure_kpa"],
}


def validate_dataset_type(dataset_type: str) -> str | None:
    if dataset_type not in SUPPORTED_DATASET_TYPES:
        return f"Unsupported dataset_type '{dataset_type}'."
    return None


def validate_dataset(dataset_type: str, frame: pd.DataFrame) -> list[str]:
    errors: list[str] = []

    type_error = validate_dataset_type(dataset_type)
    if type_error:
        return [type_error]

    required_columns = DATASET_SCHEMAS[dataset_type]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return errors

    frame = frame.copy()
    frame.columns = [column.strip() for column in frame.columns]

    for column in NUMERIC_COLUMNS[dataset_type]:
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.isna().any():
            errors.append(f"Column '{column}' contains non-numeric values.")
        frame[column] = converted

    if dataset_type == "kq_table" and "kq" in frame:
        if (frame["kq"] <= 0).any():
            errors.append("kq values must be > 0.")

    if dataset_type in {"pdd_table", "tpr_table"} and "value" in frame:
        if (frame["value"] <= 0).any():
            errors.append("Depth-table values must be > 0.")

    if dataset_type == "chamber_defaults":
        if (pd.to_numeric(frame["ndw_60co"], errors="coerce") <= 0).any():
            errors.append("ndw_60co values must be > 0.")

    if dataset_type == "environmental_data":
        pressure = pd.to_numeric(frame["pressure_kpa"], errors="coerce")
        if (pressure <= 0).any():
            errors.append("pressure_kpa values must be > 0.")

    if frame.empty:
        errors.append("Dataset cannot be empty.")

    return errors
