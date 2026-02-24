from datetime import datetime
from html import escape as html_escape
import json

import streamlit as st

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
from dosimetry_app.settings import (
    ENV_SOURCE_AUTO,
    ENV_SOURCE_DATASET,
    ENV_SOURCE_MANUAL,
    get_environment_settings,
)
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state
from dosimetry_app.weather import (
    auto_detect_environment,
    detect_location_from_ip,
    fetch_current_environment,
    reverse_geocode_coordinates,
)

initialize_application()
apply_theme()
init_session_state()


GEOLOCATION_JS_EXPRESSION = """
(async () => {
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
      (position) =>
        resolve({
          status: "success",
          permission_state: permissionState,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy_m: position.coords.accuracy,
          timestamp: position.timestamp
        }),
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


def _ensure_auto_environment_snapshot(env_settings: dict) -> None:
    if str(env_settings["env_source"]) != ENV_SOURCE_AUTO:
        return
    if st.session_state.get("live_environment_override"):
        return
    if st.session_state.get("auto_environment_warmup_done"):
        return

    configured_location = str(env_settings["env_dataset_location"]) or None
    preferred_location = configured_location if configured_location else None
    try:
        env_auto = auto_detect_environment(preferred_location=preferred_location)
        st.session_state["live_environment_override"] = env_auto
    except Exception:
        pass
    finally:
        st.session_state["auto_environment_warmup_done"] = True


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

    location_label = "Location detected"
    city = ""
    country = ""
    country_code = ""
    try:
        reverse_geo = reverse_geocode_coordinates(latitude=latitude, longitude=longitude)
        if reverse_geo.get("location_label"):
            location_label = str(reverse_geo["location_label"])
        city = str(reverse_geo.get("city", ""))
        country = str(reverse_geo.get("country", ""))
        country_code = str(reverse_geo.get("country_code", ""))
    except Exception:
        # Fall back to IP label enrichment when reverse geocoding is unavailable.
        pass

    if not city and not country:
        try:
            ip_location = detect_location_from_ip()
            city = str(ip_location.get("city", "")).strip()
            country = str(ip_location.get("country", "")).strip()
            if not country_code:
                country_code = str(ip_location.get("country_code", "")).strip()
        except Exception:
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
        if configured_location:
            return configured_location, None, None
        return "Detecting current location...", None, None

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

        preferred_location = configured_location if configured_location else None
        try:
            with st.spinner("Fetching live weather data..."):
                env_auto = auto_detect_environment(preferred_location=preferred_location)
            t_meas_c = float(env_auto["temperature_c"])
            p_meas_kpa = float(env_auto["pressure_kpa"])
        except Exception as exc:
            raise ValueError(
                "Live environmental data is unavailable. Please refresh location and try again."
            ) from exc

        st.session_state["live_environment_override"] = env_auto
        return environmental_source, t_meas_c, p_meas_kpa, env_auto

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
    _ensure_auto_environment_snapshot(env_settings)
    _ingest_browser_geolocation_payload()

header_location, header_temp, header_pressure = _header_environment_snapshot(env_settings)
header_status = _header_status_text(env_settings)
header_temp_label = f"{header_temp:.1f} C" if header_temp is not None else "--"
header_pressure_label = f"{header_pressure:.1f} kPa" if header_pressure is not None else "--"

top_left, top_mid, top_right = st.columns([1.2, 2.6, 1.2])
with top_left:
    if st.button("Open Admin Portal", key="open_admin_portal"):
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

with st.form("calculator_form", clear_on_submit=False):
    st.markdown("### Core Inputs")

    c1, c2 = st.columns(2)
    with c1:
        beam_type = st.selectbox("Beam Type", ["photon", "electron"])
        chamber_type = st.selectbox("Chamber Type", chambers)
        geometry_mode = st.selectbox("Geometry Mode", ["SSD", "SAD"])
        reading_unit = st.selectbox("Reading Unit", ["nC", "C", "pC"])
    with c2:
        energy_mv = st.number_input("Energy (MV)", min_value=1.0, value=15.0, step=0.5)
        field_size_cm = st.number_input("Field Size (cm)", min_value=1.0, value=10.0, step=0.5)
        depth_cm = st.number_input("Depth (cm)", min_value=0.1, value=10.0, step=0.1)
        d_ref_cm = st.number_input("Reference Depth (cm)", min_value=0.1, value=10.0, step=0.1)

    c3, c4 = st.columns(2)
    with c3:
        beam_quality = st.number_input("Beam Quality Metric", min_value=0.0, value=0.73, step=0.01)
        m_raw = st.number_input("Raw Reading", min_value=0.000001, value=7.674, format="%.6f")
    with c4:
        mu_meas = st.number_input("MU Measured", min_value=0.01, value=50.0, step=1.0)
        p_elec = st.number_input("P_elec", min_value=0.5, value=1.0, step=0.001, format="%.4f")

    with st.expander("Advanced Inputs (optional)", expanded=False):
        r1, r2 = st.columns(2)
        with r1:
            t0_c = st.number_input("Reference Temperature T0 (C)", value=20.0, step=0.1)
            m_high = st.number_input("M_high", min_value=0.000001, value=7.674, format="%.6f")
            m_low = st.number_input("M_low", min_value=0.000001, value=7.630, format="%.6f")
            m_pos = st.number_input("M_pos", min_value=0.000001, value=7.674, format="%.6f")
            m_neg = st.number_input("M_neg", min_value=0.000001, value=7.660, format="%.6f")
        with r2:
            p0_kpa = st.number_input("Reference Pressure P0 (kPa)", value=101.325, step=0.01)
            v_high = st.number_input("V_high (V)", min_value=1.0, value=300.0, step=1.0)
            v_low = st.number_input("V_low (V)", min_value=1.0, value=150.0, step=1.0)
            use_custom_m_ref = st.checkbox("Use custom M_ref")
            m_ref = (
                st.number_input("M_ref", min_value=0.000001, value=7.674, format="%.6f")
                if use_custom_m_ref
                else None
            )

        o1, o2 = st.columns(2)
        with o1:
            use_manual_p_tp = st.checkbox("Manual P_TP")
            p_tp_manual = (
                st.number_input("P_TP_manual", value=1.0, step=0.0001, format="%.6f")
                if use_manual_p_tp
                else None
            )
            use_manual_p_ion = st.checkbox("Manual P_ion")
            p_ion_manual = (
                st.number_input("P_ion_manual", value=1.0, step=0.0001, format="%.6f")
                if use_manual_p_ion
                else None
            )
            use_manual_p_pol = st.checkbox("Manual P_pol")
            p_pol_manual = (
                st.number_input("P_pol_manual", value=1.0, step=0.0001, format="%.6f")
                if use_manual_p_pol
                else None
            )
        with o2:
            use_manual_k_q = st.checkbox("Manual k_Q")
            k_q_manual = (
                st.number_input("k_Q_manual", value=0.973, step=0.0001, format="%.6f")
                if use_manual_k_q
                else None
            )
            use_manual_depth_factor = st.checkbox("Manual depth_factor")
            depth_factor_manual = (
                st.number_input("depth_factor_manual", value=1.0, step=0.0001, format="%.6f")
                if use_manual_depth_factor
                else None
            )
            override_ndw = st.checkbox("Override N_Dw_60Co")
            ndw_override = (
                st.number_input("N_Dw_60Co", min_value=0.0, value=5.233e7, format="%.8e")
                if override_ndw
                else None
            )

        e1, e2, e3 = st.columns(3)
        with e1:
            k_ecal = st.number_input("k_ecal", min_value=0.1, value=1.0, step=0.001, format="%.4f")
        with e2:
            k_r50 = st.number_input("k_R50", min_value=0.1, value=1.0, step=0.001, format="%.4f")
        with e3:
            p_q_gr = st.number_input("P_Q_gr", min_value=0.1, value=1.0, step=0.001, format="%.4f")

    if "t0_c" not in locals():
        t0_c = 20.0
        p0_kpa = 101.325
        m_high = 7.674
        m_low = 7.630
        v_high = 300.0
        v_low = 150.0
        m_pos = 7.674
        m_neg = 7.660
        m_ref = None
        use_manual_p_tp = False
        p_tp_manual = None
        use_manual_p_ion = False
        p_ion_manual = None
        use_manual_p_pol = False
        p_pol_manual = None
        use_manual_k_q = False
        k_q_manual = None
        use_manual_depth_factor = False
        depth_factor_manual = None
        override_ndw = False
        ndw_override = None
        k_ecal = 1.0
        k_r50 = 1.0
        p_q_gr = 1.0

    submitted = st.form_submit_button("Calculate Dose", type="primary", use_container_width=True)

if submitted:
    try:
        chamber_defaults = get_chamber_defaults(chamber_type) or {}
        env_settings = get_environment_settings()
        environmental_source, t_meas_c, p_meas_kpa, environment_details = _resolve_environment(env_settings)

        session_user = st.session_state.get("user") if st.session_state.get("authenticated") else None
        run_user_id = session_user["id"] if session_user else None
        run_username = session_user["username"] if session_user else "public_user"

        inputs = {
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
