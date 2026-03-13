#!/usr/bin/env python3
"""Export transactions to CSV or JSON for external analysis.

New data processing script (not in MCP server).

Usage:
    python export_transactions.py --date-from 2026-01-01 --date-to 2026-01-31
    python export_transactions.py --date-from 2026-01-01 --date-to 2026-01-31 --format csv --output report.csv
    python export_transactions.py --type withdrawal --category "Food & Dining" --format csv
    python export_transactions.py --all --format json --output all_transactions.json

Output: CSV or JSON to file or stdout
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error


def compact_transaction(data: dict) -> dict:
    """Extract full transaction info for export."""
    attrs = data["attributes"]["transactions"][0]
    return {
        "id": int(data["id"]),
        "date": attrs["date"][:10],
        "amount": float(attrs["amount"]),
        "description": attrs["description"],
        "source_account": attrs.get("source_name", ""),
        "destination": attrs.get("destination_name", ""),
        "type": attrs.get("type", ""),
        "category": attrs.get("category_name", ""),
        "budget": attrs.get("budget_name", ""),
        "tags": ", ".join(attrs.get("tags", [])),
        "notes": attrs.get("notes", "") or "",
        "currency": attrs.get("currency_code", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="Export Firefly III transactions")
    parser.add_argument("--date-from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="End date (YYYY-MM-DD)")
    parser.add_argument("--type", default="all", choices=["withdrawal", "deposit", "transfer", "all"])
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument("--account", help="Filter by account")
    parser.add_argument("--all", action="store_true", help="Export all transactions (last 365 days)")
    parser.add_argument("--format", default="csv", choices=["csv", "json"], help="Output format")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    args = parser.parse_args()

    if args.all:
        args.date_from = (date.today() - timedelta(days=365)).isoformat()
        args.date_to = date.today().isoformat()

    if not args.date_from:
        output_error("--date-from is required (or use --all)")

    if not args.date_to:
        args.date_to = date.today().isoformat()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    # Build search query for filtered exports
    if args.category or args.tag or args.account:
        # Use search API for filtered queries
        parts: list[str] = []
        parts.append(f"date_after:{args.date_from}")
        parts.append(f"date_before:{args.date_to}")
        if args.category:
            parts.append(f'category_is:"{args.category}"')
        if args.tag:
            parts.append(f'tag_is:"{args.tag}"')
        if args.account:
            parts.append(f'source_account_is:"{args.account}"')
        if args.type != "all":
            parts.append(f"type:{args.type}")
        query = " ".join(parts)

        all_items = []
        page = 1
        while True:
            data = client.get("/search/transactions", params={"query": query, "page": page})
            all_items.extend(data.get("data", []))
            total_pages = data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
    else:
        # Use list API for unfiltered date-range exports
        txn_type = "all" if args.type == "all" else args.type
        all_items = client.get_all_pages(
            "/transactions",
            params={"type": txn_type, "start": args.date_from, "end": args.date_to},
        )

    transactions = [compact_transaction(item) for item in all_items]

    if args.format == "json":
        output = json.dumps(transactions, indent=2, default=str)
    else:
        buf = io.StringIO()
        if transactions:
            writer = csv.DictWriter(buf, fieldnames=transactions[0].keys())
            writer.writeheader()
            writer.writerows(transactions)
        output = buf.getvalue()

    if args.output:
        Path(args.output).write_text(output)
        print(json.dumps({
            "exported": len(transactions),
            "format": args.format,
            "file": args.output,
        }))
    else:
        print(output)


if __name__ == "__main__":
    main()
