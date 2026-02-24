from __future__ import annotations

import streamlit as st

from dosimetry_app.auth import authenticate


def init_session_state() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)


def login_widget() -> None:
    init_session_state()
    if st.session_state["authenticated"]:
        return

    with st.form("login_form"):
        st.subheader("Sign in")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state["authenticated"] = True
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Invalid username or password.")


def logout_button() -> None:
    init_session_state()
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        st.rerun()


def require_login() -> dict:
    init_session_state()
    if not st.session_state["authenticated"] or not st.session_state["user"]:
        st.warning("Login is required for this page.")
        if st.button("Open Admin Portal"):
            st.switch_page("pages/9_Admin_Portal.py")
        st.stop()
    return st.session_state["user"]


def require_roles(allowed_roles: set[str]) -> dict:
    user = require_login()
    if user["role"] not in allowed_roles:
        st.error("You do not have permission for this page.")
        st.stop()
    return user


def render_sidebar_user() -> None:
    init_session_state()
    with st.sidebar:
        st.markdown("### Session")
        if st.session_state["authenticated"] and st.session_state["user"]:
            user = st.session_state["user"]
            st.write(f"User: `{user['username']}`")
            st.write(f"Role: `{user['role']}`")
            logout_button()
        else:
            st.write("Not signed in")


def render_admin_nav(current: str = "") -> None:
    nav = st.columns(5)
    with nav[0]:
        if st.button("Calculator", key=f"nav_calc_{current}"):
            st.switch_page("pages/1_Calculator.py")
    with nav[1]:
        if st.button("Admin Home", key=f"nav_home_{current}"):
            st.switch_page("pages/9_Admin_Portal.py")
    with nav[2]:
        if st.button("Datasets", key=f"nav_data_{current}"):
            st.switch_page("pages/2_Admin_Datasets.py")
    with nav[3]:
        if st.button("Formulas", key=f"nav_formula_{current}"):
            st.switch_page("pages/3_Admin_Formulas.py")
    with nav[4]:
        if st.button("Run History", key=f"nav_runs_{current}"):
            st.switch_page("pages/4_Run_History.py")
