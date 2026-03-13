#!/usr/bin/env python3
"""Create, update, or delete tags, categories, budgets, accounts, and bills.

Replaces MCP tool: manage_metadata

Usage:
    python manage_metadata.py create_tag --name "online-shopping"
    python manage_metadata.py create_category --name "Subscriptions"
    python manage_metadata.py create_budget --name "Entertainment"
    python manage_metadata.py update_budget_limit --name "Groceries" --amount 500
    python manage_metadata.py delete_tag --entity-id 42
    python manage_metadata.py create_account --name "Savings" --account-type asset
    python manage_metadata.py create_bill --name "Netflix" --amount-min 45 --amount-max 50 --repeat-freq monthly

Output: JSON result
"""

from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def handle_action(client, args) -> dict:
    """Route the action to the appropriate API call."""
    action = args.action

    # -- Tags --
    if action == "create_tag":
        data = client.post("/tags", json_data={"tag": args.name})
        return {"created": "tag", "name": args.name, "id": data["data"]["id"]}

    elif action == "update_tag":
        if not args.entity_id:
            return {"error": "entity_id is required for update_tag"}
        client.put(f"/tags/{args.entity_id}", json_data={"tag": args.name})
        return {"updated": "tag", "id": args.entity_id, "name": args.name}

    elif action == "delete_tag":
        if not args.entity_id:
            return {"error": "entity_id is required for delete_tag"}
        client.delete(f"/tags/{args.entity_id}")
        return {"deleted": "tag", "id": args.entity_id}

    # -- Categories --
    elif action == "create_category":
        data = client.post("/categories", json_data={"name": args.name})
        return {"created": "category", "name": args.name, "id": data["data"]["id"]}

    elif action == "update_category":
        if not args.entity_id:
            return {"error": "entity_id is required for update_category"}
        client.put(f"/categories/{args.entity_id}", json_data={"name": args.name})
        return {"updated": "category", "id": args.entity_id, "name": args.name}

    elif action == "delete_category":
        if not args.entity_id:
            return {"error": "entity_id is required for delete_category"}
        client.delete(f"/categories/{args.entity_id}")
        return {"deleted": "category", "id": args.entity_id}

    # -- Budgets --
    elif action == "create_budget":
        data = client.post("/budgets", json_data={"name": args.name})
        return {"created": "budget", "name": args.name, "id": data["data"]["id"]}

    elif action == "update_budget_limit":
        if args.amount is None:
            return {"error": "amount is required for update_budget_limit"}

        # Find the budget by name
        budgets = client.get("/budgets")
        budget_id = None
        for b in budgets.get("data", []):
            if b["attributes"]["name"].lower() == args.name.lower():
                budget_id = int(b["id"])
                break
        if budget_id is None:
            return {"error": f"Budget '{args.name}' not found"}

        today = date.today()
        start = today.replace(day=1)
        effective_period = args.period or "monthly"

        if effective_period == "weekly":
            start = today - timedelta(days=today.weekday())
            end_date = start + timedelta(days=6)
        elif effective_period == "yearly":
            start = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        else:
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = today.replace(day=last_day)

        data = client.post(
            f"/budgets/{budget_id}/limits",
            json_data={
                "amount": str(args.amount),
                "start": start.isoformat(),
                "end": end_date.isoformat(),
                "currency_code": args.currency_code or "MYR",
            },
        )
        return {
            "updated": "budget_limit",
            "name": args.name,
            "amount": args.amount,
            "period": effective_period,
            "id": data["data"]["id"],
        }

    elif action == "delete_budget":
        if not args.entity_id:
            return {"error": "entity_id is required for delete_budget"}
        client.delete(f"/budgets/{args.entity_id}")
        return {"deleted": "budget", "id": args.entity_id}

    # -- Accounts --
    elif action == "create_account":
        if not args.name:
            return {"error": "name is required for create_account"}
        payload: dict = {"name": args.name, "type": args.account_type or "asset"}
        if args.currency_code:
            payload["currency_code"] = args.currency_code
        data = client.post("/accounts", json_data=payload)
        return {"created": "account", "name": args.name, "id": data["data"]["id"]}

    elif action == "update_account":
        if not args.entity_id:
            return {"error": "entity_id is required for update_account"}
        payload = {}
        if args.name:
            payload["name"] = args.name
        if args.account_type:
            payload["type"] = args.account_type
        if args.currency_code:
            payload["currency_code"] = args.currency_code
        if not payload:
            return {"error": "No fields provided to update"}
        client.put(f"/accounts/{args.entity_id}", json_data=payload)
        return {"updated": "account", "id": args.entity_id}

    elif action == "delete_account":
        if not args.entity_id:
            return {"error": "entity_id is required for delete_account"}
        client.delete(f"/accounts/{args.entity_id}")
        return {"deleted": "account", "id": args.entity_id}

    # -- Bills --
    elif action == "create_bill":
        if not args.name:
            return {"error": "name is required for create_bill"}
        if args.amount_min is None or args.amount_max is None:
            return {"error": "amount_min and amount_max are required for create_bill"}
        payload = {
            "name": args.name,
            "amount_min": str(args.amount_min),
            "amount_max": str(args.amount_max),
            "date": date.today().isoformat(),
            "repeat_freq": args.repeat_freq or "monthly",
        }
        if args.currency_code:
            payload["currency_code"] = args.currency_code
        data = client.post("/bills", json_data=payload)
        return {"created": "bill", "name": args.name, "id": data["data"]["id"]}

    elif action == "update_bill":
        if not args.entity_id:
            return {"error": "entity_id is required for update_bill"}
        payload = {}
        if args.name:
            payload["name"] = args.name
        if args.amount_min is not None:
            payload["amount_min"] = str(args.amount_min)
        if args.amount_max is not None:
            payload["amount_max"] = str(args.amount_max)
        if args.repeat_freq:
            payload["repeat_freq"] = args.repeat_freq
        if args.currency_code:
            payload["currency_code"] = args.currency_code
        if not payload:
            return {"error": "No fields provided to update"}
        client.put(f"/bills/{args.entity_id}", json_data=payload)
        return {"updated": "bill", "id": args.entity_id}

    elif action == "delete_bill":
        if not args.entity_id:
            return {"error": "entity_id is required for delete_bill"}
        client.delete(f"/bills/{args.entity_id}")
        return {"deleted": "bill", "id": args.entity_id}

    return {"error": f"Unknown action '{action}'"}


ACTIONS = [
    "create_tag", "update_tag", "delete_tag",
    "create_category", "update_category", "delete_category",
    "create_budget", "update_budget_limit", "delete_budget",
    "create_account", "update_account", "delete_account",
    "create_bill", "update_bill", "delete_bill",
]


def main():
    parser = argparse.ArgumentParser(description="Manage Firefly III metadata")
    parser.add_argument("action", choices=ACTIONS, help="Action to perform")
    parser.add_argument("--name", default="", help="Entity name")
    parser.add_argument("--entity-id", type=int, help="Entity ID (for update/delete)")
    parser.add_argument("--amount", type=float, help="Budget limit or bill amount")
    parser.add_argument("--period", choices=["weekly", "monthly", "yearly"], help="Budget period")
    parser.add_argument("--account-type", choices=["asset", "expense", "revenue", "liability"])
    parser.add_argument("--amount-min", type=float, help="Bill minimum amount")
    parser.add_argument("--amount-max", type=float, help="Bill maximum amount")
    parser.add_argument("--repeat-freq", choices=["weekly", "monthly", "quarterly", "half-year", "yearly"])
    parser.add_argument("--currency-code", help="Currency code (e.g., MYR, USD)")
    args = parser.parse_args()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    result = handle_action(client, args)
    output_json(result)


if __name__ == "__main__":
    main()
