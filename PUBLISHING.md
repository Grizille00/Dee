# Publish To GitHub

## 1. Pre-publish checklist

1. Run tests:

```powershell
python -m unittest discover -s tests -v
```

2. Confirm local runtime files are not tracked:
- `data/app.db`
- `data/uploads/*`
- any `__pycache__` or `.pyc` files

3. If this repo is public, change default admin credentials in app code and README.

## 2. Initialize git locally (first time only)

```powershell
git init
git add .
git commit -m "Initial commit"
```

## 3. Create a GitHub repository

1. Create an empty repository on GitHub (no README, no .gitignore, no license).
2. Copy the repository URL.

## 4. Push to GitHub

```powershell
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## 5. Optional: protect secrets and production setup

1. Replace demo admin password logic before production deployment.
2. Add CI for tests/linting.
3. Add a license file if needed for public distribution.

## 6. Deploy to Streamlit Community Cloud

1. Go to Streamlit Community Cloud and create a new app from this GitHub repo.
2. Set `app.py` as the entrypoint.
3. In app Secrets, set:
   - `admin_username`
   - `admin_password`
4. Deploy and verify calculator and admin portal access.
