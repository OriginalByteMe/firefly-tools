#!/usr/bin/env python3
"""Batch-apply categories, tags, budgets, and notes to transactions.

Replaces MCP tool: categorize_transactions

Usage:
    # From a JSON file:
    python categorize.py --file updates.json

    # From stdin (pipe from another script):
    echo '[{"transaction_id": 123, "category": "Food"}]' | python categorize.py --stdin

    # Dry run (show what would change):
    python categorize.py --file updates.json --dry-run

    # Single transaction inline:
    python categorize.py --id 123 --category "Food & Dining" --tags "restaurant,lunch" --budget "Eating Out"

JSON format for --file or --stdin:
[
    {
        "transaction_id": 123,
        "category": "Food & Dining",
        "tags": ["restaurant", "lunch"],
        "budget": "Eating Out",
        "notes": "Team lunch"
    }
]

Output: JSON summary of results
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def apply_updates(client, updates: list[dict], dry_run: bool = False) -> dict:
    """Apply categorization updates to transactions."""
    succeeded = 0
    failed: list[dict] = []
    skipped = 0
    dry_run_preview: list[dict] = []

    for update in updates:
        txn_id = update.get("transaction_id")
        if not txn_id:
            failed.append({"error": "Missing transaction_id", "update": update})
            continue

        payload: dict = {"transactions": [{}]}
        txn_payload = payload["transactions"][0]

        if update.get("category") is not None:
            txn_payload["category_name"] = update["category"]
        if update.get("tags") is not None:
            txn_payload["tags"] = update["tags"]
        if update.get("budget") is not None:
            txn_payload["budget_name"] = update["budget"]
        if update.get("notes") is not None:
            txn_payload["notes"] = update["notes"]

        if not txn_payload:
            skipped += 1
            continue

        if dry_run:
            dry_run_preview.append({
                "transaction_id": txn_id,
                "changes": txn_payload,
            })
            continue

        try:
            client.put(f"/transactions/{txn_id}", json_data=payload)
            succeeded += 1
        except Exception as e:
            failed.append({"transaction_id": txn_id, "error": str(e)})

    result = {
        "total": len(updates),
        "succeeded": succeeded,
        "failed": len(failed),
        "skipped": skipped,
    }

    if dry_run:
        result["dry_run"] = True
        result["preview"] = dry_run_preview
    if failed:
        result["errors"] = failed

    return result


def main():
    parser = argparse.ArgumentParser(description="Batch categorize Firefly III transactions")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file", "-f", help="JSON file with updates")
    group.add_argument("--stdin", action="store_true", help="Read updates from stdin")
    group.add_argument("--id", type=int, help="Single transaction ID")

    parser.add_argument("--category", help="Category name (with --id)")
    parser.add_argument("--tags", help="Comma-separated tags (with --id)")
    parser.add_argument("--budget", help="Budget name (with --id)")
    parser.add_argument("--notes", help="Notes (with --id)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    updates: list[dict] = []

    if args.file:
        try:
            updates = json.loads(Path(args.file).read_text())
        except (json.JSONDecodeError, OSError) as e:
            output_error(f"Failed to read {args.file}: {e}")
    elif args.stdin:
        try:
            updates = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            output_error(f"Invalid JSON from stdin: {e}")
    elif args.id:
        update: dict = {"transaction_id": args.id}
        if args.category:
            update["category"] = args.category
        if args.tags:
            update["tags"] = [t.strip() for t in args.tags.split(",")]
        if args.budget:
            update["budget"] = args.budget
        if args.notes:
            update["notes"] = args.notes
        updates = [update]
    else:
        output_error("Provide --file, --stdin, or --id with categorization fields.")

    if not updates:
        output_error("No updates provided.")

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    result = apply_updates(client, updates, dry_run=args.dry_run)
    output_json(result)


if __name__ == "__main__":
    main()
