# Why Streamlit Was Chosen Over MATLAB

## Executive Summary
Streamlit was selected as the framework for the Universal Absorbed Calculation System (UACS) because it provides a modern, web-based architecture that is more scalable, cost-effective, and maintainable than MATLAB for this application. While MATLAB excels at algorithm development and numerical computation, it is fundamentally a desktop tool not designed for multi-user, browser-based collaboration. Streamlit enables rapid deployment, real-time environmental data integration, and future extensibility while eliminating licensing costs and infrastructure barriers.

---

## Detailed Comparison: Streamlit vs. MATLAB

### 1. **Accessibility and Deployment**

#### Streamlit Advantages:
- **Browser-based access:** No installation required. Users access the calculator through any modern web browser from any device.
- **Zero licensing barriers:** Open-source and community editions are free to use, reducing operational costs.
- **Instant deployment:** Streamlit Community Cloud offers one-click deployment with minimal infrastructure setup.
- **Remote access:** Users can collaborate from different locations without VPN or network infrastructure.

#### MATLAB Limitations:
- **Requires local installation:** Each user must install MATLAB, which is time-consuming and requires administrative privileges.
- **Expensive licensing:** MATLAB licenses cost thousands of dollars per seat, making organization-wide deployment prohibitive.
- **Single-user environment:** MATLAB is designed for individual use; sharing requires either deploying MATLAB Compiler Runtime (MCR) apps or using MATLAB Web App Server (expensive enterprise solution).
- **Limited remote accessibility:** Desktop-based nature makes remote collaboration difficult.

---

### 2. **Multi-User Collaboration and Admin Portal**

#### Streamlit Advantages:
- **Built-in admin portal:** The system includes an admin dashboard for dataset management, formula versioning, and run history—all accessible via the same web interface.
- **Audit trail:** Calculation runs are automatically stored with user identity, inputs, outputs, and dataset versions for traceability.
- **Concurrent users:** Multiple users can access the calculator simultaneously without conflicts.
- **Role-based access:** Authentication and role-based permissions (admin, viewer, public) are straightforward to implement in Streamlit.

#### MATLAB Limitations:
- **No native collaboration features:** MATLAB is fundamentally single-user; adding a shared admin portal would require building a separate web app, increasing complexity and cost.
- **Difficult audit integration:** Storing and reviewing calculation history is not native to MATLAB; custom database integration is required.
- **Limited concurrent access:** Desktop apps do not handle concurrent users well without complex licensing and network setups.
- **Separate interface for admin functions:** Would need a completely different tool (web framework) for admin features, fragmenting the codebase.

---

### 3. **Cost of Ownership**

#### Streamlit Advantages:
- **Free community hosting:** Streamlit Community Cloud costs nothing for moderate usage.
- **Scalable pricing:** Paid Streamlit plans start at a fraction of the cost of MATLAB licensing.
- **Single ecosystem:** All development (UI, logic, data handling) in one Python environment reduces toolchain costs.
- **Open-source dependencies:** Can leverage free scientific libraries (NumPy, Pandas, SciPy) without additional licensing.

#### MATLAB Limitations:
- **Per-seat licensing:** MATLAB licenses cost ~$2,150/year per user (academic) or ~$2,300+ per year (commercial).
- **Additional toolbox costs:** Specialized toolboxes (e.g., Signal Processing, Statistics) require extra licensing.
- **MATLAB Web App Server:** Deploying web-based MATLAB apps requires expensive enterprise licensing and infrastructure.
- **Upgrade and maintenance:** Ongoing subscription costs for updates and support.

---

### 4. **Maintainability and Code Quality**

#### Streamlit Advantages:
- **Unified codebase:** UI, logic, and data handling all in Python, reducing fragmentation.
- **Extensive documentation:** Streamlit has comprehensive guides, examples, and a large community.
- **Standard Python tools:** Can use linters, type checkers, version control, and CI/CD pipelines familiar to developers.
- **Easier troubleshooting:** Python stack traces and debugging are straightforward.

#### MATLAB Limitations:
- **Fragmented architecture:** MATLAB for computation + separate web framework for UI creates two codebases to maintain.
- **Limited ecosystem integration:** MATLAB doesn't integrate as smoothly with modern Python-based scientific tools.
- **Steeper learning curve:** Fewer developers are proficient in MATLAB compared to Python.
- **Debugging complexity:** Connecting MATLAB to external systems (databases, APIs) requires custom middleware.

---

### 5. **Real-Time Environmental Data Integration**

#### Streamlit Advantages:
- **Native API support:** Python's `requests` library makes fetching temperature/pressure from weather APIs trivial.
- **Automatic updates:** Streamlit reruns on user input, so live data is refreshed easily.
- **Fallback mechanisms:** Can seamlessly switch between live API and manual entry without UI complexity.
- **Data caching:** Built-in caching prevents excessive API calls.

#### MATLAB Limitations:
- **Cumbersome API integration:** MATLAB's built-in HTTP support is less intuitive than Python.
- **Manual refresh required:** Retrieving live data would require additional UI logic not native to MATLAB's calculator paradigm.
- **No built-in caching:** Implementing efficient data refresh strategies is manual and error-prone.

---

### 6. **Protocol Flexibility and Future Extensibility**

#### Streamlit Advantages:
- **Easy protocol switching:** TRS-398 and TG-51 modes are implemented with simple conditionals and dynamic form fields.
- **Formula versioning:** Formulas are stored as expressions in a database; updates don't require code recompilation.
- **Dataset-driven:** Chamber defaults, PDD tables, TPR tables, and kQ tables are all loaded from CSV datasets—easy to update without code changes.
- **Rapid iteration:** Changes to the calculator UI or formulas can be deployed in minutes.

#### MATLAB Limitations:
- **Code-based formulas:** Formulas hardcoded in MATLAB require recompilation and redeployment for changes.
- **Limited dataset flexibility:** Storing and switching between datasets is not as straightforward.
- **Slower deployment cycle:** Updates require rebuilding and redistributing compiled binaries.

---

### 7. **AI and Future Integration**

#### Streamlit Advantages:
- **Seamless AI integration:** Python ecosystem allows easy integration with LLMs, recommendation engines, and validation tools.
- **Data pipeline compatibility:** Works naturally with machine learning libraries (scikit-learn, TensorFlow) for future enhancements.
- **API ecosystem:** Easy to integrate with external services for validation, logging, or advanced analysis.

#### MATLAB Limitations:
- **Limited AI tooling:** MATLAB's deep learning support is less mature than Python's ecosystem.
- **Integration overhead:** Connecting MATLAB to external AI services requires custom middleware.

---

### 8. **User Experience and Responsiveness**

#### Streamlit Advantages:
- **Instant feedback:** Interactive widgets respond immediately; calculation results update in real-time.
- **Responsive design:** Built-in support for mobile-friendly layouts and modern UI patterns.
- **Forms and validation:** Native support for form submission, input validation, and error messages.
- **Export capabilities:** Easy to add CSV export, PDF generation, and print functionality.

#### MATLAB Limitations:
- **Limited UI responsiveness:** Desktop apps feel slower and less reactive than web apps.
- **Basic form support:** Creating a polished calculator interface requires significant custom GUI coding.
- **Export complexity:** Implementing CSV, PDF, and print features is manual.

---

## Summary Table

| Criterion | Streamlit | MATLAB |
|-----------|-----------|--------|
| **Deployment Model** | Web-based, browser access | Desktop, requires installation |
| **Cost per User** | Free to $50+/month | $2,150-$3,000+/year per seat |
| **Multi-user Support** | Native | Requires enterprise server ($$$) |
| **Admin Portal** | Integrated | Separate tool required |
| **API Integration** | Trivial (Python requests) | Cumbersome |
| **Maintainability** | Single Python codebase | Fragmented (MATLAB + web) |
| **Future-proofing** | Excellent (Python ecosystem) | Limited (MATLAB-centric) |
| **Deployment Speed** | Minutes (Streamlit Cloud) | Days/weeks (build & distribute) |
| **Collaboration** | Seamless (browser-based) | Difficult (desktop-based) |
| **Time to Production** | Weeks | Months |

---

## Main Justifications

- **Scalability:** Streamlit allows the system to be deployed as a web application, making it accessible to multiple users without requiring local MATLAB installations or duplicated desktop deployments.
- **Cost-effectiveness:** Eliminates expensive per-seat MATLAB licensing and infrastructure costs, reducing total cost of ownership.
- **Multi-user collaboration:** Built-in support for concurrent users, authentication, and role-based access control without additional infrastructure.
- **Admin integration:** Provides an integrated admin portal for dataset management, formula versioning, and audit trails—something MATLAB cannot do natively.
- **Future-proofing:** The framework makes it easier to adapt the system as technology evolves, including support for new protocols, updated formulas, and new system features.
- **AI integration:** Because Streamlit is Python-based, it can integrate easily with AI services such as large language models, recommendation engines, and automated validation tools.
- **Live environmental data:** Streamlit can connect to APIs to fetch real-time temperature and pressure based on the user's location, which is useful for dose calculations that depend on environmental conditions.
- **User overrides:** The platform supports both automatic API retrieval and manual override, which improves reliability when live data is unavailable or needs verification.
- **Interactive workflow:** Streamlit is well suited for calculator-style systems with protocol toggles, chamber selection, dynamic form fields, and instant output updates.
- **Maintainability:** Keeping the interface, logic, and API calls in one Python ecosystem simplifies maintenance compared with a MATLAB-centric implementation.
- **Extensibility:** The system can be expanded later with audit trails, dashboards, report exports, admin panels, and other features without major redesign.
- **Rapid deployment:** Changes and updates can be deployed instantly to all users without requiring software distribution or installations.

---

## Academic Wording
Streamlit was used because it offers a scalable, web-accessible platform for building scientific applications that is superior to MATLAB for collaborative, multi-user deployment scenarios. Unlike MATLAB, which is a desktop tool designed for individual researchers, Streamlit provides native support for concurrent users, integrated admin functionality, real-time data APIs, and cost-effective deployment. The Python-based ecosystem enables rapid development, seamless integration with modern AI services, and straightforward adaptation to evolving scientific requirements. This makes Streamlit fundamentally more suitable for a long-term, organization-wide system than a MATLAB-only implementation.

---

## Report Ready Version
The system was developed in Streamlit rather than MATLAB to provide a scalable, cost-effective, web-based architecture suitable for multi-user collaboration. Streamlit eliminates expensive per-seat licensing ($2,150+/year per user in MATLAB), enables instant browser-based deployment without local installations, and provides integrated admin functionality for dataset management and audit trails. Unlike MATLAB, which is designed for individual desktop use, Streamlit natively supports concurrent users, real-time environmental data retrieval from APIs, role-based access control, and rapid updates that are deployed instantly to all users. The Python ecosystem also simplifies integration with modern AI services and enables faster adaptation to future scientific and technological requirements. These factors combine to reduce both the cost of ownership and time-to-market while improving long-term maintainability and extensibility.

---

## Short Thesis Point
Streamlit was chosen because it eliminates MATLAB's costly licensing ($2,150+/year per user), enables web-based multi-user collaboration, integrates real-time environmental APIs natively, and provides a cost-effective path to scalable deployment while keeping the system adaptable to future advances in technology and scientific methodology.
