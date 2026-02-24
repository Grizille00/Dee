# Universal Absorbed Calculation System

Streamlit app for absorbed dose calculations with a public calculator and admin portal.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Default Admin Login

- Username: `admin`
- Password: `admin123`

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
