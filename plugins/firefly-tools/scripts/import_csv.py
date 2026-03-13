#!/usr/bin/env python3
"""Import a CSV bank statement into Firefly III via the Data Importer.

Replaces MCP tool: import_bank_statement

Usage:
    python import_csv.py /path/to/statement.csv                  # Auto-detect bank
    python import_csv.py /path/to/statement.csv --bank hsbc      # Specify bank
    python import_csv.py /path/to/statement.csv --bank maybank
    python import_csv.py /path/to/statement.csv --dry-run        # Validate only

Output: JSON with import result
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def find_configs_dir() -> Path:
    """Locate the bank config directory."""
    # Check relative to this script (scripts/../../../src/firefly_mcp/configs/)
    script_dir = Path(__file__).resolve().parent
    # Configs are in the MCP server source
    configs = script_dir.parent.parent.parent / "src" / "firefly_mcp" / "configs"
    if configs.exists():
        return configs
    # Also check plugin root level
    configs = script_dir.parent / "configs"
    if configs.exists():
        return configs
    raise FileNotFoundError(
        f"Bank config directory not found. Checked:\n"
        f"  - {script_dir.parent.parent.parent / 'src' / 'firefly_mcp' / 'configs'}\n"
        f"  - {script_dir.parent / 'configs'}"
    )


def detect_bank(csv_text: str) -> str:
    """Auto-detect bank from CSV content."""
    lower = csv_text[:500].lower()
    if "maybank" in lower:
        return "maybank"
    return "hsbc"


def main():
    parser = argparse.ArgumentParser(description="Import a CSV bank statement into Firefly III")
    parser.add_argument("csv_path", help="Path to the CSV file")
    parser.add_argument("--bank", default="auto", choices=["auto", "hsbc", "maybank"],
                        help="Bank name or 'auto' to detect (default: auto)")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't import")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        output_error(f"File not found: {args.csv_path}")

    csv_bytes = csv_path.read_bytes()
    csv_text = csv_bytes.decode("utf-8", errors="replace")

    bank = args.bank
    if bank == "auto":
        bank = detect_bank(csv_text)

    try:
        configs_dir = find_configs_dir()
    except FileNotFoundError as e:
        output_error(str(e))

    config_path = configs_dir / f"{bank}.json"
    if not config_path.exists():
        available = [p.stem for p in configs_dir.glob("*.json")]
        output_error(f"No config for bank '{bank}'. Available: {', '.join(available)}")

    config_json = config_path.read_text()
    line_count = len(csv_text.strip().splitlines()) - 1  # Minus header

    if args.dry_run:
        output_json({
            "dry_run": True,
            "file": csv_path.name,
            "bank": bank,
            "rows": line_count,
            "message": f"Would import {line_count} row(s) from '{csv_path.name}' using {bank} config.",
        })
        return

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    try:
        result_text = client.upload_csv(csv_bytes, config_json)
    except Exception as e:
        output_error(f"Import failed: {e}")

    output_json({
        "file": csv_path.name,
        "bank": bank,
        "rows": line_count,
        "result": result_text,
    })


if __name__ == "__main__":
    main()
