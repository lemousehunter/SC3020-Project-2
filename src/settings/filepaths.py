import os
from pathlib import Path

# DIR
SRC_DIR = Path(os.path.abspath(Path(os.path.abspath(os.path.dirname(os.path.abspath(__file__)))).parent))
ROOT_DIR = SRC_DIR.parent
DATA_DIR = ROOT_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
SETTINGS_DIR = SRC_DIR / "settings"
VIZ_DIR = ROOT_DIR / "vizualizations"

# FILEPATH
DB_SETTINGS_PATH = SETTINGS_DIR / "db_settings.json"
