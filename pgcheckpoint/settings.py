"""Caminhos e constantes compartilhadas."""

import re
from pathlib import Path

# Raiz do projeto (pasta que contem o pacote pgcheckpoint/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = PROJECT_ROOT / ".pgcheckpoint"
CONFIG_FILE = BASE_DIR / "config.json"
DUMPS_DIR = BASE_DIR / "dumps"

ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
CONFIG_VERSION = 1
SUBPROCESS_TIMEOUT = 3600  # 1 hora


def ensure_dirs() -> None:
    BASE_DIR.mkdir(exist_ok=True)
    DUMPS_DIR.mkdir(exist_ok=True)
