#!/usr/bin/env python3
"""Detect and normalize inconsistent merchant names across transactions.

New data processing script (not in MCP server).

Groups transactions by similar destination names and suggests consolidations.
For example, "GRAB*2847 KL", "GRAB*9182 PJ", and "GrabCar" would be grouped.

Usage:
    python normalize_merchants.py                      # Last 90 days
    python normalize_merchants.py --days 180           # Last 180 days
    python normalize_merchants.py --threshold 0.6      # Lower similarity threshold
    python normalize_merchants.py --apply              # Apply the suggested normalizations

Output: JSON with suggested merchant name consolidations
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def clean_merchant(name: str) -> str:
    """Clean a merchant name for comparison."""
    cleaned = name.lower().strip()
    # Remove reference numbers
    cleaned = re.sub(r"[*#]\d+", "", cleaned)
    # Remove trailing location codes
    cleaned = re.sub(r"\s+(kl|pj|sg|my|selangor|kuala\s*lumpur)\s*$", "", cleaned, flags=re.I)
    # Remove POS/VISA prefixes
    cleaned = re.sub(r"^(pos\s+debit|visa\s+pos|mst\s+|dbt\s+)\s*", "", cleaned, flags=re.I)
    # Remove trailing digits
    cleaned = re.sub(r"\s+\d{4,}$", "", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def names_similar(a: str, b: str, threshold: float) -> bool:
    """Check if two merchant names are similar."""
    ca, cb = clean_merchant(a), clean_merchant(b)
    if ca == cb:
        return True
    # Check prefix match (first word)
    wa = ca.split()[0] if ca else ""
    wb = cb.split()[0] if cb else ""
    if wa and wb and wa == wb and len(wa) >= 4:
        return True
    return SequenceMatcher(None, ca, cb).ratio() >= threshold


def choose_canonical(names: list[str]) -> str:
    """Choose the best canonical name from a group."""
    # Prefer the longest name that isn't full of numbers
    scored = []
    for name in names:
        # Penalize names with lots of digits/reference numbers
        digit_ratio = sum(c.isdigit() for c in name) / max(len(name), 1)
        # Prefer proper capitalization
        has_caps = any(c.isupper() for c in name[1:]) if len(name) > 1 else False
        score = len(name) - (digit_ratio * 50) + (10 if has_caps else 0)
        scored.append((score, name))
    scored.sort(reverse=True)
    return scored[0][1]


def main():
    parser = argparse.ArgumentParser(description="Normalize merchant names in Firefly III")
    parser.add_argument("--days", type=int, default=90, help="Days to analyze (default: 90)")
    parser.add_argument("--threshold", type=float, default=0.65,
                        help="Similarity threshold 0-1 (default: 0.65)")
    parser.add_argument("--min-transactions", type=int, default=2,
                        help="Minimum transactions per merchant group (default: 2)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply normalizations (update transaction descriptions)")
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

    # Collect all destination names with their transaction IDs
    dest_txns: dict[str, list[int]] = defaultdict(list)
    for item in all_items:
        attrs = item["attributes"]["transactions"][0]
        dest = attrs.get("destination_name", "")
        if dest:
            dest_txns[dest].append(int(item["id"]))

    # Group similar destination names
    unique_names = list(dest_txns.keys())
    groups: list[list[str]] = []
    used: set[str] = set()

    for i, name_a in enumerate(unique_names):
        if name_a in used:
            continue
        group = [name_a]
        used.add(name_a)
        for j in range(i + 1, len(unique_names)):
            name_b = unique_names[j]
            if name_b in used:
                continue
            if names_similar(name_a, name_b, args.threshold):
                group.append(name_b)
                used.add(name_b)
        if len(group) >= 2:
            groups.append(group)

    # Build consolidation suggestions
    suggestions: list[dict] = []
    for group in groups:
        total_txns = sum(len(dest_txns[name]) for name in group)
        if total_txns < args.min_transactions:
            continue

        canonical = choose_canonical(group)
        variants = [n for n in group if n != canonical]

        suggestion = {
            "canonical_name": canonical,
            "variants": variants,
            "total_transactions": total_txns,
            "variant_details": [
                {"name": v, "transaction_count": len(dest_txns[v])}
                for v in variants
            ],
        }
        suggestions.append(suggestion)

    suggestions.sort(key=lambda s: s["total_transactions"], reverse=True)

    # Apply normalizations if requested
    applied = 0
    if args.apply:
        for suggestion in suggestions:
            canonical = suggestion["canonical_name"]
            for variant in suggestion["variants"]:
                for txn_id in dest_txns[variant]:
                    try:
                        client.put(
                            f"/transactions/{txn_id}",
                            json_data={"transactions": [{"destination_name": canonical}]},
                        )
                        applied += 1
                    except Exception:
                        pass

    result = {
        "suggestions": suggestions,
        "total_groups": len(suggestions),
        "total_merchants_scanned": len(unique_names),
        "period": f"{start.isoformat()} to {end.isoformat()}",
    }

    if args.apply:
        result["applied"] = applied

    output_json(result)


if __name__ == "__main__":
    main()
