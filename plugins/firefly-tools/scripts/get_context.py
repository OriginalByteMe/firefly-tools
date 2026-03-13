#!/usr/bin/env python3
"""Fetch financial context: categories, tags, budgets, accounts, bills.

Replaces MCP tool: get_financial_context

Usage:
    python get_context.py                  # Fetch everything
    python get_context.py --what categories # Fetch only categories
    python get_context.py --what budgets    # Fetch only budgets
    python get_context.py --cache           # Use cached result if <5min old

Output: JSON to stdout
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


CACHE_DIR = Path(tempfile.gettempdir()) / "firefly-cowork-cache"
CACHE_TTL = 300  # 5 minutes


def _cache_key(what: str) -> Path:
    """Generate a cache file path for a given query."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"context_{what}.json"


def _read_cache(what: str) -> dict | None:
    """Read cached data if it exists and is fresh."""
    path = _cache_key(what)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL:
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(what: str, data: dict) -> None:
    """Write data to cache."""
    try:
        path = _cache_key(what)
        path.write_text(json.dumps(data, default=str))
    except OSError:
        pass  # Cache is best-effort


def fetch_tags(client) -> list[dict]:
    data = client.get("/tags")
    return [{"id": int(t["id"]), "name": t["attributes"]["tag"]} for t in data.get("data", [])]


def fetch_categories(client) -> list[dict]:
    data = client.get("/categories")
    return [{"id": int(c["id"]), "name": c["attributes"]["name"]} for c in data.get("data", [])]


def fetch_budgets(client) -> list[dict]:
    data = client.get("/budgets")
    results = []
    for b in data.get("data", []):
        attrs = b["attributes"]
        entry = {"id": int(b["id"]), "name": attrs["name"]}
        if attrs.get("auto_budget_amount"):
            entry["auto_budget_amount"] = attrs["auto_budget_amount"]
            entry["auto_budget_period"] = attrs.get("auto_budget_period", "monthly")
        results.append(entry)
    return results


def fetch_accounts(client) -> list[dict]:
    data = client.get("/accounts", params={"type": "asset"})
    return [
        {
            "id": int(a["id"]),
            "name": a["attributes"]["name"],
            "type": a["attributes"]["type"],
            "balance": a["attributes"].get("current_balance"),
            "currency": a["attributes"].get("currency_code"),
        }
        for a in data.get("data", [])
    ]


def fetch_bills(client) -> list[dict]:
    data = client.get("/bills")
    return [
        {
            "id": int(b["id"]),
            "name": b["attributes"]["name"],
            "amount_min": b["attributes"].get("amount_min"),
            "amount_max": b["attributes"].get("amount_max"),
            "repeat_freq": b["attributes"].get("repeat_freq"),
        }
        for b in data.get("data", [])
    ]


FETCHERS = {
    "tags": fetch_tags,
    "categories": fetch_categories,
    "budgets": fetch_budgets,
    "accounts": fetch_accounts,
    "bills": fetch_bills,
}


def main():
    parser = argparse.ArgumentParser(description="Fetch Firefly III financial context")
    parser.add_argument(
        "--what",
        default="all",
        choices=["all", "tags", "categories", "budgets", "accounts", "bills"],
        help="What to fetch (default: all)",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Use cached results if available and <5min old",
    )
    args = parser.parse_args()

    if args.cache:
        cached = _read_cache(args.what)
        if cached:
            output_json(cached)
            return

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    result: dict = {}

    if args.what == "all":
        for key, fetcher in FETCHERS.items():
            result[key] = fetcher(client)
    else:
        result[args.what] = FETCHERS[args.what](client)

    if args.cache:
        _write_cache(args.what, result)

    output_json(result)


if __name__ == "__main__":
    main()
