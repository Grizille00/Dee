# Universal Absorbed Calculation System

Streamlit app for absorbed dose calculations with a public calculator and admin portal.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Default Admin Login

- Username: `admin` (only when no secrets/env override is provided)
- Password: `admin123` (development default)

Change credentials before production use.

## What It Does

- Public calculator landing page (no auth).
- Admin portal for environment settings, datasets, formulas, and run history.
- Uses fetched temperature/pressure values in calculations.

## Required Dataset Types

- `kq_table`
- `pdd_table`
- `tpr_table`
- `chamber_defaults`
- `environmental_data`

## Main Files

- `app.py`
- `pages/1_Calculator.py`
- `pages/9_Admin_Portal.py`
- `dosimetry_app/`

## Streamlit Community Deployment

1. Push this repository to GitHub.
2. Create a Streamlit Community Cloud app pointing to `app.py`.
3. In Streamlit Cloud `Secrets`, set:
   - `admin_username`
   - `admin_password`
4. Deploy.

Optional runtime overrides:
- `DOSIMETRY_DATA_DIR` can be set to control where DB/uploads are stored.
