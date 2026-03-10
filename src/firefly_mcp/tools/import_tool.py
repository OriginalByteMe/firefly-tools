from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient

CONFIGS_DIR = Path(__file__).parent.parent / "configs"

BANK_CONFIGS = {
    "hsbc": CONFIGS_DIR / "hsbc.json",
    "maybank": CONFIGS_DIR / "maybank.json",
}


def _detect_bank(csv_text: str) -> str:
    """Auto-detect bank from CSV content. Falls back to hsbc."""
    lower = csv_text[:500].lower()
    if "maybank" in lower:
        return "maybank"
    return "hsbc"


async def import_bank_statement(
    csv_path: Annotated[str, Field(description="Absolute path to the CSV file to import")],
    bank: Annotated[str, Field(description="Bank name: 'hsbc', 'maybank', or 'auto' to detect")] = "auto",
    dry_run: Annotated[bool, Field(description="If true, validate only without importing")] = False,
    *,
    client: FireflyClient,
) -> str:
    """Import a CSV bank statement into Firefly III via the Data Importer."""
    path = Path(csv_path)
    if not path.exists():
        return f"Error: File not found: {csv_path}"

    csv_bytes = path.read_bytes()
    csv_text = csv_bytes.decode("utf-8", errors="replace")

    if bank == "auto":
        bank = _detect_bank(csv_text)

    config_path = BANK_CONFIGS.get(bank)
    if config_path is None:
        return f"Error: Unknown bank '{bank}'. Available: {', '.join(BANK_CONFIGS)}"

    if not config_path.exists():
        return f"Error: Config file not found: {config_path}"

    config_json = config_path.read_text()

    if dry_run:
        line_count = len(csv_text.strip().splitlines()) - 1
        return (
            f"Dry run: Would import {line_count} row(s) from '{path.name}' "
            f"using {bank} config. No data sent."
        )

    result = await client.upload_csv(csv_bytes, config_json)
    return f"Import result ({bank}, {path.name}):\n{result}"
