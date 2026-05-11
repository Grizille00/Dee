from datetime import datetime
from html import escape as html_escape
import json
import csv
import io

import streamlit as st
from typing import Any

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:  # pragma: no cover - optional runtime dependency
    streamlit_js_eval = None

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.calculator import calculate_dose
from dosimetry_app.datasets import (
    get_chamber_defaults,
    get_environment_from_dataset,
    list_available_chambers,
)
from dosimetry_app.runs import record_run
from dosimetry_app.config import DEFAULT_P0_KPA, DEFAULT_T0_C
from dosimetry_app.settings import (
    ENV_SOURCE_AUTO,
    ENV_SOURCE_DATASET,
    ENV_SOURCE_MANUAL,
    KTP_SOURCE_AUTO_AUTO,
    KTP_SOURCE_AUTO_MANUAL,
    KTP_SOURCE_MANUAL,
    get_environment_settings,
)
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state
from dosimetry_app.weather import (
    fetch_current_environment,
    reverse_geocode_coordinates,
)

initialize_application()
apply_theme()
init_session_state()


GEOLOCATION_JS_EXPRESSION = """
(async () => {
  const reverseGeocodeInBrowser = async (latitude, longitude) => {
    try {
      const endpoint = "https://api.bigdatacloud.net/data/reverse-geocode-client";
      const params = new URLSearchParams({
        latitude: String(latitude),
        longitude: String(longitude),
        localityLanguage: "en"
      });
      const response = await fetch(`${endpoint}?${params.toString()}`, { method: "GET" });
      if (!response.ok) {
        return {};
      }
      const payload = await response.json();
      const city =
        payload.city ||
        payload.locality ||
        payload.principalSubdivision ||
        "";
      const country = payload.countryName || "";
      const countryCode = payload.countryCode || "";
      const parts = [city, country].filter(Boolean);
      return {
        city,
        country,
        country_code: countryCode,
        location_label: parts.length ? parts.join(", ") : ""
      };
    } catch (err) {
      return {};
    }
  };

  if (!navigator.geolocation) {
    return {
      status: "error",
      code: "geolocation_not_supported",
      message: "Browser geolocation is not supported."
    };
  }

  let permissionState = "unknown";
  if (navigator.permissions && navigator.permissions.query) {
    try {
      const permission = await navigator.permissions.query({ name: "geolocation" });
      permissionState = permission.state;
    } catch (err) {
      permissionState = "unknown";
    }
  }

  return await new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const reverseGeo = await reverseGeocodeInBrowser(
          position.coords.latitude,
          position.coords.longitude
        );
        resolve({
          status: "success",
          permission_state: permissionState,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy_m: position.coords.accuracy,
          timestamp: position.timestamp,
          city: reverseGeo.city || "",
          country: reverseGeo.country || "",
          country_code: reverseGeo.country_code || "",
          location_label: reverseGeo.location_label || ""
        });
      },
      (error) =>
        resolve({
          status: "error",
          permission_state: permissionState,
          code: error.code || null,
          message: error.message || "permission_denied"
        }),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  });
})()
"""


def _ensure_local_state() -> None:
    st.session_state.setdefault("live_environment_override", None)
    st.session_state.setdefault("browser_geo_error", "")
    st.session_state.setdefault("browser_geo_notice", "")
    st.session_state.setdefault("browser_geo_attempted", False)
    st.session_state.setdefault("browser_geo_pending", True)
    st.session_state.setdefault("browser_geo_request_token", 1)
    st.session_state.setdefault("browser_geo_processed_token", 0)
    st.session_state.setdefault("browser_geo_last_update", "")
    st.session_state.setdefault("auto_environment_warmup_done", False)


def _trigger_browser_location_request() -> None:
    current_token = int(st.session_state.get("browser_geo_request_token", 1))
    st.session_state["browser_geo_request_token"] = current_token + 1
    st.session_state["browser_geo_pending"] = True
    st.session_state["browser_geo_attempted"] = True
    st.session_state["browser_geo_notice"] = ""
    st.session_state["browser_geo_error"] = ""


def _extract_component_payload(raw_payload: object) -> dict | None:
    if raw_payload is None:
        return None
    if isinstance(raw_payload, dict):
        if "value" in raw_payload and "dataType" in raw_payload:
            value = raw_payload.get("value")
            return value if isinstance(value, dict) else None
        return raw_payload
    return None


def _ingest_browser_geolocation_payload() -> None:
    request_token = int(st.session_state.get("browser_geo_request_token", 1))
    processed_token = int(st.session_state.get("browser_geo_processed_token", 0))
    if request_token <= processed_token:
        return

    if streamlit_js_eval is None:
        st.session_state["browser_geo_processed_token"] = request_token
        st.session_state["browser_geo_pending"] = False
        st.session_state["browser_geo_error"] = (
            "Browser location is unavailable because `streamlit-js-eval` is not installed."
        )
        st.session_state["browser_geo_notice"] = ""
        st.session_state["browser_geo_attempted"] = True
        return

    raw_payload = streamlit_js_eval(
        js_expressions=GEOLOCATION_JS_EXPRESSION,
        key=f"browser_geolocation_{request_token}",
    )
    payload = _extract_component_payload(raw_payload)
    if not payload:
        return

    st.session_state["browser_geo_processed_token"] = request_token
    st.session_state["browser_geo_pending"] = False
    st.session_state["browser_geo_attempted"] = True

    status = str(payload.get("status", "")).lower()
    if status != "success":
        message = str(payload.get("message") or "Permission denied or unavailable.")
        st.session_state["browser_geo_error"] = f"Browser location unavailable: {message}"
        st.session_state["browser_geo_notice"] = ""
        st.rerun()
        return

    try:
        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
    except Exception:
        st.session_state["browser_geo_error"] = "Browser location payload is invalid."
        st.session_state["browser_geo_notice"] = ""
        st.rerun()
        return

    try:
        weather = fetch_current_environment(latitude=latitude, longitude=longitude)
    except Exception:
        st.session_state["browser_geo_error"] = (
            "Location detected, but live weather service could not be reached. Please refresh."
        )
        st.session_state["browser_geo_notice"] = ""
        st.rerun()
        return

    location_label = str(payload.get("location_label", "")).strip() or "Location detected"
    city = str(payload.get("city", "")).strip()
    country = str(payload.get("country", "")).strip()
    country_code = str(payload.get("country_code", "")).strip()

    if not city or not country:
        try:
            reverse_geo = reverse_geocode_coordinates(latitude=latitude, longitude=longitude)
            if reverse_geo.get("location_label"):
                location_label = str(reverse_geo["location_label"])
            city = str(reverse_geo.get("city", "")).strip() or city
            country = str(reverse_geo.get("country", "")).strip() or country
            country_code = str(reverse_geo.get("country_code", "")).strip() or country_code
        except Exception:
            # Keep browser coordinates and continue without city/country enrichment.
            pass

    if city and country:
        location_label = f"{city}, {country}"
    elif city:
        location_label = city
    elif country:
        location_label = country

    environment = {
        "source": "browser_geolocation",
        "location": location_label,
        "latitude": latitude,
        "longitude": longitude,
        "city": city,
        "country": country,
        "country_code": country_code,
        "temperature_c": float(weather["temperature_c"]),
        "pressure_kpa": float(weather["pressure_kpa"]),
        "provider": {
            "geolocation": "browser navigator.geolocation",
            "weather": "open-meteo.com",
        },
    }
    st.session_state["live_environment_override"] = environment
    st.session_state["browser_geo_error"] = ""
    st.session_state["browser_geo_notice"] = "Location and weather updated."
    st.session_state["browser_geo_last_update"] = datetime.now().strftime("%H:%M:%S")

    st.rerun()


def _header_environment_snapshot(env_settings: dict) -> tuple[str, float | None, float | None]:
    source = str(env_settings["env_source"])
    if source == ENV_SOURCE_MANUAL:
        source = ENV_SOURCE_AUTO
    configured_location = str(env_settings["env_dataset_location"]) or None
    live_override = st.session_state.get("live_environment_override")

    if source == ENV_SOURCE_AUTO:
        if live_override:
            city = str(live_override.get("city", "")).strip()
            country = str(live_override.get("country", "")).strip()
            if city and country:
                location_label = f"{city}, {country}"
            elif city:
                location_label = city
            elif country:
                location_label = country
            else:
                location_label = str(live_override.get("location", "Current location"))
            return (
                location_label,
                float(live_override.get("temperature_c")) if live_override.get("temperature_c") is not None else None,
                float(live_override.get("pressure_kpa")) if live_override.get("pressure_kpa") is not None else None,
            )
        return "Waiting for browser location...", None, None

    if source == ENV_SOURCE_DATASET:
        try:
            env_row = get_environment_from_dataset(configured_location)
            if env_row:
                return (
                    str(env_row["location"]),
                    float(env_row["temperature_c"]),
                    float(env_row["pressure_kpa"]),
                )
        except Exception:
            pass
        return "Dataset location unavailable", None, None

    return "Configured fallback", None, None


def _header_status_text(env_settings: dict) -> str:
    source = str(env_settings["env_source"])
    if source == ENV_SOURCE_MANUAL:
        source = ENV_SOURCE_AUTO
    if source == ENV_SOURCE_AUTO:
        live_override = st.session_state.get("live_environment_override") or {}
        if live_override:
            last_update = str(st.session_state.get("browser_geo_last_update") or "")
            if str(live_override.get("source")) == "browser_geolocation":
                if last_update:
                    return f"Live location in use. Updated {last_update}."
                return "Live location in use."
            return "Using live weather data."
        if st.session_state.get("browser_geo_pending"):
            return "Requesting browser location permission..."
        return "Waiting for location permission."

    if source == ENV_SOURCE_DATASET:
        return "Using dataset environmental values."

    return "Using fallback environmental values."


def _resolve_environment(env_settings: dict) -> tuple[str, float, float, dict]:
    environmental_source = str(env_settings["env_source"])
    configured_location = str(env_settings["env_dataset_location"]) or None
    live_override = st.session_state.get("live_environment_override")

    # Legacy manual mode is treated as auto so calculations always use fetched values.
    if environmental_source == ENV_SOURCE_MANUAL:
        environmental_source = ENV_SOURCE_AUTO

    if environmental_source == ENV_SOURCE_DATASET:
        env_row = get_environment_from_dataset(configured_location)
        if not env_row:
            raise ValueError("No active environmental_data dataset values available.")
        t_meas_c = float(env_row["temperature_c"])
        p_meas_kpa = float(env_row["pressure_kpa"])
        environment_details = {
            "source": ENV_SOURCE_DATASET,
            "location": env_row["location"],
            "temperature_c": t_meas_c,
            "pressure_kpa": p_meas_kpa,
        }
        return environmental_source, t_meas_c, p_meas_kpa, environment_details

    if environmental_source == ENV_SOURCE_AUTO:
        if live_override and live_override.get("temperature_c") is not None and live_override.get("pressure_kpa") is not None:
            t_meas_c = float(live_override["temperature_c"])
            p_meas_kpa = float(live_override["pressure_kpa"])
            environment_details = dict(live_override)
            environment_details["override_used"] = True
            return environmental_source, t_meas_c, p_meas_kpa, environment_details

        raise ValueError(
            "Browser location weather data is unavailable. Allow location permission and press Use My Location."
        )

    raise ValueError("Unsupported environmental source configuration.")


def _flatten_details(payload: object, prefix: str = "") -> list[tuple[str, object]]:
    if isinstance(payload, dict):
        flattened: list[tuple[str, object]] = []
        for key, value in payload.items():
            key_str = str(key)
            qualified_key = f"{prefix}.{key_str}" if prefix else key_str
            if isinstance(value, dict):
                flattened.extend(_flatten_details(value, qualified_key))
            else:
                flattened.append((qualified_key, value))
        return flattened
    return [(prefix or "value", payload)]


def _detail_value_text(value: object) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        if value != 0 and (abs(value) >= 10000 or abs(value) < 0.001):
            return f"{value:.6e}"
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        preview = ", ".join(_detail_value_text(item) for item in values[:5])
        return f"{preview} ..." if len(values) > 5 else preview
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def _build_calculation_summary(
    inputs: dict[str, Any],
    result: dict[str, Any],
    environment_details: dict[str, Any],
) -> tuple[str, str]:
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["Category", "Field", "Value"])

    def write_section(section_name: str, section: dict[str, Any]) -> None:
        for key, value in section.items():
            if key == "environmental_details":
                continue
            writer.writerow([section_name, key, _detail_value_text(value)])

    write_section("Inputs", inputs)
    write_section("Intermediate", result.get("intermediate", {}))
    write_section("Outputs", result.get("outputs", {}))
    write_section("Environment", environment_details)

    lines = [
        "Calculation Summary",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Inputs:",
    ]
    for key, value in inputs.items():
        if key == "environmental_details":
            continue
        lines.append(f"{key}: {_detail_value_text(value)}")
    lines.extend(["", "Intermediate Values:"])
    for key, value in result.get("intermediate", {}).items():
        lines.append(f"{key}: {_detail_value_text(value)}")
    lines.extend(["", "Outputs:"])
    for key, value in result.get("outputs", {}).items():
        lines.append(f"{key}: {_detail_value_text(value)}")
    lines.extend(["", "Environment:"])
    for key, value in environment_details.items():
        lines.append(f"{key}: {_detail_value_text(value)}")

    return csv_buffer.getvalue(), "\n".join(lines)


def _render_detail_cards(payload: object, columns: int = 3) -> None:
    items = _flatten_details(payload)
    if not items:
        st.caption("No details available.")
        return

    column_count = max(1, columns)
    card_columns = st.columns(column_count)
    for index, (label, value) in enumerate(items):
        with card_columns[index % column_count]:
            st.markdown(
                f"""
                <div class="detail-card">
                  <div class="detail-label">{html_escape(label)}</div>
                  <div class="detail-value">{html_escape(_detail_value_text(value))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _environment_details_for_display(details: dict) -> dict:
    payload = dict(details)
    payload.pop("source", None)
    payload.pop("country_code", None)
    placeholder_values = {
        "",
        "current location",
        "detecting current location...",
        "location detected",
        "unknown location",
    }

    def _is_placeholder_location(value: object) -> bool:
        return str(value).strip().lower() in placeholder_values

    provider = payload.get("provider")
    if isinstance(provider, dict):
        provider_filtered = {
            key: value
            for key, value in provider.items()
            if str(key) not in {"geolocation", "weather"}
        }
        if provider_filtered:
            payload["provider"] = provider_filtered
        else:
            payload.pop("provider", None)

    city = str(payload.get("city", "")).strip()
    country = str(payload.get("country", "")).strip()
    if _is_placeholder_location(city):
        city = ""
    if _is_placeholder_location(country):
        country = ""

    location = str(payload.get("location", "")).strip()
    if not city or not country:
        if location and not _is_placeholder_location(location):
            parts = [part.strip() for part in location.split(",") if part.strip()]
            if not city and parts:
                city = parts[0]
            if not country and len(parts) >= 2:
                country = parts[-1]

    if city:
        payload["city"] = city
    else:
        payload.pop("city", None)
    if country:
        payload["country"] = country
    else:
        payload.pop("country", None)

    if _is_placeholder_location(location):
        if city and country:
            payload["location"] = f"{city}, {country}"
        elif city:
            payload["location"] = city
        elif country:
            payload["location"] = country
        else:
            payload.pop("location", None)

    return payload


_ensure_local_state()
env_settings = get_environment_settings()
admin_env_source = str(env_settings["env_source"])
if admin_env_source == ENV_SOURCE_MANUAL:
    admin_env_source = ENV_SOURCE_AUTO
if admin_env_source == ENV_SOURCE_AUTO:
    _ingest_browser_geolocation_payload()

header_location, header_temp, header_pressure = _header_environment_snapshot(env_settings)
header_status = _header_status_text(env_settings)
header_temp_label = f"{header_temp:.1f} C" if header_temp is not None else "--"
header_pressure_label = f"{header_pressure:.1f} kPa" if header_pressure is not None else "--"

top_left, top_mid, top_right = st.columns([1.2, 2.6, 1.2])
with top_left:
    if st.button("Open Admin Portal", key="open_admin_portal", use_container_width=True):
        st.switch_page("pages/9_Admin_Portal.py")
with top_mid:
    st.markdown(
        f"""
        <div class="env-header">
          <div class="env-header-item"><strong>Location</strong><span>{header_location}</span></div>
          <div class="env-header-item"><strong>Temperature</strong><span>{header_temp_label}</span></div>
          <div class="env-header-item"><strong>Pressure</strong><span>{header_pressure_label}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(header_status)
with top_right:
    if admin_env_source == ENV_SOURCE_AUTO:
        if st.button("Use My Location", key="use_my_location", use_container_width=True):
            _trigger_browser_location_request()
            st.rerun()
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        user = st.session_state["user"]
        st.caption(f"Signed in as `{user['username']}` ({user['role']})")
    else:
        st.caption("Public calculator mode")

chambers = list_available_chambers()
if not chambers:
    st.error("No chamber defaults are active. Upload/activate `chamber_defaults` dataset first.")
    st.stop()

st.markdown(
    """
    <div class="hero-box">
      <div class="hero-title">Universal Absorbed Calculation System</div>
      <div class="hero-subtitle">
        Fill core values, click calculate, and review results below.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if admin_env_source == ENV_SOURCE_AUTO:
    if st.session_state.get("browser_geo_pending"):
        st.info("Waiting for browser location permission...")
    elif not st.session_state.get("browser_geo_attempted") and not st.session_state.get("live_environment_override"):
        st.info("Use `Use My Location` to refresh live temperature and pressure.")
    if st.session_state.get("browser_geo_error"):
        st.warning(str(st.session_state["browser_geo_error"]))
    if st.session_state.get("browser_geo_notice"):
        st.success(str(st.session_state["browser_geo_notice"]))

protocol_tabs = st.tabs(["TRS398", "TG51"])

with protocol_tabs[0]:
    protocol_mode = "TRS398"
    with st.container():
        st.markdown("### TRS-398 Calculation Mode")

        admin_env_settings = get_environment_settings()
        ktp_source_options = [
            KTP_SOURCE_AUTO_AUTO,
            KTP_SOURCE_AUTO_MANUAL,
            KTP_SOURCE_MANUAL,
        ]
        ktp_source_default = admin_env_settings.get("ktp_source", KTP_SOURCE_AUTO_AUTO)
        ktp_source_index = (
            ktp_source_options.index(ktp_source_default)
            if ktp_source_default in ktp_source_options
            else 0
        )

        ktp_source = st.radio(
            "Select KTP Source",
            options=ktp_source_options,
            index=ktp_source_index,
            horizontal=True,
            key="trs_ktp_source",
        )

        manual_temperature_c = None
        manual_pressure_kpa = None
        if ktp_source == KTP_SOURCE_AUTO_MANUAL:
            with st.expander("Manual Weather Inputs", expanded=True):
                w1, w2 = st.columns(2)
                with w1:
                    manual_temperature_c = st.number_input(
                        "Manual Temperature (C)",
                        min_value=-50.0,
                        value=22.0,
                        step=0.1,
                        format="%.1f",
                        key="trs_manual_temperature_c",
                    )
                with w2:
                    manual_pressure_kpa = st.number_input(
                        "Manual Pressure (kPa)",
                        min_value=0.1,
                        value=101.325,
                        step=0.1,
                        format="%.3f",
                        key="trs_manual_pressure_kpa",
                    )
        elif ktp_source == KTP_SOURCE_MANUAL:
            st.markdown("**Manual Temperature and Pressure Entry**")
            w1, w2 = st.columns(2)
            with w1:
                manual_temperature_c = st.number_input(
                    "Temperature (C)",
                    min_value=-50.0,
                    value=22.0,
                    step=0.1,
                    format="%.1f",
                    key="trs_manual_temperature_c",
                )
            with w2:
                manual_pressure_kpa = st.number_input(
                    "Pressure (kPa)",
                    min_value=0.1,
                    value=101.325,
                    step=0.1,
                    format="%.3f",
                    key="trs_manual_pressure_kpa",
                )

        st.markdown("### Core Inputs")
        c1, c2 = st.columns(2)
        with c1:
            beam_type = st.selectbox("Beam Type", ["photon", "electron"], key="trs_beam_type")
            chamber_type = st.selectbox("Chamber Type", chambers, key="trs_chamber_type")
            geometry_mode = st.selectbox("Geometry Mode", ["SSD", "SAD"], key="trs_geometry_mode")
            reading_unit = st.selectbox("Reading Unit", ["nC", "C", "pC"], key="trs_reading_unit")
        with c2:
            energy_mv = st.number_input(
                "Energy (MV)", min_value=1.0, value=15.0, step=0.5, key="trs_energy_mv"
            )
            field_size_cm = st.number_input(
                "Field Size (cm)", min_value=1.0, value=10.0, step=0.5, key="trs_field_size_cm"
            )
            depth_cm = st.number_input(
                "Depth (cm)", min_value=0.1, value=10.0, step=0.1, key="trs_depth_cm"
            )
            d_ref_cm = st.number_input(
                "Reference Depth (cm)", min_value=0.1, value=10.0, step=0.1, key="trs_d_ref_cm"
            )

        c3, c4 = st.columns(2)
        with c3:
            manual_kq_selected = bool(st.session_state.get("trs_use_manual_k_q", False))
            tpr_20_10 = st.number_input(
                "TPR20,10",
                min_value=0.0,
                value=0.730,
                step=0.001,
                format="%.3f",
                key="trs_tpr_20_10",
                disabled=manual_kq_selected,
            )
            if manual_kq_selected:
                st.caption("Manual k_Q selected: TPR20,10 does not affect k_Q fitting.")
            m_raw = st.number_input(
                "Raw Reading",
                min_value=0.000001,
                value=7.674,
                format="%.7f",
                key="trs_m_raw",
            )
        with c4:
            mu_meas = st.number_input(
                "MU Measured",
                min_value=0.01,
                value=50.0,
                step=1.0,
                key="trs_mu_meas",
            )
            p_elec = st.number_input(
                "k_elec",
                min_value=0.5,
                value=1.0,
                step=0.001,
                format="%.4f",
                key="trs_p_elec",
            )

        chamber_defaults_values = get_chamber_defaults(chamber_type) or {}
        if chamber_defaults_values:
            r_cav_cm = chamber_defaults_values.get("r_cav", chamber_defaults_values.get("rcav_cm"))
            details = (
                f"**Selected chamber defaults (TRS-398 fitting parameters):** "
                f"N_Dw_60Co ≈ {chamber_defaults_values['ndw_60co']:.4e}, "
                f"r_cav ≈ {r_cav_cm:.3f} cm"
            )
            if "a" in chamber_defaults_values and "b" in chamber_defaults_values:
                details += f", a ≈ {chamber_defaults_values['a']:.5f}, b ≈ {chamber_defaults_values['b']:.5f}"
            st.markdown(details)

        with st.expander("Advanced Inputs (optional)", expanded=False):
            r1, r2 = st.columns(2)
            with r1:
                t0_c = st.number_input(
                    "Reference Temperature T0 (C)",
                    value=22.0,
                    step=0.1,
                    key="trs_t0_c",
                )
                m_high = st.number_input(
                    "M_high",
                    min_value=0.000001,
                    value=7.674,
                    format="%.6f",
                    key="trs_m_high",
                )
                m_low = st.number_input(
                    "M_low",
                    min_value=0.000001,
                    value=7.630,
                    format="%.6f",
                    key="trs_m_low",
                )
                m_pos = st.number_input(
                    "M_pos",
                    min_value=0.000001,
                    value=7.674,
                    format="%.6f",
                    key="trs_m_pos",
                )
                m_neg = st.number_input(
                    "M_neg",
                    min_value=0.000001,
                    value=7.660,
                    format="%.6f",
                    key="trs_m_neg",
                )
            with r2:
                p0_kpa = st.number_input(
                    "Reference Pressure P0 (kPa)",
                    value=101.325,
                    step=0.01,
                    key="trs_p0_kpa",
                )
                v_high = st.number_input(
                    "V_high (V)",
                    min_value=1.0,
                    value=300.0,
                    step=1.0,
                    key="trs_v_high",
                )
                v_low = st.number_input(
                    "V_low (V)",
                    min_value=1.0,
                    value=150.0,
                    step=1.0,
                    key="trs_v_low",
                )
                use_custom_m_ref = st.checkbox("Use custom M_ref", key="trs_use_custom_m_ref")
                m_ref = (
                    st.number_input(
                        "M_ref",
                        min_value=0.000001,
                        value=7.674,
                        format="%.6f",
                        key="trs_m_ref",
                    )
                    if use_custom_m_ref
                    else None
                )

            o1, o2 = st.columns(2)
            with o1:
                use_manual_p_tp = st.checkbox("Manual k_TP", key="trs_use_manual_p_tp")
                p_tp_manual = (
                    st.number_input(
                        "k_TP_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="trs_k_tp_manual",
                    )
                    if use_manual_p_tp
                    else None
                )
                use_manual_p_ion = st.checkbox("Manual k_s", key="trs_use_manual_p_ion")
                p_ion_manual = (
                    st.number_input(
                        "k_s_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="trs_k_s_manual",
                    )
                    if use_manual_p_ion
                    else None
                )
                use_manual_p_pol = st.checkbox("Manual k_pol", key="trs_use_manual_p_pol")
                p_pol_manual = (
                    st.number_input(
                        "k_pol_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="trs_k_pol_manual",
                    )
                    if use_manual_p_pol
                    else None
                )
            with o2:
                use_advanced_kq_fitting = st.checkbox(
                    "Use advanced k_Q fitting",
                    key="trs_use_advanced_kq_fitting",
                )
                use_manual_k_q = False
                k_q_manual = None

                # Prefill kQ fitting parameters from chamber defaults when available.
                chamber_a = chamber_defaults_values.get("a")
                chamber_b = chamber_defaults_values.get("b")

                if use_advanced_kq_fitting:
                    if chamber_a is None or chamber_b is None:
                        st.warning(
                            "TRS-398 advanced k_Q fitting selected, but the selected chamber defaults dataset "
                            "does not provide 'a' and 'b'. Upload/activate a chamber_defaults dataset with Table 45 "
                            "parameters for this chamber type."
                        )
                    kq_a = st.number_input(
                        "k_Q fitting parameter a (chamber Table 45)",
                        value=float(chamber_a) if chamber_a is not None else 1.08918,
                        step=0.0001,
                        format="%.5f",
                        key="trs_kq_a",
                        disabled=chamber_a is None and chamber_b is None,
                    )
                    kq_b = st.number_input(
                        "k_Q fitting parameter b (chamber Table 45)",
                        value=float(chamber_b) if chamber_b is not None else -0.09222,
                        step=0.0001,
                        format="%.5f",
                        key="trs_kq_b",
                        disabled=chamber_a is None and chamber_b is None,
                    )
                else:
                    use_manual_k_q = st.checkbox("Manual k_Q", key="trs_use_manual_k_q")
                    k_q_manual = (
                        st.number_input(
                            "Manual k_Q (overrides fitted k_Q from TPR20,10)",
                            min_value=0.01,
                            value=0.973,
                            step=0.0001,
                            format="%.6f",
                            key="trs_k_q_manual",
                        )
                        if use_manual_k_q
                        else None
                    )

                if use_advanced_kq_fitting:
                    st.caption("k_Q will be fitted from TPR20,10 using chamber parameters a/b.")

                use_manual_depth_factor = st.checkbox("Manual depth_factor", key="trs_use_manual_depth_factor")
                depth_factor_manual = (
                    st.number_input(
                        "depth_factor_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="trs_depth_factor_manual",
                    )
                    if use_manual_depth_factor
                    else None
                )
                override_ndw = st.checkbox("Override N_Dw_60Co", key="trs_override_ndw")
                ndw_override = (
                    st.number_input(
                        "N_Dw_60Co",
                        min_value=0.0,
                        value=5.233e7,
                        format="%.8e",
                        key="trs_ndw_override",
                    )
                    if override_ndw
                    else None
                )

            e1, e2, e3 = st.columns(3)
            with e1:
                k_ecal = st.number_input(
                    "k_ecal",
                    min_value=0.1,
                    value=1.0,
                    step=0.001,
                    format="%.4f",
                    key="trs_k_ecal",
                )
            with e2:
                k_r50 = st.number_input(
                    "k_R50",
                    min_value=0.1,
                    value=1.0,
                    step=0.001,
                    format="%.4f",
                    key="trs_k_r50",
                )
            with e3:
                p_q_gr = st.number_input(
                    "P_Q_gr",
                    min_value=0.1,
                    value=1.0,
                    step=0.001,
                    format="%.4f",
                    key="trs_p_q_gr",
                )

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            submitted_trs398 = st.button(
                "Calculate Dose", type="primary", use_container_width=True, key="trs_submit"
            )
        with btn_col2:
            cleared_trs398 = st.button("Clear Form", use_container_width=True, key="trs_clear")

        if cleared_trs398:
            st.session_state.update(
                {
                    "trs_ktp_source": KTP_SOURCE_AUTO_AUTO,
                    "trs_manual_temperature_c": 22.0,
                    "trs_manual_pressure_kpa": 101.325,
                    "trs_beam_type": "photon",
                    "trs_chamber_type": chambers[0] if chambers else "",
                    "trs_geometry_mode": "SSD",
                    "trs_reading_unit": "nC",
                    "trs_energy_mv": 15.0,
                    "trs_field_size_cm": 10.0,
                    "trs_depth_cm": 10.0,
                    "trs_d_ref_cm": 10.0,
                    "trs_tpr_20_10": 0.730,
                    "trs_m_raw": 7.674,
                    "trs_mu_meas": 50.0,
                    "trs_p_elec": 1.0,
                    "trs_t0_c": 22.0,
                    "trs_m_high": 7.674,
                    "trs_m_low": 7.630,
                    "trs_m_pos": 7.674,
                    "trs_m_neg": 7.660,
                    "trs_p0_kpa": 101.325,
                    "trs_v_high": 300.0,
                    "trs_v_low": 150.0,
                    "trs_use_custom_m_ref": False,
                    "trs_m_ref": 7.674,
                    "trs_use_manual_p_tp": False,
                    "trs_k_tp_manual": 1.0,
                    "trs_use_manual_p_ion": False,
                    "trs_k_s_manual": 1.0,
                    "trs_use_manual_p_pol": False,
                    "trs_k_pol_manual": 1.0,
                    "trs_use_advanced_kq_fitting": False,
                    "trs_use_manual_k_q": False,
                    "trs_k_q_manual": 0.973,
                    "trs_use_manual_depth_factor": False,
                    "trs_depth_factor_manual": 1.0,
                    "trs_override_ndw": False,
                    "trs_ndw_override": 52330000.0,
                    "trs_k_ecal": 1.0,
                    "trs_k_r50": 1.0,
                    "trs_p_q_gr": 1.0,
                }
            )
            st.experimental_rerun()

    if submitted_trs398:
        try:
            chamber_defaults = get_chamber_defaults(chamber_type) or {}
            if ktp_source == KTP_SOURCE_AUTO_MANUAL:
                t_meas_c = float(manual_temperature_c)
                p_meas_kpa = float(manual_pressure_kpa)
                environmental_source = "Manual Weather"
                environment_details = {
                    "source": environmental_source,
                    "temperature_c": t_meas_c,
                    "pressure_kpa": p_meas_kpa,
                    "provider": {"weather": "manual entry"},
                }
            elif ktp_source == KTP_SOURCE_MANUAL:
                t_meas_c = float(manual_temperature_c)
                p_meas_kpa = float(manual_pressure_kpa)
                environmental_source = "Manual Entry"
                environment_details = {
                    "source": environmental_source,
                    "temperature_c": t_meas_c,
                    "pressure_kpa": p_meas_kpa,
                    "provider": {"source": "manual entry"},
                }
            else:
                if ktp_source == KTP_SOURCE_AUTO_AUTO:
                    env_settings["env_source"] = ENV_SOURCE_AUTO
                environmental_source, t_meas_c, p_meas_kpa, environment_details = _resolve_environment(env_settings)

            session_user = st.session_state.get("user") if st.session_state.get("authenticated") else None
            run_user_id = session_user["id"] if session_user else None
            run_username = session_user["username"] if session_user else "public_user"

            inputs = {
                "protocol_mode": protocol_mode,
                "beam_type": beam_type,
                "geometry_mode": geometry_mode,
                "chamber_type": chamber_type,
                # TRS-398 chamber-loaded Table 45 parameters (used for advanced k_Q fitting).
                "chamber_a": chamber_defaults.get("a"),
                "chamber_b": chamber_defaults.get("b"),
                "chamber_r_cav": chamber_defaults.get("r_cav") or chamber_defaults.get("rcav_cm"),
                "reading_unit": reading_unit,
                "energy_mv": energy_mv,
                "field_size_cm": field_size_cm,
                "depth_cm": depth_cm,
                "d_ref_cm": d_ref_cm,
                # TRS-398 beam quality metadata for audit/governance.
                "TPR_20_10": tpr_20_10,
                "beam_quality_type": "TPR20_10",
                "beam_quality_value": tpr_20_10,
                "M_raw": m_raw,
                "MU_meas": mu_meas,
                "P_elec": p_elec,
                "T_meas_C": t_meas_c,
                "P_meas_kPa": p_meas_kpa,
                "manual_temperature_c": manual_temperature_c,
                "manual_pressure_kpa": manual_pressure_kpa,
                "T0_C": t0_c,
                "P0_kPa": p0_kpa,
                "T0_cert": t0_c,
                "P0_cert": p0_kpa,
                "M_high": m_high,
                "M_low": m_low,
                "V_high": v_high,
                "V_low": v_low,
                "M_pos": m_pos,
                "M_neg": m_neg,
                "M_ref": m_ref,
                "use_manual_p_tp": use_manual_p_tp,
                "P_TP_manual": p_tp_manual,
                "use_manual_p_ion": use_manual_p_ion,
                "P_ion_manual": p_ion_manual,
                "use_manual_p_pol": use_manual_p_pol,
                "P_pol_manual": p_pol_manual,
                "use_advanced_k_q_fitting": use_advanced_kq_fitting,
                "use_manual_k_q": use_manual_k_q,
                "k_Q_manual": k_q_manual,
                # Only pass kq_a/kq_b explicitly when advanced fitting is selected.
                # If chamber a/b are present, calculator will use them even if these are omitted.
                "kq_a": (st.session_state.get("trs_kq_a") if use_advanced_kq_fitting else None),
                "kq_b": (st.session_state.get("trs_kq_b") if use_advanced_kq_fitting else None),
                "use_manual_depth_factor": use_manual_depth_factor,
                "depth_factor_manual": depth_factor_manual,
                "N_Dw_60Co": ndw_override if override_ndw else chamber_defaults.get("ndw_60co"),
                "k_ecal": k_ecal,
                "k_R50": k_r50,
                "P_Q_gr": p_q_gr,
                "environmental_source": environmental_source,
                "environmental_details": environment_details,
                "ktp_source": ktp_source,
            }

            result = calculate_dose(inputs)

            # Store computed TRS-398 audit values functionally (not comments-only).
            intermediate = result.get("intermediate", {})
            inputs["k_Q_computed"] = intermediate.get("k_Q_computed", intermediate.get("k_Q"))
            inputs["k_TP_computed"] = intermediate.get("k_TP_computed", intermediate.get("k_TP"))
            inputs["k_s_computed"] = intermediate.get("k_s_computed", intermediate.get("k_s"))
            inputs["k_pol_computed"] = intermediate.get("k_pol_computed", intermediate.get("k_pol"))

            record_run(
                user_id=run_user_id,
                username=run_username,
                beam_type=beam_type,
                inputs=inputs,
                outputs=result,
                formula_name=result["formula_name"],
                formula_version=result["formula_version"],
                dataset_versions=result["dataset_versions"],
            )

            st.success("Calculation complete.")

            m1, m2 = st.columns(2)
            m1.metric("Dose / measurement (Gy)", f"{result['outputs']['dose_per_measurement_gy']:.6f}")
            m2.metric("Dose / 100 MU (Gy)", f"{result['outputs']['dose_per_100mu_gy']:.6f}")

            csv_data, text_data = _build_calculation_summary(inputs, result, environment_details)
            export_col1, export_col2, export_col3 = st.columns([1, 1, 1])
            with export_col1:
                st.download_button(
                    "Download CSV",
                    data=csv_data,
                    file_name="calculation_summary.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with export_col2:
                st.download_button(
                    "Download Summary (TXT)",
                    data=text_data,
                    file_name="calculation_summary.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with export_col3:
                st.markdown(
                    "<button onclick=\"window.print()\" "
                    "style=\"width:100%; padding:0.72rem 1rem; border:none; "
                    "border-radius:12px; background:#7bb661; color:#ffffff; font-weight:600; "
                    "cursor:pointer;\">Print Summary</button>",
                    unsafe_allow_html=True,
                )
            st.caption("Printed: Calculation Summary. Use the browser print dialog to export to PDF or a printed report.")

            with st.expander("Show Calculation Details", expanded=False):
                st.markdown("#### Formula Expression")
                st.code(result["formula_expression"])
                st.caption(f"Formula: {result['formula_name']} (v{result['formula_version']})")

                st.markdown("#### Intermediate Values")
                _render_detail_cards(result["intermediate"], columns=3)

                st.markdown("### Environment Used")
                _render_detail_cards(_environment_details_for_display(environment_details), columns=3)

                st.markdown("### Dataset Versions")
                _render_detail_cards(result["dataset_versions"], columns=2)
        except Exception as exc:
            st.error(f"Calculation failed: {exc}")

# Ensure download buttons keep green theme even when Streamlit defaults differ.
st.markdown(
    """
    <style>
    div[data-testid="stDownloadButton"] button {
        background: #7bb661 !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
    }
    div[data-testid="stDownloadButton"] button:hover {
        filter: brightness(0.96) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with protocol_tabs[1]:
    protocol_mode = "TG51"
    with st.form("calculator_form_tg51", clear_on_submit=False):
        st.markdown("### TG-51 Calculation Mode")

        admin_env_settings = get_environment_settings()
        ktp_source_options = [
            KTP_SOURCE_AUTO_AUTO,
            KTP_SOURCE_AUTO_MANUAL,
            KTP_SOURCE_MANUAL,
        ]
        ktp_source_default = admin_env_settings.get("ktp_source", KTP_SOURCE_AUTO_AUTO)
        ktp_source_index = (
            ktp_source_options.index(ktp_source_default)
            if ktp_source_default in ktp_source_options
            else 0
        )

        ktp_source = st.radio(
            "Select KTP Source",
            options=ktp_source_options,
            index=ktp_source_index,
            horizontal=True,
            key="tg51_ktp_source",
        )

        manual_temperature_c = None
        manual_pressure_kpa = None
        if ktp_source == KTP_SOURCE_AUTO_MANUAL:
            with st.expander("Manual Weather Inputs", expanded=True):
                w1, w2 = st.columns(2)
                with w1:
                    manual_temperature_c = st.number_input(
                        "Manual Temperature (C)",
                        min_value=-50.0,
                        value=22.0,
                        step=0.1,
                        format="%.1f",
                        key="tg51_manual_temperature_c",
                    )
                with w2:
                    manual_pressure_kpa = st.number_input(
                        "Manual Pressure (kPa)",
                        min_value=0.1,
                        value=101.325,
                        step=0.1,
                        format="%.3f",
                        key="tg51_manual_pressure_kpa",
                    )

        c1, c2 = st.columns(2)
        with c1:
            beam_type = st.selectbox("Beam Type", ["photon", "electron"], key="tg51_beam_type")
            chamber_type = st.selectbox("Chamber Type", chambers, key="tg51_chamber_type")
            geometry_mode = st.selectbox("Geometry Mode", ["SSD", "SAD"], key="tg51_geometry_mode")
            reading_unit = st.selectbox("Reading Unit", ["nC", "C", "pC"], key="tg51_reading_unit")
        with c2:
            energy_mv = st.number_input(
                "Energy (MV)", min_value=1.0, value=15.0, step=0.5, key="tg51_energy_mv"
            )
            field_size_cm = st.number_input(
                "Field Size (cm)", min_value=1.0, value=10.0, step=0.5, key="tg51_field_size_cm"
            )
            depth_cm = st.number_input(
                "Depth (cm)", min_value=0.1, value=10.0, step=0.1, key="tg51_depth_cm"
            )
            d_ref_cm = st.number_input(
                "Reference Depth (cm)", min_value=0.1, value=10.0, step=0.1, key="tg51_d_ref_cm"
            )

        c3, c4 = st.columns(2)
        with c3:
            beam_quality = st.number_input(
                "Beam Quality Metric",
                min_value=0.0,
                value=0.73,
                step=0.001,
                format="%.3f",
                key="tg51_beam_quality",
            )
            m_raw = st.number_input(
                "Raw Reading",
                min_value=0.000001,
                value=7.674,
                format="%.7f",
                key="tg51_m_raw",
            )
        with c4:
            mu_meas = st.number_input(
                "MU Measured",
                min_value=0.01,
                value=50.0,
                step=1.0,
                key="tg51_mu_meas",
            )
            p_elec = st.number_input(
                "P_elec",
                min_value=0.5,
                value=1.0,
                step=0.001,
                format="%.4f",
                key="tg51_p_elec",
            )

        chamber_defaults_values = get_chamber_defaults(chamber_type) or {}
        if chamber_defaults_values:
            st.markdown(
                f"**Selected chamber defaults:** N_Dw_60Co ≈ {chamber_defaults_values['ndw_60co']:.4e}, "
                f"r_cav = {chamber_defaults_values['rcav_cm']:.3f} cm"
            )

        with st.expander("Advanced Inputs (optional)", expanded=False):
            r1, r2 = st.columns(2)
            with r1:
                t0_c = st.number_input(
                    "Reference Temperature T0 (C)", value=20.0, step=0.1, key="tg51_t0_c"
                )
                m_high = st.number_input(
                    "M_high",
                    min_value=0.000001,
                    value=7.674,
                    format="%.6f",
                    key="tg51_m_high",
                )
                m_low = st.number_input(
                    "M_low",
                    min_value=0.000001,
                    value=7.630,
                    format="%.6f",
                    key="tg51_m_low",
                )
                m_pos = st.number_input(
                    "M_pos",
                    min_value=0.000001,
                    value=7.674,
                    format="%.6f",
                    key="tg51_m_pos",
                )
                m_neg = st.number_input(
                    "M_neg",
                    min_value=0.000001,
                    value=7.660,
                    format="%.6f",
                    key="tg51_m_neg",
                )
            with r2:
                p0_kpa = st.number_input(
                    "Reference Pressure P0 (kPa)",
                    value=101.325,
                    step=0.01,
                    key="tg51_p0_kpa",
                )
                v_high = st.number_input(
                    "V_high (V)",
                    min_value=1.0,
                    value=300.0,
                    step=1.0,
                    key="tg51_v_high",
                )
                v_low = st.number_input(
                    "V_low (V)",
                    min_value=1.0,
                    value=150.0,
                    step=1.0,
                    key="tg51_v_low",
                )
                use_custom_m_ref = st.checkbox("Use custom M_ref", key="tg51_use_custom_m_ref")
                m_ref = (
                    st.number_input(
                        "M_ref",
                        min_value=0.000001,
                        value=7.674,
                        format="%.6f",
                        key="tg51_m_ref",
                    )
                    if use_custom_m_ref
                    else None
                )

            o1, o2 = st.columns(2)
            with o1:
                use_manual_p_tp = st.checkbox("Manual P_TP", key="tg51_use_manual_p_tp")
                p_tp_manual = (
                    st.number_input(
                        "P_TP_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="tg51_p_tp_manual",
                    )
                    if use_manual_p_tp
                    else None
                )
                use_manual_p_ion = st.checkbox("Manual P_ion", key="tg51_use_manual_p_ion")
                p_ion_manual = (
                    st.number_input(
                        "P_ion_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="tg51_p_ion_manual",
                    )
                    if use_manual_p_ion
                    else None
                )
                use_manual_p_pol = st.checkbox("Manual P_pol", key="tg51_use_manual_p_pol")
                p_pol_manual = (
                    st.number_input(
                        "P_pol_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="tg51_p_pol_manual",
                    )
                    if use_manual_p_pol
                    else None
                )
            with o2:
                use_manual_k_q = st.checkbox("Manual k_Q", key="tg51_use_manual_k_q")
                k_q_manual = (
                    st.number_input(
                        "k_Q_manual",
                        value=0.973,
                        step=0.0001,
                        format="%.6f",
                        key="tg51_k_q_manual",
                    )
                    if use_manual_k_q
                    else None
                )
                use_manual_depth_factor = st.checkbox("Manual depth_factor", key="tg51_use_manual_depth_factor")
                depth_factor_manual = (
                    st.number_input(
                        "depth_factor_manual",
                        value=1.0,
                        step=0.0001,
                        format="%.6f",
                        key="tg51_depth_factor_manual",
                    )
                    if use_manual_depth_factor
                    else None
                )
                override_ndw = st.checkbox("Override N_Dw_60Co", key="tg51_override_ndw")
                ndw_override = (
                    st.number_input(
                        "N_Dw_60Co",
                        min_value=0.0,
                        value=5.233e7,
                        format="%.8e",
                        key="tg51_ndw_override",
                    )
                    if override_ndw
                    else None
                )

            e1, e2, e3 = st.columns(3)
            with e1:
                k_ecal = st.number_input(
                    "k_ecal",
                    min_value=0.1,
                    value=1.0,
                    step=0.001,
                    format="%.4f",
                    key="tg51_k_ecal",
                )
            with e2:
                k_r50 = st.number_input(
                    "k_R50",
                    min_value=0.1,
                    value=1.0,
                    step=0.001,
                    format="%.4f",
                    key="tg51_k_r50",
                )
            with e3:
                p_q_gr = st.number_input(
                    "P_Q_gr",
                    min_value=0.1,
                    value=1.0,
                    step=0.001,
                    format="%.4f",
                    key="tg51_p_q_gr",
                )

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            submitted_tg51 = st.form_submit_button("Calculate Dose", type="primary", use_container_width=True)
        with btn_col2:
            cleared_tg51 = st.form_submit_button("Clear Form", use_container_width=True)

        if cleared_tg51:
            st.session_state.update(
                {
                    "tg51_beam_type": "photon",
                    "tg51_chamber_type": chambers[0] if chambers else "",
                    "tg51_geometry_mode": "SSD",
                    "tg51_reading_unit": "nC",
                    "tg51_energy_mv": 15.0,
                    "tg51_field_size_cm": 10.0,
                    "tg51_depth_cm": 10.0,
                    "tg51_d_ref_cm": 10.0,
                    "tg51_beam_quality": 0.73,
                    "tg51_m_raw": 7.674,
                    "tg51_mu_meas": 50.0,
                    "tg51_p_elec": 1.0,
                    "tg51_t0_c": 20.0,
                    "tg51_m_high": 7.674,
                    "tg51_m_low": 7.630,
                    "tg51_m_pos": 7.674,
                    "tg51_m_neg": 7.660,
                    "tg51_p0_kpa": 101.325,
                    "tg51_v_high": 300.0,
                    "tg51_v_low": 150.0,
                    "tg51_use_custom_m_ref": False,
                    "tg51_m_ref": 7.674,
                    "tg51_use_manual_p_tp": False,
                    "tg51_p_tp_manual": 1.0,
                    "tg51_use_manual_p_ion": False,
                    "tg51_p_ion_manual": 1.0,
                    "tg51_use_manual_p_pol": False,
                    "tg51_p_pol_manual": 1.0,
                    "tg51_use_manual_k_q": False,
                    "tg51_k_q_manual": 0.973,
                    "tg51_use_manual_depth_factor": False,
                    "tg51_depth_factor_manual": 1.0,
                    "tg51_override_ndw": False,
                    "tg51_ndw_override": 52330000.0,
                    "tg51_k_ecal": 1.0,
                    "tg51_k_r50": 1.0,
                    "tg51_p_q_gr": 1.0,
                }
            )
            st.experimental_rerun()

    if submitted_tg51:
        try:
            chamber_defaults = get_chamber_defaults(chamber_type) or {}

            if ktp_source == KTP_SOURCE_AUTO_MANUAL:
                # Explicit manual environment for TG-51.
                t_meas_c = float(manual_temperature_c)
                p_meas_kpa = float(manual_pressure_kpa)
                environmental_source = "Manual Weather"
                environment_details = {
                    "source": environmental_source,
                    "temperature_c": t_meas_c,
                    "pressure_kpa": p_meas_kpa,
                    "provider": {"weather": "manual entry"},
                }
            else:
                # Existing behavior: auto/configured/fallback environment.
                if admin_env_source == ENV_SOURCE_AUTO:
                    if st.session_state.get("browser_geo_pending"):
                        raise ValueError("Browser location weather is still pending.")
                    environmental_source, t_meas_c, p_meas_kpa, environment_details = _resolve_environment(env_settings)
                else:
                    environmental_source = "Configured fallback"
                    t_meas_c = float(st.session_state.get("env_manual_temperature_c", DEFAULT_T0_C))
                    p_meas_kpa = float(st.session_state.get("env_manual_pressure_kpa", DEFAULT_P0_KPA))
                    environment_details = {
                        "source": admin_env_source,
                        "temperature_c": t_meas_c,
                        "pressure_kpa": p_meas_kpa,
                    }

            session_user = st.session_state.get("user") if st.session_state.get("authenticated") else None
            run_user_id = session_user["id"] if session_user else None
            run_username = session_user["username"] if session_user else "public_user"

            inputs = {
                "protocol_mode": protocol_mode,
                "beam_type": beam_type,
                "geometry_mode": geometry_mode,
                "chamber_type": chamber_type,
                "reading_unit": reading_unit,
                "energy_mv": energy_mv,
                "field_size_cm": field_size_cm,
                "depth_cm": depth_cm,
                "d_ref_cm": d_ref_cm,
                "beam_quality": beam_quality,
                "M_raw": m_raw,
                "MU_meas": mu_meas,
                "P_elec": p_elec,
                "T_meas_C": t_meas_c,
                "P_meas_kPa": p_meas_kpa,
                "T0_C": t0_c,
                "P0_kPa": p0_kpa,
                "M_high": m_high,
                "M_low": m_low,
                "V_high": v_high,
                "V_low": v_low,
                "M_pos": m_pos,
                "M_neg": m_neg,
                "M_ref": m_ref,
                "use_manual_p_tp": use_manual_p_tp,
                "P_TP_manual": p_tp_manual,
                "use_manual_p_ion": use_manual_p_ion,
                "P_ion_manual": p_ion_manual,
                "use_manual_p_pol": use_manual_p_pol,
                "P_pol_manual": p_pol_manual,
                "use_manual_k_q": use_manual_k_q,
                "k_Q_manual": k_q_manual,
                "use_manual_depth_factor": use_manual_depth_factor,
                "depth_factor_manual": depth_factor_manual,
                "N_Dw_60Co": ndw_override if override_ndw else chamber_defaults.get("ndw_60co"),
                "k_ecal": k_ecal,
                "k_R50": k_r50,
                "P_Q_gr": p_q_gr,
                "environmental_source": environmental_source,
                "environmental_details": environment_details,
            }

            result = calculate_dose(inputs)

            record_run(
                user_id=run_user_id,
                username=run_username,
                beam_type=beam_type,
                inputs=inputs,
                outputs=result,
                formula_name=result["formula_name"],
                formula_version=result["formula_version"],
                dataset_versions=result["dataset_versions"],
            )

            st.success("Calculation complete.")

            m1, m2 = st.columns(2)
            m1.metric("Dose / measurement (Gy)", f"{result['outputs']['dose_per_measurement_gy']:.6f}")
            m2.metric("Dose / 100 MU (Gy)", f"{result['outputs']['dose_per_100mu_gy']:.6f}")

            csv_data, text_data = _build_calculation_summary(inputs, result, environment_details)
            export_col1, export_col2, export_col3 = st.columns([1, 1, 1])
            with export_col1:
                st.download_button(
                    "Download CSV",
                    data=csv_data,
                    file_name="calculation_summary.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with export_col2:
                st.download_button(
                    "Download Summary (TXT)",
                    data=text_data,
                    file_name="calculation_summary.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with export_col3:
                st.markdown(
                    "<button onclick=\"window.print()\" "
                    "style=\"width:100%; padding:0.72rem 1rem; border:none; "
                    "border-radius:12px; background:#7bb661; color:#ffffff; font-weight:600; "
                    "cursor:pointer;\">Print Summary</button>",
                    unsafe_allow_html=True,
                )
            st.caption("Printed: Calculation Summary. Use the browser print dialog to export to PDF or a printed report.")

            with st.expander("Show Calculation Details", expanded=False):
                st.markdown("#### Formula Expression")
                st.code(result["formula_expression"])
                st.caption(f"Formula: {result['formula_name']} (v{result['formula_version']})")

                st.markdown("#### Intermediate Values")
                _render_detail_cards(result["intermediate"], columns=3)

                st.markdown("### Environment Used")
                _render_detail_cards(_environment_details_for_display(environment_details), columns=3)

                st.markdown("### Dataset Versions")
                _render_detail_cards(result["dataset_versions"], columns=2)
        except Exception as exc:
            st.error(f"Calculation failed: {exc}")

st.markdown("Need help using the calculator? [Open the full user guide](/docs)")
