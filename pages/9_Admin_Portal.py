import json

import pandas as pd
import streamlit as st

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.datasets import (
    activate_dataset,
    get_active_dataset,
    get_supported_dataset_types,
    list_environment_locations,
    list_datasets,
    save_uploaded_dataset,
)
from dosimetry_app.formulas import (
    activate_formula,
    create_formula,
    list_formulas,
    safe_eval_formula,
)
from dosimetry_app.runs import get_run, list_runs
from dosimetry_app.settings import (
    ENV_SOURCE_AUTO,
    ENV_SOURCE_DATASET,
    get_environment_settings,
    save_environment_settings,
)
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state, login_widget, logout_button

initialize_application()
apply_theme()
init_session_state()


def _render_overview(user: dict) -> None:
    datasets = list_datasets()
    formulas = list_formulas()
    recent_runs = list_runs(limit=200)

    active_datasets = sum(1 for row in datasets if row["status"] == "active")
    active_formulas = sum(1 for row in formulas if row["status"] == "active")
    invalid_formulas = sum(1 for row in formulas if row["status"] == "invalid")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Datasets", len(datasets))
    m2.metric("Active Datasets", active_datasets)
    m3.metric("Active Formulas", active_formulas)
    m4.metric("Recent Runs", len(recent_runs))

    st.caption(f"Role: `{user['role']}`")
    if user["role"] in {"admin", "physicist"}:
        st.info("Manage settings, datasets, formulas, and history from these tabs.")
    else:
        st.info("Viewer role can access overview and run history.")
    if invalid_formulas > 0:
        st.warning(f"There are {invalid_formulas} invalid formulas in the registry.")


def _render_environment_tab() -> None:
    st.markdown("### Environmental Source Settings")
    env_settings = get_environment_settings()
    source_options = [ENV_SOURCE_DATASET, ENV_SOURCE_AUTO]
    source_index = source_options.index(str(env_settings["env_source"])) if env_settings["env_source"] in source_options else 0

    dataset_locations = list_environment_locations()
    dataset_location_options = [""] + dataset_locations
    stored_location = str(env_settings["env_dataset_location"])
    dataset_location_index = (
        dataset_location_options.index(stored_location) if stored_location in dataset_location_options else 0
    )

    with st.form("portal_environment_settings_form"):
        env_source = st.selectbox("Temperature/Pressure Source", source_options, index=source_index)
        env_dataset_location = st.selectbox(
            "Location Target (used for Dataset and Auto source)",
            dataset_location_options,
            index=dataset_location_index,
            format_func=lambda value: "Live auto-detection (IP/browser)" if value == "" else value,
        )
        settings_submitted = st.form_submit_button("Save Environmental Settings")

    if settings_submitted:
        try:
            if env_source == ENV_SOURCE_DATASET and not dataset_locations:
                raise ValueError("No active environmental_data dataset locations available.")
            save_environment_settings(
                env_source=env_source,
                env_manual_temperature_c=float(env_settings["env_manual_temperature_c"]),
                env_manual_pressure_kpa=float(env_settings["env_manual_pressure_kpa"]),
                env_dataset_location=env_dataset_location,
            )
            st.success("Environmental settings saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to save settings: {exc}")

    st.caption(
        "Calculator uses fetched temperature/pressure from dataset or live weather. "
        "No manual typing is required."
    )


def _render_datasets_tab(user: dict) -> None:
    st.markdown("### Upload Dataset")
    with st.form("portal_upload_dataset_form"):
        dataset_type = st.selectbox("Dataset Type", get_supported_dataset_types(), key="portal_dataset_type")
        file = st.file_uploader("Dataset File (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="portal_dataset_file")
        notes = st.text_input("Notes", value="", key="portal_dataset_notes")
        uploaded = st.form_submit_button("Upload Dataset")

    if uploaded:
        if not file:
            st.error("Please choose a file.")
        else:
            dataset_id, errors = save_uploaded_dataset(
                dataset_type=dataset_type,
                uploaded_file=file,
                uploaded_by=user["username"],
                notes=notes or None,
            )
            if errors:
                st.error(f"Dataset v{dataset_id} uploaded but failed validation.")
                for err in errors:
                    st.write(f"- {err}")
            else:
                st.success(f"Dataset uploaded successfully. Record ID: {dataset_id}")

    st.markdown("### Activate Dataset Version")
    all_rows = list_datasets()
    eligible = [row for row in all_rows if row["validation_status"] == "passed" and row["status"] != "active"]
    if eligible:
        selected_label = st.selectbox(
            "Choose dataset version",
            [f"id={row['id']} | {row['dataset_type']} v{row['version']}" for row in eligible],
            key="portal_dataset_activate_select",
        )
        selected_id = int(selected_label.split("|")[0].replace("id=", "").strip())
        if st.button("Activate Selected Dataset", key="portal_dataset_activate_button"):
            try:
                activate_dataset(selected_id)
                st.success("Dataset activated.")
                st.rerun()
            except Exception as exc:
                st.error(f"Activation failed: {exc}")
    else:
        st.info("No eligible inactive datasets to activate.")

    st.markdown("### Dataset Registry")
    if all_rows:
        table = []
        for row in all_rows:
            table.append(
                {
                    "id": row["id"],
                    "dataset_type": row["dataset_type"],
                    "version": row["version"],
                    "status": row["status"],
                    "validation_status": row["validation_status"],
                    "uploaded_by": row["uploaded_by"],
                    "uploaded_at": row["uploaded_at"],
                    "notes": row["notes"],
                    "validation_errors": ", ".join(json.loads(row["validation_errors_json"] or "[]")),
                }
            )
        st.dataframe(pd.DataFrame(table), use_container_width=True)
    else:
        st.info("No datasets found.")

    st.markdown("### Active Dataset Preview")
    for dataset_type in get_supported_dataset_types():
        metadata, frame = get_active_dataset(dataset_type)
        with st.expander(dataset_type):
            if metadata is None or frame is None:
                st.write("No active dataset")
            else:
                st.write(f"Version: {metadata['version']} | Uploaded by: {metadata['uploaded_by']}")
                st.dataframe(frame.head(50), use_container_width=True)


def _render_formulas_tab(user: dict) -> None:
    st.markdown("### Create Formula")
    with st.form("portal_create_formula_form"):
        name = st.text_input("Formula Name", value="dw_custom", key="portal_formula_name")
        beam_type = st.selectbox("Beam Type", ["photon", "electron"], key="portal_formula_beam_type")
        expression = st.text_area(
            "Expression",
            value="M_Q * N_Dw_60Co * k_Q * depth_factor",
            height=100,
            key="portal_formula_expression",
        )
        variables_raw = st.text_input(
            "Variables (comma-separated)",
            value="M_Q, N_Dw_60Co, k_Q, depth_factor",
            key="portal_formula_variables",
        )
        units_raw = st.text_area(
            "Units JSON",
            value='{"output":"Gy per measurement"}',
            height=80,
            key="portal_formula_units",
        )
        notes = st.text_input("Notes", value="", key="portal_formula_notes")
        create_submitted = st.form_submit_button("Create Formula")

    if create_submitted:
        variables = [value.strip() for value in variables_raw.split(",") if value.strip()]
        try:
            units = json.loads(units_raw) if units_raw.strip() else {}
        except json.JSONDecodeError as exc:
            st.error(f"Invalid Units JSON: {exc}")
            units = None

        if units is not None:
            formula_id, errors = create_formula(
                name=name.strip(),
                beam_type=beam_type,
                expression=expression.strip(),
                variables=variables,
                units=units,
                created_by=user["username"],
                notes=notes or None,
            )
            if errors:
                st.error(f"Formula created (id={formula_id}) but failed validation.")
                for err in errors:
                    st.write(f"- {err}")
            else:
                st.success(f"Formula created successfully (id={formula_id}).")

    all_formulas = list_formulas()

    st.markdown("### Test Formula")
    if all_formulas:
        labels = [
            f"id={row['id']} | {row['beam_type']} | {row['name']} v{row['version']} ({row['status']})"
            for row in all_formulas
        ]
        selected_label = st.selectbox("Formula", labels, key="portal_formula_test_select")
        selected_id = int(selected_label.split("|")[0].replace("id=", "").strip())
        selected = next(row for row in all_formulas if row["id"] == selected_id)
        st.code(selected["expression"])
        test_values = st.text_area(
            "Test values JSON",
            value='{"M_Q": 1.0, "N_Dw_60Co": 5.233e7, "k_Q": 0.973, "depth_factor": 1.0}',
            key="portal_formula_test_values",
        )
        if st.button("Run Test Evaluation", key="portal_formula_test_run"):
            try:
                values = json.loads(test_values)
                output = safe_eval_formula(selected["expression"], values)
                st.success(f"Result: {output}")
            except Exception as exc:
                st.error(f"Test evaluation failed: {exc}")
    else:
        st.info("No formulas available.")

    st.markdown("### Activate Formula")
    eligible = [row for row in all_formulas if row["status"] != "active" and row["status"] != "invalid"]
    if eligible:
        activate_label = st.selectbox(
            "Eligible formulas",
            [f"id={row['id']} | {row['beam_type']} | {row['name']} v{row['version']}" for row in eligible],
            key="portal_formula_activate_select",
        )
        activate_id = int(activate_label.split("|")[0].replace("id=", "").strip())
        if st.button("Activate Selected Formula", key="portal_formula_activate_button"):
            try:
                activate_formula(activate_id)
                st.success("Formula activated.")
                st.rerun()
            except Exception as exc:
                st.error(f"Activation failed: {exc}")
    else:
        st.info("No eligible formulas to activate.")

    st.markdown("### Formula Registry")
    if all_formulas:
        table = []
        for row in all_formulas:
            table.append(
                {
                    "id": row["id"],
                    "beam_type": row["beam_type"],
                    "name": row["name"],
                    "version": row["version"],
                    "status": row["status"],
                    "expression": row["expression"],
                    "variables": ", ".join(row["variables"]),
                    "validation_errors": ", ".join(row["validation_errors"]),
                    "created_by": row["created_by"],
                    "created_at": row["created_at"],
                }
            )
        st.dataframe(pd.DataFrame(table), use_container_width=True)
    else:
        st.info("No formulas found.")


def _render_history_tab() -> None:
    limit = st.slider("Rows", min_value=10, max_value=500, value=100, step=10, key="portal_history_rows")
    rows = list_runs(limit=limit)

    if not rows:
        st.info("No calculation runs available.")
        return

    table_rows = []
    for row in rows:
        dose_per_100 = None
        outputs = row.get("outputs", {})
        if isinstance(outputs, dict):
            nested = outputs.get("outputs", {})
            if isinstance(nested, dict):
                dose_per_100 = nested.get("dose_per_100mu_gy")

        table_rows.append(
            {
                "id": row["id"],
                "run_ts": row["run_ts"],
                "username": row["username"],
                "beam_type": row["beam_type"],
                "formula_name": row["formula_name"],
                "formula_version": row["formula_version"],
                "dose_per_100mu_gy": dose_per_100,
            }
        )

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

    selected_id = st.number_input(
        "Inspect run id",
        min_value=1,
        step=1,
        value=int(table_rows[0]["id"]),
        key="portal_history_run_id",
    )
    selected = get_run(int(selected_id))
    if selected:
        st.markdown("### Selected Run Details")
        st.write(f"Timestamp: `{selected['run_ts']}`")
        st.write(f"User: `{selected['username']}`")
        st.write(f"Formula: `{selected['formula_name']} v{selected['formula_version']}`")
        st.markdown("Inputs")
        st.code(json.dumps(selected["inputs"], indent=2))
        st.markdown("Outputs")
        st.code(json.dumps(selected["outputs"], indent=2))
        st.markdown("Dataset Versions")
        st.code(json.dumps(selected["dataset_versions"], indent=2))
    else:
        st.warning("Run not found for selected id.")


st.markdown(
    """
    <div class="hero-box">
      <div class="hero-title">Admin Portal</div>
      <div class="hero-subtitle">
        Sign in to manage datasets, formulas, settings, and calculation history in one page.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

top_left, top_right = st.columns([1, 1])
with top_left:
    if st.button("Back to Calculator", key="admin_back_to_calculator"):
        st.switch_page("pages/1_Calculator.py")
with top_right:
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        logout_button()

if not st.session_state.get("authenticated") or not st.session_state.get("user"):
    login_widget()
    st.stop()

user = st.session_state["user"]
st.success(f"Signed in as `{user['username']}` ({user['role']})")

if user["role"] in {"admin", "physicist"}:
    tab_overview, tab_environment, tab_datasets, tab_formulas, tab_history = st.tabs(
        ["Overview", "Environment", "Datasets", "Formulas", "Run History"]
    )
    with tab_overview:
        _render_overview(user)
    with tab_environment:
        _render_environment_tab()
    with tab_datasets:
        _render_datasets_tab(user)
    with tab_formulas:
        _render_formulas_tab(user)
    with tab_history:
        _render_history_tab()
else:
    tab_overview, tab_history = st.tabs(["Overview", "Run History"])
    with tab_overview:
        _render_overview(user)
    with tab_history:
        _render_history_tab()
