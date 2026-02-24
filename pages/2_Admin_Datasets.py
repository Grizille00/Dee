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
from dosimetry_app.settings import (
    ENV_SOURCE_AUTO,
    ENV_SOURCE_DATASET,
    get_environment_settings,
    save_environment_settings,
)
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state, render_admin_nav, require_roles

initialize_application()
apply_theme()
init_session_state()
user = require_roles({"admin", "physicist"})

st.title("Admin - Datasets")
st.caption("Upload, validate, version, and activate datasets used by the calculator")
render_admin_nav(current="datasets")

st.markdown("### Environmental Source Settings")
env_settings = get_environment_settings()
source_options = [ENV_SOURCE_DATASET, ENV_SOURCE_AUTO]
if env_settings["env_source"] not in source_options:
    source_index = 0
else:
    source_index = source_options.index(str(env_settings["env_source"]))

dataset_locations = list_environment_locations()
dataset_location_options = [""] + dataset_locations
stored_location = str(env_settings["env_dataset_location"])
if stored_location not in dataset_location_options:
    dataset_location_index = 0
else:
    dataset_location_index = dataset_location_options.index(stored_location)

with st.form("environment_settings_form"):
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
    "No manual typing is required in calculator or admin."
)

with st.form("upload_dataset_form"):
    dataset_type = st.selectbox("Dataset Type", get_supported_dataset_types())
    file = st.file_uploader("Dataset File (CSV/XLSX)", type=["csv", "xlsx", "xls"])
    notes = st.text_input("Notes", value="")
    submitted = st.form_submit_button("Upload Dataset")

if submitted:
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
    )
    selected_id = int(selected_label.split("|")[0].replace("id=", "").strip())
    if st.button("Activate Selected Dataset"):
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
    with st.expander(f"{dataset_type}"):
        if metadata is None or frame is None:
            st.write("No active dataset")
        else:
            st.write(f"Version: {metadata['version']} | Uploaded by: {metadata['uploaded_by']}")
            st.dataframe(frame.head(50), use_container_width=True)
