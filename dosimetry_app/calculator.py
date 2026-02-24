from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from dosimetry_app.config import DEFAULT_P0_KPA, DEFAULT_T0_C
from dosimetry_app.datasets import (
    get_active_dataset,
    get_active_dataset_versions,
    get_chamber_defaults,
)
from dosimetry_app.formulas import get_active_formula, safe_eval_formula


def to_coulomb(reading: float, unit: str) -> float:
    if unit == "nC":
        return reading * 1e-9
    if unit == "pC":
        return reading * 1e-12
    return reading


def compute_p_tp(
    t_meas_c: float,
    p_meas_kpa: float,
    t0_c: float = DEFAULT_T0_C,
    p0_kpa: float = DEFAULT_P0_KPA,
) -> float:
    if p_meas_kpa <= 0 or p0_kpa <= 0:
        raise ValueError("Pressure values must be > 0.")
    numerator = (273.15 + t_meas_c) * p0_kpa
    denominator = (273.15 + t0_c) * p_meas_kpa
    return numerator / denominator


def compute_p_ion_two_voltage(
    m_high: float,
    m_low: float,
    v_high: float,
    v_low: float,
) -> float:
    if any(value <= 0 for value in (m_high, m_low, v_high, v_low)):
        raise ValueError("Two-voltage inputs must be > 0.")
    if math.isclose(v_high, v_low):
        raise ValueError("v_high and v_low cannot be equal.")

    if v_high < v_low:
        v_high, v_low = v_low, v_high
        m_high, m_low = m_low, m_high

    voltage_ratio = v_high / v_low
    reading_ratio = m_high / m_low
    denominator = reading_ratio - voltage_ratio
    if math.isclose(denominator, 0.0):
        raise ValueError("Invalid two-voltage readings: denominator is zero.")
    return (1.0 - voltage_ratio) / denominator


def compute_p_pol(m_pos: float, m_neg: float, m_ref: float | None = None) -> float:
    reference = abs(m_ref) if m_ref is not None else abs(m_pos)
    if reference <= 0:
        raise ValueError("Reference polarity reading must be > 0.")
    return (abs(m_pos) + abs(m_neg)) / (2.0 * reference)


def _interpolate_by_depth(frame: pd.DataFrame, depth_cm: float) -> float:
    sorted_frame = frame.sort_values("depth_cm")
    x = sorted_frame["depth_cm"].astype(float).to_numpy()
    y = sorted_frame["value"].astype(float).to_numpy()
    if depth_cm < x.min() or depth_cm > x.max():
        raise ValueError("Depth is outside dataset range; extrapolation is disabled.")
    return float(np.interp(depth_cm, x, y))


def _nearest_column_value(values: pd.Series, target: float) -> float:
    unique_values = sorted(float(value) for value in set(values.astype(float).tolist()))
    return min(unique_values, key=lambda value: abs(value - target))


def lookup_k_q(chamber_type: str, beam_quality: float, kq_frame: pd.DataFrame) -> float:
    frame = kq_frame.copy()
    frame["beam_quality"] = pd.to_numeric(frame["beam_quality"], errors="coerce")
    frame["kq"] = pd.to_numeric(frame["kq"], errors="coerce")
    frame = frame.dropna(subset=["beam_quality", "kq"])
    frame = frame[frame["chamber_type"].astype(str) == str(chamber_type)]
    if frame.empty:
        raise ValueError(f"No kQ rows found for chamber '{chamber_type}'.")

    frame = frame.sort_values("beam_quality")
    x = frame["beam_quality"].to_numpy(dtype=float)
    y = frame["kq"].to_numpy(dtype=float)
    if beam_quality < float(x.min()) or beam_quality > float(x.max()):
        raise ValueError("Beam quality is outside kQ table range.")
    return float(np.interp(beam_quality, x, y))


def lookup_depth_factor(
    geometry_mode: str,
    depth_cm: float,
    d_ref_cm: float,
    energy_mv: float,
    field_size_cm: float,
) -> float:
    dataset_type = "pdd_table" if geometry_mode == "SSD" else "tpr_table"
    _, frame = get_active_dataset(dataset_type)
    if frame is None or frame.empty:
        return 1.0

    numeric_columns = ["energy_mv", "field_size_cm", "depth_cm", "value"]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=numeric_columns)

    nearest_energy = _nearest_column_value(frame["energy_mv"], energy_mv)
    energy_slice = frame[frame["energy_mv"] == nearest_energy]

    nearest_field = _nearest_column_value(energy_slice["field_size_cm"], field_size_cm)
    table_slice = energy_slice[energy_slice["field_size_cm"] == nearest_field]
    if table_slice.empty:
        return 1.0

    value_depth = _interpolate_by_depth(table_slice, depth_cm)
    value_ref = _interpolate_by_depth(table_slice, d_ref_cm)
    if value_ref == 0:
        raise ValueError("Reference depth value is zero; cannot compute depth factor.")
    return value_depth / value_ref


def calculate_dose(inputs: dict[str, Any]) -> dict[str, Any]:
    beam_type = str(inputs["beam_type"])
    if beam_type not in {"photon", "electron"}:
        raise ValueError("beam_type must be photon or electron.")

    chamber_type = str(inputs["chamber_type"])
    chamber_defaults = get_chamber_defaults(chamber_type) or {}

    m_raw = float(inputs["M_raw"])
    mu_meas = float(inputs["MU_meas"])
    reading_unit = str(inputs.get("reading_unit", "nC"))
    m_raw_c = to_coulomb(m_raw, reading_unit)

    t_meas = float(inputs.get("T_meas_C", DEFAULT_T0_C))
    p_meas = float(inputs.get("P_meas_kPa", DEFAULT_P0_KPA))
    t0 = float(inputs.get("T0_C", DEFAULT_T0_C))
    p0 = float(inputs.get("P0_kPa", DEFAULT_P0_KPA))

    p_tp = (
        float(inputs["P_TP_manual"])
        if inputs.get("use_manual_p_tp")
        else compute_p_tp(t_meas, p_meas, t0_c=t0, p0_kpa=p0)
    )

    p_ion = (
        float(inputs["P_ion_manual"])
        if inputs.get("use_manual_p_ion")
        else compute_p_ion_two_voltage(
            float(inputs["M_high"]),
            float(inputs["M_low"]),
            float(inputs["V_high"]),
            float(inputs["V_low"]),
        )
    )

    m_pos = float(inputs.get("M_pos", m_raw))
    m_neg = float(inputs.get("M_neg", m_raw))
    m_ref = inputs.get("M_ref")
    p_pol = (
        float(inputs["P_pol_manual"])
        if inputs.get("use_manual_p_pol")
        else compute_p_pol(m_pos, m_neg, float(m_ref) if m_ref is not None else None)
    )

    p_elec = float(inputs.get("P_elec", 1.0))
    m_q = m_raw_c * p_tp * p_ion * p_pol * p_elec

    ndw = (
        float(inputs["N_Dw_60Co"])
        if inputs.get("N_Dw_60Co") is not None
        else float(chamber_defaults.get("ndw_60co", 0.0))
    )
    if ndw <= 0:
        raise ValueError("N_Dw_60Co must be provided or available in chamber defaults.")

    beam_quality = float(inputs.get("beam_quality", 0.0))
    _, kq_frame = get_active_dataset("kq_table")
    if kq_frame is None or kq_frame.empty:
        raise ValueError("Active kq_table dataset is required.")

    k_q = (
        float(inputs["k_Q_manual"])
        if inputs.get("use_manual_k_q")
        else lookup_k_q(chamber_type, beam_quality, kq_frame)
    )

    geometry_mode = str(inputs.get("geometry_mode", "SSD"))
    depth_cm = float(inputs.get("depth_cm", 10.0))
    d_ref_cm = float(inputs.get("d_ref_cm", 10.0))
    energy_mv = float(inputs.get("energy_mv", 6.0))
    field_size_cm = float(inputs.get("field_size_cm", 10.0))

    depth_factor = (
        float(inputs["depth_factor_manual"])
        if inputs.get("use_manual_depth_factor")
        else lookup_depth_factor(
            geometry_mode=geometry_mode,
            depth_cm=depth_cm,
            d_ref_cm=d_ref_cm,
            energy_mv=energy_mv,
            field_size_cm=field_size_cm,
        )
    )

    formula = get_active_formula(beam_type)
    if not formula:
        raise ValueError(f"No active formula for beam type '{beam_type}'.")

    variables = {
        "M_raw_C": m_raw_c,
        "M_Q": m_q,
        "P_TP": p_tp,
        "P_ion": p_ion,
        "P_pol": p_pol,
        "P_elec": p_elec,
        "N_Dw_60Co": ndw,
        "k_Q": k_q,
        "depth_factor": depth_factor,
        "k_ecal": float(inputs.get("k_ecal", 1.0)),
        "k_R50": float(inputs.get("k_R50", 1.0)),
        "P_Q_gr": float(inputs.get("P_Q_gr", 1.0)),
        "MU_meas": mu_meas,
    }

    dose_per_measurement = safe_eval_formula(formula["expression"], variables)
    dose_per_100mu = dose_per_measurement * (100.0 / mu_meas)

    dataset_versions = get_active_dataset_versions()

    return {
        "beam_type": beam_type,
        "geometry_mode": geometry_mode,
        "formula_name": formula["name"],
        "formula_version": int(formula["version"]),
        "formula_expression": formula["expression"],
        "dataset_versions": dataset_versions,
        "intermediate": {
            "M_raw_C": m_raw_c,
            "P_TP": p_tp,
            "P_ion": p_ion,
            "P_pol": p_pol,
            "P_elec": p_elec,
            "M_Q": m_q,
            "N_Dw_60Co": ndw,
            "k_Q": k_q,
            "depth_factor": depth_factor,
        },
        "outputs": {
            "dose_per_measurement_gy": dose_per_measurement,
            "dose_per_100mu_gy": dose_per_100mu,
        },
    }

