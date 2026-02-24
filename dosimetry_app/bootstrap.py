from dosimetry_app.auth import ensure_default_admin
from dosimetry_app.config import DATA_DIR, UPLOAD_DIR
from dosimetry_app.database import init_db
from dosimetry_app.datasets import ensure_africa_environment_dataset, seed_builtin_datasets
from dosimetry_app.formulas import seed_default_formulas
from dosimetry_app.settings import apply_live_detection_defaults_for_legacy_installations, ensure_default_settings


def initialize_application() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    ensure_default_admin()
    ensure_default_settings()
    seed_builtin_datasets()
    ensure_africa_environment_dataset()
    apply_live_detection_defaults_for_legacy_installations()
    seed_default_formulas()
