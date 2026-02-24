import streamlit as st

from dosimetry_app.bootstrap import initialize_application
from dosimetry_app.settings import ENV_SOURCE_AUTO, ENV_SOURCE_DATASET, get_environment_settings
from dosimetry_app.theme import apply_theme
from dosimetry_app.ui import init_session_state

initialize_application()
apply_theme()
init_session_state()

st.markdown(
    """
    <div class="hero-box">
      <div class="hero-title">User Guide</div>
      <div class="hero-subtitle">
        Simple, complete instructions for using the Universal Absorbed Calculation System.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

nav_left, nav_right = st.columns(2)
with nav_left:
    if st.button("Back to Calculator", key="docs_back_calculator", use_container_width=True):
        st.switch_page("pages/1_Calculator.py")
with nav_right:
    if st.button("Open Admin Portal", key="docs_open_admin", use_container_width=True):
        st.switch_page("pages/9_Admin_Portal.py")

st.caption("Use the tabs below to quickly jump to the section you need.")

tab_quick_start, tab_calculator_steps, tab_field_guide, tab_results, tab_admin, tab_troubleshooting, tab_faq = st.tabs(
    [
        "Quick Start",
        "Calculator Steps",
        "Fields Explained",
        "Understanding Results",
        "Admin Guide",
        "Troubleshooting",
        "FAQ",
    ]
)

with tab_quick_start:
    st.markdown("### What This System Does")
    st.markdown(
        """
        - This system helps you calculate absorbed dose using a guided calculator form.
        - The calculator page is public and opens first.
        - The admin portal is login-protected and is used to manage data/settings.
        - Temperature and pressure are fetched automatically and used in calculations.
        """
    )

    env_settings = get_environment_settings()
    env_source = str(env_settings.get("env_source", ""))
    env_source_label = "Auto (IP + Weather API)" if env_source == ENV_SOURCE_AUTO else "Dataset"
    if env_source not in {ENV_SOURCE_AUTO, ENV_SOURCE_DATASET}:
        env_source_label = env_source or "Unknown"
    st.info(f"Current temperature/pressure source: `{env_source_label}`")

    st.markdown("### 3-Minute Quick Start")
    st.markdown(
        """
        1. Open the calculator page.
        2. Allow location permission in your browser if prompted.
        3. Fill required calculator fields.
        4. Click `Calculate Dose`.
        5. Read the result cards and optional details.
        """
    )

    st.markdown("### Who Should Use Which Page")
    st.markdown(
        """
        - `Calculator`: for all users who need to perform calculations.
        - `Admin Portal`: for admins/physicists managing datasets and formulas.
        - `Guide (/docs)`: this page, for instructions and support.
        """
    )

with tab_calculator_steps:
    st.markdown("### Step-by-Step: Using the Calculator")
    st.markdown(
        """
        1. Open the calculator landing page.
        2. Confirm the header shows location, temperature, and pressure.
        3. If needed, press `Use My Location` to refresh live data.
        4. Fill in Core Inputs.
        5. Open Advanced Inputs only if your workflow requires them.
        6. Press `Calculate Dose`.
        7. Review:
           - Dose per measurement (Gy)
           - Dose per 100 MU (Gy)
           - Optional detail sections under `Show Calculation Details`
        """
    )

    st.markdown("### Before You Calculate")
    st.markdown(
        """
        - Make sure the correct chamber type is selected.
        - Confirm all numeric inputs are in the expected units.
        - If calculation fails, check the error message and fix the highlighted issue.
        """
    )

    st.markdown("### Mobile-Friendly Usage Tips")
    st.markdown(
        """
        - Scroll section by section and complete fields from top to bottom.
        - Use the `Calculate Dose` button at the bottom of the form.
        - Expand advanced sections only when necessary to reduce clutter.
        """
    )

with tab_field_guide:
    st.markdown("### Core Fields (Simple Meaning)")
    st.markdown(
        """
        - `Beam Type`: choose photon or electron.
        - `Chamber Type`: choose the chamber you are using.
        - `Geometry Mode`: choose SSD or SAD based on your setup.
        - `Reading Unit`: unit of your measured reading.
        - `Energy (MV)`: beam energy.
        - `Field Size (cm)`: treatment field size.
        - `Depth (cm)`: measurement depth.
        - `Reference Depth (cm)`: depth used as reference point.
        - `Beam Quality Metric`: quality value used to select correction factors.
        - `Raw Reading`: uncorrected measured reading.
        - `MU Measured`: monitor units used during measurement.
        - `P_elec`: electrometer correction factor.
        """
    )

    st.markdown("### Advanced Fields (Use Only If Needed)")
    st.markdown(
        """
        - Advanced options are for detailed QA/special protocols.
        - If you are unsure, leave advanced values at their defaults.
        - Manual overrides should be used only when validated by your team workflow.
        """
    )

    st.markdown("### Temperature and Pressure")
    st.markdown(
        """
        - You do not type these manually on calculator.
        - The system fetches them automatically from live source or dataset source.
        - Current values are shown in the top header.
        """
    )

with tab_results:
    st.markdown("### Result Cards")
    st.markdown(
        """
        - `Dose / measurement (Gy)`: computed dose for the entered measurement.
        - `Dose / 100 MU (Gy)`: normalized dose output for 100 MU.
        """
    )

    st.markdown("### Calculation Details Section")
    st.markdown(
        """
        - `Formula Expression`: formula used for this run.
        - `Intermediate Values`: internal correction and support values.
        - `Environment Used`: location, temperature, pressure used for this run.
        - `Dataset Versions`: active data versions used when calculation ran.
        """
    )

    st.markdown("### How to Confirm Result Quality")
    st.markdown(
        """
        - Verify chamber type, energy, depth, and field size were entered correctly.
        - Confirm header location/temperature/pressure are correct.
        - Re-run calculation after any correction and compare outputs.
        """
    )

with tab_admin:
    st.markdown("### Admin Access and Roles")
    st.markdown(
        """
        - `Admin / Physicist`: can manage environment, datasets, formulas, and run history.
        - `Viewer`: can review overview and run history.
        """
    )

    st.markdown("### Admin Workflow (Recommended Order)")
    st.markdown(
        """
        1. Environment tab:
           - choose `Auto` or `Dataset` source for temperature/pressure.
        2. Datasets tab:
           - upload datasets, review validation, activate correct version.
        3. Formulas tab:
           - create/test formulas, then activate approved version.
        4. Run History tab:
           - review run records, inspect detailed payloads for audits.
        """
    )

    st.markdown("### Required Dataset Columns")
    st.markdown(
        """
        - `kq_table`: `chamber_type, beam_quality, kq`
        - `pdd_table`: `energy_mv, field_size_cm, depth_cm, value`
        - `tpr_table`: `energy_mv, field_size_cm, depth_cm, value`
        - `chamber_defaults`: `chamber_type, ndw_60co, rcav_cm, reference_polarity`
        - `environmental_data`: `location, temperature_c, pressure_kpa`
        """
    )

with tab_troubleshooting:
    st.markdown("### Common Problems and Fixes")
    with st.expander("Location is not updating"):
        st.markdown(
            """
            1. Confirm browser location permission is allowed for this app.
            2. Press `Use My Location` again.
            3. If previously denied, re-enable location access in browser site settings.
            """
        )
    with st.expander("Weather data could not be refreshed"):
        st.markdown(
            """
            1. Retry after a short wait (temporary network/provider issue).
            2. Ask admin to switch Environment source to `Dataset`.
            3. Confirm internet connectivity on the host running the app.
            """
        )
    with st.expander("Calculation failed"):
        st.markdown(
            """
            1. Confirm required datasets are uploaded and active.
            2. Confirm an active formula exists for selected beam type.
            3. Check your input values and units for mistakes.
            """
        )
    with st.expander("Admin login does not work"):
        st.markdown(
            """
            1. Re-check username and password.
            2. If credentials were changed, use the current deployed credentials.
            """
        )

with tab_faq:
    st.markdown("### Frequently Asked Questions")
    with st.expander("Do I need to sign in to calculate dose?"):
        st.markdown("No. The calculator is public and does not require login.")
    with st.expander("Do I need to enter temperature and pressure manually?"):
        st.markdown(
            "No. The system fetches these automatically and applies them during calculation."
        )
    with st.expander("When should I use Advanced Inputs?"):
        st.markdown(
            "Use them only when your protocol specifically requires overrides or extra correction controls."
        )
    with st.expander("Can I trust old data versions after updates?"):
        st.markdown(
            "Each run stores formula and dataset versions used, so historical runs remain traceable."
        )

st.caption("Guide route: `/docs` | You can return to calculator anytime using the top button.")
