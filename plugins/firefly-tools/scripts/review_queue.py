#!/usr/bin/env python3
"""Fetch transactions needing review (missing categories, tags, or budgets).

Replaces MCP tool: get_review_queue

Usage:
    python review_queue.py                          # Last 30 days, all unreviewed
    python review_queue.py --days 7                  # Last 7 days
    python review_queue.py --filter uncategorized    # Only missing categories
    python review_queue.py --filter untagged         # Only missing tags
    python review_queue.py --filter unbudgeted       # Only missing budgets

Output: JSON array of transactions needing review
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def compact_transaction(data: dict) -> dict:
    """Extract compact transaction info from API response."""
    attrs = data["attributes"]["transactions"][0]
    return {
        "id": int(data["id"]),
        "date": attrs["date"][:10],
        "amount": float(attrs["amount"]),
        "description": attrs["description"],
        "source_account": attrs.get("source_name", ""),
        "destination": attrs.get("destination_name", ""),
        "category": attrs.get("category_name"),
        "budget": attrs.get("budget_name"),
        "tags": attrs.get("tags", []),
        "notes": attrs.get("notes"),
    }


def needs_review(txn: dict, filter_type: str) -> bool:
    """Check if a transaction matches the review filter."""
    if filter_type == "untagged":
        return len(txn["tags"]) == 0
    if filter_type == "uncategorized":
        return txn["category"] is None
    if filter_type == "unbudgeted":
        return txn["budget"] is None
    # all_unreviewed: missing any metadata
    return len(txn["tags"]) == 0 or txn["category"] is None or txn["budget"] is None


def main():
    parser = argparse.ArgumentParser(description="Fetch Firefly III review queue")
    parser.add_argument("--days", type=int, default=30, help="Days to look back (default: 30)")
    parser.add_argument(
        "--filter",
        default="all_unreviewed",
        choices=["untagged", "uncategorized", "unbudgeted", "all_unreviewed"],
        help="Filter type (default: all_unreviewed)",
    )
    args = parser.parse_args()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    end = date.today()
    start = end - timedelta(days=args.days)

    all_items = client.get_all_pages(
        "/transactions",
        params={"type": "withdrawal", "start": start.isoformat(), "end": end.isoformat()},
    )

    results = []
    for item in all_items:
        txn = compact_transaction(item)
        if needs_review(txn, args.filter):
            results.append(txn)

    output_json({
        "transactions": results,
        "total": len(results),
        "filter": args.filter,
        "period": f"{start.isoformat()} to {end.isoformat()}",
    })


if __name__ == "__main__":
    main()
