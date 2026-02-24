import json

import pandas as pd
import streamlit as st

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.formulas import (
    activate_formula,
    create_formula,
    list_formulas,
    safe_eval_formula,
)
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state, render_admin_nav, require_roles

initialize_application()
apply_theme()
init_session_state()
user = require_roles({"admin", "physicist"})

st.title("Admin - Formulas")
st.caption("Create, validate, test, and activate formulas used by the calculator")
render_admin_nav(current="formulas")

with st.form("create_formula_form"):
    name = st.text_input("Formula Name", value="dw_custom")
    beam_type = st.selectbox("Beam Type", ["photon", "electron"])
    expression = st.text_area(
        "Expression",
        value="M_Q * N_Dw_60Co * k_Q * depth_factor",
        height=100,
    )
    variables_raw = st.text_input(
        "Variables (comma-separated)",
        value="M_Q, N_Dw_60Co, k_Q, depth_factor",
    )
    units_raw = st.text_area("Units JSON", value='{"output":"Gy per measurement"}', height=80)
    notes = st.text_input("Notes", value="")
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
    selected_label = st.selectbox("Formula", labels)
    selected_id = int(selected_label.split("|")[0].replace("id=", "").strip())
    selected = next(row for row in all_formulas if row["id"] == selected_id)
    st.code(selected["expression"])
    test_values = st.text_area("Test values JSON", value='{"M_Q": 1.0, "N_Dw_60Co": 5.233e7, "k_Q": 0.973, "depth_factor": 1.0}')
    if st.button("Run Test Evaluation"):
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
    )
    activate_id = int(activate_label.split("|")[0].replace("id=", "").strip())
    if st.button("Activate Selected Formula"):
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
