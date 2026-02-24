import streamlit as st

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state

st.set_page_config(page_title="Dosimetry Calculator", page_icon=":material/calculate:", layout="wide")

initialize_application()
apply_theme()
init_session_state()

# Public landing route goes directly to calculator.
st.switch_page("pages/1_Calculator.py")

