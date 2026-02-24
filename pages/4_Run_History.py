import json

import pandas as pd
import streamlit as st

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.runs import get_run, list_runs
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state, render_admin_nav, require_login

initialize_application()
apply_theme()
init_session_state()
require_login()

st.title("Run History")
st.caption("Audit trail for calculator executions")
render_admin_nav(current="history")

limit = st.slider("Rows", min_value=10, max_value=500, value=100, step=10)
rows = list_runs(limit=limit)

if not rows:
    st.info("No calculation runs available.")
    st.stop()

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

selected_id = st.number_input("Inspect run id", min_value=1, step=1, value=int(table_rows[0]["id"]))
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
