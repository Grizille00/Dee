# System Design Document (SDD)

System: Universal Absorbed Calculation System

## 1. System Design Overview
The Universal Absorbed Calculation System is a web-based scientific calculator for radiation dosimetry. It is designed to support physics quality assurance teams with a modern, browser-first workflow that combines interactive calculation, configuration, dataset management, and audit tracing.

The system is organized into three main areas:
1. Calculator page for measurement input, environment selection, and dose computation.
2. Admin portal for dataset management, formula management, and run history.
3. Background services for applying themes, loading datasets, and storing calculation runs.

## 2. Technology Stack
The application uses the following technologies:

- **Python**: Primary application language for backend logic, dataset handling, and formula evaluation.
- **Streamlit**: Web UI framework for rapid deployment of interactive scientific tools.
- **SQLite**: Lightweight database engine to store settings, run history, and active formula metadata.
- **Pandas / NumPy**: Data libraries for dataset interpolation, numeric lookups, and table processing.
- **HTML/CSS**: Custom styling for responsive desktop layout, print-friendly export, and polished UI.

## 3. Justification of Technology Choices
### Why Streamlit?
- Streamlit enables rapid development of data-driven interfaces with minimal UI boilerplate.
- It integrates naturally with Python scientific libraries and allows direct display of tables, charts, and form controls.
- Rapid iteration is possible during development and demonstration phases.
- The community edition supports easy hosting, sharing, and validation before moving to a paid platform.

### Why not MATLAB?
- **Accessibility**: MATLAB requires a paid license and local installation; this web app runs in any browser.
- **Collaboration**: Browser-based deployment allows multiple users and remote review without MATLAB access.
- **Maintainability**: Python has a larger ecosystem for open-source scientific computing and easier integration with web technologies.
- **Deployment**: Streamlit apps can be hosted quickly on the community tier and later migrated to enterprise-grade hosting.
- **Cost**: MATLAB licensing is expensive for broader distribution; Streamlit Community avoids that barrier.

## 4. Application Behavior and Data Flow
### Input and Calculation Flow
1. The user selects beam type, chamber type, geometry, and reading units.
2. The user chooses a protocol mode:
   - **TRS-398**: uses TRS-398-specific factors (k_TP, k_s, k_pol, and k_Q).
   - **TG-51**: uses TG-51-specific k_Q lookup/overrides.
3. The user chooses KTP / correction inputs:
   - **Automatic weather inputs** (live/configured) or **Manual weather inputs** (temperature/pressure entry).
4. For **TRS-398**, k_Q is resolved as follows:
   - **Advanced k_Q fitting**: computes k_Q from **TPR20,10** and **chamber-loaded Table 45 parameters** `a` and `b` from the active `chamber_defaults` dataset.
   - **Manual k_Q**: allows explicit `k_Q_manual` override (bypasses the TPR-derived k_Q fit).
   - Guardrails are shown in the UI if the selected chamber dataset does not provide required Table 45 parameters (`a`/`b`) for advanced fitting.
5. The calculator computes correction factors and applies the active formula to produce dose values.
6. The result page displays dose per measurement and dose per 100 MU.
7. Users can print the summary or download CSV / text exports.

### Audit and Traceability
- Each successful calculation is recorded with:
  - user identity or public mode
  - input values and environment details
  - chosen formula and dataset versions
  - computed outputs
- This supports internal review and a reproducible audit trail.

## 5. User Interface Features
The calculator includes:
- Core form input fields for beam, energy, field size, depth, and raw measurement.
- KTP source selection for automatic vs manual modes.
- Manual weather input fields when manual weather mode is selected.
- A clear form button to reset values to defaults.
- A print button to create a printed or PDF report via browser print.
- Export buttons for CSV and text summary files.
- A details expander for formula expression, intermediate values, dataset versions, and environment context.

## 6. Hosting Strategy
### Current Hosting: Streamlit Community
- The app is currently designed for Streamlit Community hosting.
- Community hosting is suitable for early deployment, prototype testing, and public demonstrations.
- It provides a fast, low-cost way to validate workflows with stakeholders.

### Future Hosting: Paid Streamlit Platform
- Once the app is validated, a paid Streamlit deployment or private workspace is recommended for:
  - higher reliability and uptime
  - custom domain support
  - private access controls and authentication
  - stronger performance for multiple simultaneous users
- A paid Streamlit plan simplifies access control and offers more predictable service levels.

## 7. Why Not MATLAB for This Deployment
MATLAB is powerful for algorithm development, but it is not ideal for this application because:
- It is not a browser-native deployment platform.
- It requires local installation and licenses for each user.
- It is less convenient for a shared admin/data management portal.
- The collaboration and hosting model is more limited than a web-first Streamlit architecture.

## 8. Summary of Benefits
This system is designed to deliver:
- fast browser-based access for calculation and review
- flexible manual or automatic data entry modes
- improved traceability through stored runs and active dataset version tracking
- a lightweight deployment path on Streamlit Community today, with an easy migration path to a paid platform in the future
- a practical alternative to heavier desktop tools like MATLAB for a shared physics workflow

## 9. Operational Notes
- The user experience is optimized for wide-screen desktop use and responsive layouts.
- The app uses safe formula execution and type-safe dataset lookups.
- Live weather and location services are optional; manual weather input is supported to avoid dependency on network services.
- Export and print options provide a clear “Calculation Summary” output for record keeping.
