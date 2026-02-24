# Dosimetry Streamlit Project

Streamlit app with:
- Calculator interface for photon/electron dose workflows (`Universal Absorbed Calculation System`).
- Admin portal to upload/version/activate datasets.
- Admin portal to create/version/activate formulas.
- Audit history of all calculator runs.
- Admin-managed environmental source modes: dataset-based or auto-detected live weather.
- Responsive UI theme loaded from `style.css` for desktop and mobile.

## Quick start

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Run app:

```powershell
streamlit run app.py
```

3. Public calculator opens as landing page (no login required).

4. Admin portal login (from `Open Admin Portal` button):
- Username: `admin`
- Password: `admin123`

## GitHub publish prep

1. Ensure local runtime files are not committed (`data/app.db`, `data/uploads/*`).
2. Run tests before pushing:

```powershell
python -m unittest discover -s tests -v
```

3. Follow the step-by-step publish commands in `PUBLISHING.md`.

## Project layout

- `app.py`: Landing redirect to calculator.
- `pages/1_Calculator.py`: Main calculator interface.
- `pages/2_Admin_Datasets.py`: Dataset upload/activation + environmental source settings.
- `pages/3_Admin_Formulas.py`: Formula manager.
- `pages/4_Run_History.py`: Audit log viewer.
- `pages/9_Admin_Portal.py`: Login-gated admin entry page.
- `dosimetry_app/`: Core backend modules.
- `data/seed/`: Seed datasets auto-loaded on first boot.
- `style.css`: Global Streamlit UI styles/colors.

## Supported datasets

- `kq_table` columns: `chamber_type, beam_quality, kq`
- `pdd_table` columns: `energy_mv, field_size_cm, depth_cm, value`
- `tpr_table` columns: `energy_mv, field_size_cm, depth_cm, value`
- `chamber_defaults` columns: `chamber_type, ndw_60co, rcav_cm, reference_polarity`
- `environmental_data` columns: `location, temperature_c, pressure_kpa`

## Notes

- This implementation is an engineering scaffold for your project specification.
- Clinical use requires protocol-level physics validation and institutional QA sign-off.
- Default admin credentials are included for local demo setup; change them before public/production deployment.
- Auto weather mode uses `ipapi.co` (IP geolocation) and `open-meteo.com` (current weather).
- Temperature/pressure source is configured in `Admin - Datasets`; Calculator reads that setting.
- Default configuration is `Auto (IP + Weather API)` with live location detection.
- The built-in environmental seed covers many African locations and supports case-insensitive/partial location matching.
- In `Calculator`, when auto mode is enabled, browser geolocation is requested automatically on page load.
- Calculator header shows current location, temperature, and pressure with a single `Use My Location` button (also used to refresh).
- Fetched temperature/pressure values are applied directly to calculation; no manual temperature/pressure typing is required.
- If live weather fetch is unavailable, calculation is blocked until live/dataset environmental values are available (no manual fallback values).
- Calculation details are rendered as light key-value cards (instead of dark table/json widgets).
- Environment details emphasize location/conditions (city and country) and hide provider/internal source metadata.
- Calculator UX is simplified and minimal: core inputs first, optional advanced settings collapsed by default.
- Streamlit sidebar is permanently hidden; navigation is done with in-page buttons.
- Admin experience is consolidated into a single tabbed portal page for settings and info management.
