import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_data_dir() -> Path:
    override = os.getenv("DOSIMETRY_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return BASE_DIR / "data"


DATA_DIR = _resolve_data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
SEED_DIR = BASE_DIR / "data" / "seed"
DB_PATH = DATA_DIR / "app.db"

DEFAULT_T0_C = 20.0
DEFAULT_P0_KPA = 101.325

SUPPORTED_DATASET_TYPES = (
    "kq_table",
    "pdd_table",
    "tpr_table",
    "chamber_defaults",
    "environmental_data",
)
