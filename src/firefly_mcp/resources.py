from __future__ import annotations

import json
from pathlib import Path

CONFIGS_DIR = Path(__file__).parent / "configs"


def get_bank_config(bank: str) -> str:
    """Read and return the Data Importer config for a bank."""
    config_path = CONFIGS_DIR / f"{bank}.json"
    if not config_path.exists():
        available = [p.stem for p in CONFIGS_DIR.glob("*.json")]
        return json.dumps({"error": f"Unknown bank '{bank}'", "available": available})
    return config_path.read_text()
