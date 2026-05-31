"""Business configuration loading for the BLRPackworks demo."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "business_config.json"


@lru_cache(maxsize=1)
def load_business_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
