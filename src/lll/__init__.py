"""Lead Line Lens: decode a water utility's lead service line inventory."""

import os
from pathlib import Path

__version__ = "0.1.0"

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("LLL_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = Path(os.environ.get("LLL_MODEL_DIR", REPO_ROOT / "models"))
TEMPLATE_DIR = Path(os.environ.get("LLL_TEMPLATE_DIR", REPO_ROOT / "templates"))

METHODOLOGY_URL = "https://github.com/prad101/lead-line-lens/blob/main/docs/methodology.md"
MODEL_CARD_URL = "https://github.com/prad101/lead-line-lens/blob/main/docs/model_card.md"
