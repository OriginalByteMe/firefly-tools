#!/usr/bin/env python3
"""Discover recurring transactions (subscriptions, bills, regular payments).

Replaces MCP tool: discover_recurring

Usage:
    python discover_recurring.py                        # 180 days, min 3 occurrences
    python discover_recurring.py --days 365             # Full year
    python discover_recurring.py --min-occurrences 2    # Lower threshold
    python discover_recurring.py --no-bills-only        # Only show items without bills

Output: JSON with recurring transaction groups
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def normalize_description(desc: str) -> str:
    """Normalize a transaction description for grouping."""
    cleaned = re.sub(r"\s*[-/]\s*\d{6,}$", "", desc)
    cleaned = re.sub(r"\s*#\d+$", "", cleaned)
    cleaned = re.sub(r"\s+\d{2,4}[/-]\d{2,4}([/-]\d{2,4})?$", "", cleaned)
    return cleaned.strip().lower()


def detect_frequency(dates: list[date]) -> dict | None:
    """Detect the most likely frequency from transaction dates."""
    if len(dates) < 2:
        return None

    sorted_dates = sorted(dates)
    gaps = [(sorted_dates[i + 1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)]
    if not gaps:
        return None

    avg_gap = sum(gaps) / len(gaps)
    median_gap = sorted(gaps)[len(gaps) // 2]

    freq_map = [
        (5, 10, "weekly", 7),
        (12, 18, "biweekly", 14),
        (25, 35, "monthly", 30),
        (55, 70, "bimonthly", 60),
        (80, 100, "quarterly", 91),
        (170, 195, "half-yearly", 182),
        (350, 380, "yearly", 365),
    ]

    freq = None
    expected_gap = None
    for low, high, name, expected in freq_map:
        if low <= median_gap <= high:
            freq = name
            expected_gap = expected
            break

    if freq is None:
        return None

    close_gaps = sum(1 for g in gaps if abs(g - expected_gap) <= expected_gap * 0.35)
    if close_gaps < len(gaps) * 0.5:
        return None

    return {
        "frequency": freq,
        "avg_gap_days": round(avg_gap, 1),
        "median_gap_days": median_gap,
        "consistency": round(close_gaps / len(gaps), 2),
    }


def compact_transaction(data: dict) -> dict:
    """Extract compact transaction info."""
    attrs = data["attributes"]["transactions"][0]
    return {
        "id": int(data["id"]),
        "date": attrs["date"][:10],
        "amount": float(attrs["amount"]),
        "description": attrs["description"],
        "destination": attrs.get("destination_name", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="Discover recurring transactions")
    parser.add_argument("--days", type=int, default=180, help="Days of history to analyze (default: 180)")
    parser.add_argument("--min-occurrences", type=int, default=3, help="Minimum repetitions (default: 3)")
    parser.add_argument("--no-bills-only", action="store_true", help="Only show items without existing bills")
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

    txns = [compact_transaction(item) for item in all_items]

    # Group by normalized description
    groups: dict[str, list[dict]] = defaultdict(list)
    for txn in txns:
        key = normalize_description(txn["description"])
        groups[key].append(txn)

    # Detect recurring patterns
    recurring: list[dict] = []
    for key, group_txns in groups.items():
        if len(group_txns) < args.min_occurrences:
            continue

        dates = [date.fromisoformat(t["date"]) for t in group_txns]
        freq_info = detect_frequency(dates)
        if freq_info is None:
            continue

        amounts = [t["amount"] for t in group_txns]
        avg_amount = sum(amounts) / len(amounts)
        amount_variance = max(amounts) - min(amounts)
        is_fixed = amount_variance <= avg_amount * 0.1

        latest = max(group_txns, key=lambda t: t["date"])
        sorted_by_date = sorted(group_txns, key=lambda t: t["date"])

        recurring.append({
            "description": latest["description"],
            "normalized_key": key,
            "occurrences": len(group_txns),
            "frequency": freq_info["frequency"],
            "avg_amount": round(avg_amount, 2),
            "amount_range": {"min": min(amounts), "max": max(amounts)},
            "fixed_amount": is_fixed,
            "consistency": freq_info["consistency"],
            "avg_gap_days": freq_info["avg_gap_days"],
            "first_seen": sorted_by_date[0]["date"],
            "last_seen": sorted_by_date[-1]["date"],
            "destination": latest["destination"],
            "has_bill": False,
            "sample_transaction_ids": [t["id"] for t in sorted_by_date[-3:]],
        })

    recurring.sort(key=lambda r: r["occurrences"], reverse=True)

    # Check for existing bills
    bills_data = client.get("/bills")
    bill_names = {b["attributes"]["name"].lower() for b in bills_data.get("data", [])}
    for item in recurring:
        if item["normalized_key"] in bill_names or item["destination"].lower() in bill_names:
            item["has_bill"] = True

    if args.no_bills_only:
        recurring = [r for r in recurring if not r["has_bill"]]

    output_json({
        "recurring": recurring,
        "total_found": len(recurring),
        "period_analyzed": {"start": start.isoformat(), "end": end.isoformat()},
        "total_transactions_scanned": len(txns),
    })


if __name__ == "__main__":
    main()
