#!/usr/bin/env python3
"""Pre-validate a CSV file before importing into Firefly III.

New data processing script (not in MCP server).

Checks:
- Date format parsing
- Amount parsing (handles various formats)
- Duplicate detection against existing transactions
- Column structure validation
- Empty/malformed rows

Usage:
    python validate_import.py /path/to/statement.csv
    python validate_import.py /path/to/statement.csv --bank hsbc
    python validate_import.py /path/to/statement.csv --check-duplicates   # Check against Firefly
    python validate_import.py /path/to/statement.csv --check-duplicates --days 30

Output: JSON validation report
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def parse_date(value: str) -> str | None:
    """Try to parse a date string in common formats."""
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
        "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%Y%m%d",
    ]
    for fmt in formats:
        try:
            from datetime import datetime
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_amount(value: str) -> float | None:
    """Try to parse an amount string."""
    cleaned = value.strip()
    # Remove currency symbols and thousands separators
    cleaned = re.sub(r"[^\d.,\-+]", "", cleaned)
    # Handle European format (1.234,56)
    if "," in cleaned and "." in cleaned:
        if cleaned.rindex(",") > cleaned.rindex("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Could be 1,234 or 1,23 — check decimal places after comma
        after_comma = cleaned.split(",")[-1]
        if len(after_comma) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def validate_csv(csv_text: str) -> dict:
    """Validate CSV structure and content."""
    issues: list[dict] = []
    warnings: list[dict] = []
    stats = {"total_rows": 0, "valid_rows": 0, "date_errors": 0, "amount_errors": 0, "empty_rows": 0}

    reader = csv.reader(io.StringIO(csv_text))
    try:
        header = next(reader)
    except StopIteration:
        return {"valid": False, "issues": [{"row": 0, "type": "empty_file", "message": "File is empty"}]}

    stats["columns"] = len(header)
    stats["header"] = header

    # Try to identify date and amount columns
    date_col = None
    amount_col = None
    desc_col = None

    for i, col in enumerate(header):
        lower = col.strip().lower()
        if any(k in lower for k in ["date", "datum", "tarikh"]):
            date_col = i
        elif any(k in lower for k in ["amount", "sum", "jumlah", "debit"]):
            amount_col = i
        elif any(k in lower for k in ["description", "desc", "particular", "details", "narrative"]):
            desc_col = i

    dates_seen: list[str] = []
    amounts_seen: list[float] = []

    for row_num, row in enumerate(reader, start=2):
        stats["total_rows"] += 1

        if not any(cell.strip() for cell in row):
            stats["empty_rows"] += 1
            warnings.append({"row": row_num, "type": "empty_row", "message": "Empty row"})
            continue

        if len(row) != len(header):
            issues.append({
                "row": row_num,
                "type": "column_mismatch",
                "message": f"Expected {len(header)} columns, got {len(row)}",
            })

        # Validate date
        if date_col is not None and date_col < len(row):
            parsed = parse_date(row[date_col])
            if parsed is None and row[date_col].strip():
                stats["date_errors"] += 1
                issues.append({
                    "row": row_num,
                    "type": "date_error",
                    "message": f"Cannot parse date: '{row[date_col]}'",
                })
            elif parsed:
                dates_seen.append(parsed)

        # Validate amount
        if amount_col is not None and amount_col < len(row):
            parsed_amt = parse_amount(row[amount_col])
            if parsed_amt is None and row[amount_col].strip():
                stats["amount_errors"] += 1
                issues.append({
                    "row": row_num,
                    "type": "amount_error",
                    "message": f"Cannot parse amount: '{row[amount_col]}'",
                })
            elif parsed_amt is not None:
                amounts_seen.append(parsed_amt)

        if not issues or issues[-1]["row"] != row_num:
            stats["valid_rows"] += 1

    # Summary stats
    if dates_seen:
        stats["date_range"] = {"min": min(dates_seen), "max": max(dates_seen)}
    if amounts_seen:
        stats["amount_range"] = {"min": min(amounts_seen), "max": max(amounts_seen)}
        stats["total_amount"] = round(sum(amounts_seen), 2)

    stats["detected_columns"] = {
        "date": date_col,
        "amount": amount_col,
        "description": desc_col,
    }

    return {
        "valid": len(issues) == 0,
        "stats": stats,
        "issues": issues[:50],  # Cap at 50 to avoid huge output
        "warnings": warnings[:20],
        "issue_count": len(issues),
        "warning_count": len(warnings),
    }


def check_duplicates(client, csv_text: str, days: int = 30) -> list[dict]:
    """Check for potential duplicates against existing Firefly transactions."""
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)

    # Detect columns
    date_col = amount_col = desc_col = None
    for i, col in enumerate(header):
        lower = col.strip().lower()
        if any(k in lower for k in ["date", "datum"]):
            date_col = i
        elif any(k in lower for k in ["amount", "sum", "debit"]):
            amount_col = i
        elif any(k in lower for k in ["description", "desc", "particular", "narrative"]):
            desc_col = i

    if date_col is None or amount_col is None:
        return []

    # Fetch existing transactions
    end = date.today()
    start = end - timedelta(days=days)
    existing = client.get_all_pages(
        "/transactions",
        params={"type": "all", "start": start.isoformat(), "end": end.isoformat()},
    )

    # Build lookup of (date, amount) -> description
    existing_set: dict[tuple[str, float], list[str]] = {}
    for item in existing:
        attrs = item["attributes"]["transactions"][0]
        key = (attrs["date"][:10], abs(float(attrs["amount"])))
        existing_set.setdefault(key, []).append(attrs["description"])

    duplicates = []
    for row_num, row in enumerate(reader, start=2):
        if date_col >= len(row) or amount_col >= len(row):
            continue
        parsed_date = parse_date(row[date_col])
        parsed_amount = parse_amount(row[amount_col])
        if parsed_date and parsed_amount is not None:
            key = (parsed_date, abs(parsed_amount))
            if key in existing_set:
                desc = row[desc_col] if desc_col and desc_col < len(row) else ""
                duplicates.append({
                    "csv_row": row_num,
                    "date": parsed_date,
                    "amount": parsed_amount,
                    "csv_description": desc,
                    "existing_descriptions": existing_set[key],
                })

    return duplicates


def main():
    parser = argparse.ArgumentParser(description="Validate a CSV before importing to Firefly III")
    parser.add_argument("csv_path", help="Path to the CSV file")
    parser.add_argument("--check-duplicates", action="store_true", help="Check for duplicates in Firefly")
    parser.add_argument("--days", type=int, default=30, help="Days to check for duplicates (default: 30)")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        output_error(f"File not found: {args.csv_path}")

    csv_text = csv_path.read_text(errors="replace")
    result = validate_csv(csv_text)

    if args.check_duplicates:
        try:
            client = get_client()
            dupes = check_duplicates(client, csv_text, days=args.days)
            result["potential_duplicates"] = dupes
            result["duplicate_count"] = len(dupes)
        except (FileNotFoundError, ValueError) as e:
            result["duplicate_check_error"] = str(e)

    output_json(result)


if __name__ == "__main__":
    main()
