from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
SEED_DIR = DATA_DIR / "seed"
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
