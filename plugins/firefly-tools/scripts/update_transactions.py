#!/usr/bin/env python3
"""Bulk-update transactions: change type, destination, description, amount, metadata.

Replaces MCP tool: update_transactions

Usage:
    # From a JSON file:
    python update_transactions.py --file updates.json

    # From stdin:
    echo '[{"transaction_id": 123, "type": "transfer", "destination_name": "Savings"}]' | python update_transactions.py --stdin

    # Single transaction:
    python update_transactions.py --id 123 --type transfer --destination-name "Investment Account"

    # Dry run:
    python update_transactions.py --file updates.json --dry-run

JSON format for --file or --stdin:
[
    {
        "transaction_id": 123,
        "type": "transfer",
        "destination_id": 5,
        "category": "Transfers",
        "description": "Monthly savings"
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


FIELD_MAP = {
    "type": "type",
    "source_id": "source_id",
    "destination_id": "destination_id",
    "destination_name": "destination_name",
    "category": "category_name",
    "tags": "tags",
    "budget": "budget_name",
    "notes": "notes",
    "description": "description",
    "amount": "amount",
}


def apply_updates(client, updates: list[dict], dry_run: bool = False) -> dict:
    """Apply bulk updates to transactions."""
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

        for attr, api_field in FIELD_MAP.items():
            value = update.get(attr)
            if value is not None:
                txn_payload[api_field] = value

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
    parser = argparse.ArgumentParser(description="Bulk update Firefly III transactions")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file", "-f", help="JSON file with updates")
    group.add_argument("--stdin", action="store_true", help="Read updates from stdin")
    group.add_argument("--id", type=int, help="Single transaction ID")

    parser.add_argument("--type", choices=["withdrawal", "deposit", "transfer"])
    parser.add_argument("--destination-id", type=int, help="Destination account ID")
    parser.add_argument("--destination-name", help="Destination account name")
    parser.add_argument("--source-id", type=int, help="Source account ID")
    parser.add_argument("--description", help="New description")
    parser.add_argument("--amount", help="New amount")
    parser.add_argument("--category", help="Category name")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--budget", help="Budget name")
    parser.add_argument("--notes", help="Notes")
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
        if args.type:
            update["type"] = args.type
        if args.destination_id:
            update["destination_id"] = args.destination_id
        if args.destination_name:
            update["destination_name"] = args.destination_name
        if args.source_id:
            update["source_id"] = args.source_id
        if args.description:
            update["description"] = args.description
        if args.amount:
            update["amount"] = args.amount
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
        output_error("Provide --file, --stdin, or --id with fields to update.")

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
