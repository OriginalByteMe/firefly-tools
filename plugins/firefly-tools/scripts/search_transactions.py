#!/usr/bin/env python3
"""Search transactions with flexible filters.

Replaces MCP tool: search_transactions

Usage:
    python search_transactions.py --query "starbucks"
    python search_transactions.py --date-from 2026-01-01 --date-to 2026-01-31
    python search_transactions.py --category "Food & Dining" --amount-min 50
    python search_transactions.py --tag "subscription" --type withdrawal
    python search_transactions.py --account "HSBC Checking" --budget "Groceries"

Output: JSON array of compact transactions to stdout
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def build_search_query(
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    account: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    budget: str | None = None,
    type: str = "all",
) -> str:
    """Build Firefly III search query string from natural parameters."""
    parts: list[str] = []
    if query:
        parts.append(query)
    if date_from:
        parts.append(f"date_after:{date_from}")
    if date_to:
        parts.append(f"date_before:{date_to}")
    if amount_min is not None:
        parts.append(f"amount_more:{amount_min}")
    if amount_max is not None:
        parts.append(f"amount_less:{amount_max}")
    if account:
        parts.append(f'source_account_is:"{account}"')
    if category:
        parts.append(f'category_is:"{category}"')
    if tag:
        parts.append(f'tag_is:"{tag}"')
    if budget:
        parts.append(f'budget_is:"{budget}"')
    if type != "all":
        parts.append(f"type:{type}")
    return " ".join(parts)


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


def main():
    parser = argparse.ArgumentParser(description="Search Firefly III transactions")
    parser.add_argument("--query", "-q", help="Free-text description search")
    parser.add_argument("--date-from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="End date (YYYY-MM-DD)")
    parser.add_argument("--amount-min", type=float, help="Minimum amount")
    parser.add_argument("--amount-max", type=float, help="Maximum amount")
    parser.add_argument("--account", "-a", help="Source account name")
    parser.add_argument("--category", "-c", help="Category name")
    parser.add_argument("--tag", "-t", help="Tag name")
    parser.add_argument("--budget", "-b", help="Budget name")
    parser.add_argument(
        "--type",
        default="all",
        choices=["withdrawal", "deposit", "transfer", "all"],
        help="Transaction type (default: all)",
    )
    parser.add_argument("--limit", type=int, help="Max results to return")
    args = parser.parse_args()

    search_query = build_search_query(
        query=args.query,
        date_from=args.date_from,
        date_to=args.date_to,
        amount_min=args.amount_min,
        amount_max=args.amount_max,
        account=args.account,
        category=args.category,
        tag=args.tag,
        budget=args.budget,
        type=args.type,
    )

    if not search_query:
        output_error("At least one search filter is required.")

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    results: list[dict] = []
    page = 1

    while True:
        data = client.get("/search/transactions", params={"query": search_query, "page": page})
        for item in data.get("data", []):
            results.append(compact_transaction(item))

        total_pages = data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

        if args.limit and len(results) >= args.limit:
            results = results[: args.limit]
            break

    output_json({"transactions": results, "total": len(results), "query": search_query})


if __name__ == "__main__":
    main()
