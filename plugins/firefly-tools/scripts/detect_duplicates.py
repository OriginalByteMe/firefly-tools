#!/usr/bin/env python3
"""Scan Firefly III for duplicate transactions.

New data processing script (not in MCP server).

Detects duplicates by matching: same date + similar amount + similar description.

Usage:
    python detect_duplicates.py                      # Last 30 days
    python detect_duplicates.py --days 90            # Last 90 days
    python detect_duplicates.py --strict             # Exact amount + description match only
    python detect_duplicates.py --auto-mark          # Add "possible-duplicate" tag

Output: JSON with duplicate groups
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


def normalize(desc: str) -> str:
    """Normalize description for comparison."""
    cleaned = desc.lower().strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[#\-/]\d{4,}", "", cleaned)
    return cleaned.strip()


def descriptions_similar(a: str, b: str, threshold: float = 0.7) -> bool:
    """Check if two descriptions are similar enough."""
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def main():
    parser = argparse.ArgumentParser(description="Detect duplicate transactions in Firefly III")
    parser.add_argument("--days", type=int, default=30, help="Days to scan (default: 30)")
    parser.add_argument("--strict", action="store_true",
                        help="Only flag exact matches (same date, amount, description)")
    parser.add_argument("--threshold", type=float, default=0.7,
                        help="Description similarity threshold 0-1 (default: 0.7)")
    parser.add_argument("--auto-mark", action="store_true",
                        help="Add 'possible-duplicate' tag to detected duplicates")
    args = parser.parse_args()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    end = date.today()
    start = end - timedelta(days=args.days)

    all_items = client.get_all_pages(
        "/transactions",
        params={"type": "all", "start": start.isoformat(), "end": end.isoformat()},
    )

    # Build transaction list
    txns = []
    for item in all_items:
        attrs = item["attributes"]["transactions"][0]
        txns.append({
            "id": int(item["id"]),
            "date": attrs["date"][:10],
            "amount": float(attrs["amount"]),
            "description": attrs["description"],
            "source_account": attrs.get("source_name", ""),
            "destination": attrs.get("destination_name", ""),
            "tags": attrs.get("tags", []),
        })

    # Group by (date, amount) to find candidates
    candidates: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for txn in txns:
        key = (txn["date"], round(txn["amount"], 2))
        candidates[key].append(txn)

    # Find duplicates
    duplicate_groups: list[dict] = []
    seen_ids: set[int] = set()

    for key, group in candidates.items():
        if len(group) < 2:
            continue

        # Within each (date, amount) group, cluster by description similarity
        clusters: list[list[dict]] = []
        for txn in group:
            if txn["id"] in seen_ids:
                continue
            matched = False
            for cluster in clusters:
                ref = cluster[0]
                if args.strict:
                    if normalize(txn["description"]) == normalize(ref["description"]):
                        cluster.append(txn)
                        matched = True
                        break
                else:
                    if descriptions_similar(txn["description"], ref["description"], args.threshold):
                        cluster.append(txn)
                        matched = True
                        break
            if not matched:
                clusters.append([txn])

        for cluster in clusters:
            if len(cluster) < 2:
                continue
            for txn in cluster:
                seen_ids.add(txn["id"])
            duplicate_groups.append({
                "date": key[0],
                "amount": key[1],
                "count": len(cluster),
                "transactions": [
                    {
                        "id": t["id"],
                        "description": t["description"],
                        "source_account": t["source_account"],
                        "destination": t["destination"],
                        "tags": t["tags"],
                    }
                    for t in cluster
                ],
            })

    # Auto-mark if requested
    marked = 0
    if args.auto_mark and duplicate_groups:
        for group in duplicate_groups:
            for txn in group["transactions"]:
                if "possible-duplicate" not in txn["tags"]:
                    new_tags = txn["tags"] + ["possible-duplicate"]
                    try:
                        client.put(
                            f"/transactions/{txn['id']}",
                            json_data={"transactions": [{"tags": new_tags}]},
                        )
                        marked += 1
                    except Exception:
                        pass

    result = {
        "duplicate_groups": duplicate_groups,
        "total_groups": len(duplicate_groups),
        "total_duplicate_transactions": sum(g["count"] for g in duplicate_groups),
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "transactions_scanned": len(txns),
    }

    if args.auto_mark:
        result["marked_with_tag"] = marked

    output_json(result)


if __name__ == "__main__":
    main()
