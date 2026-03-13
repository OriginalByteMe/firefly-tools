#!/usr/bin/env python3
"""Manage automation rules: list, create, update, delete, test, fire.

Replaces MCP tools: manage_automations, test_automation, get_automation_context

Usage:
    python manage_rules.py list
    python manage_rules.py get --rule-id 5
    python manage_rules.py context                    # Show available keywords & rule groups
    python manage_rules.py test --rule-id 5           # Dry-run against existing transactions
    python manage_rules.py fire --rule-id 5           # Actually fire rule
    python manage_rules.py test-group --group-id 2    # Test entire group
    python manage_rules.py fire-group --group-id 2    # Fire entire group
    python manage_rules.py delete --rule-id 5
    python manage_rules.py enable --rule-id 5
    python manage_rules.py disable --rule-id 5

    # Create from JSON:
    python manage_rules.py create --file rule.json
    # Or inline:
    python manage_rules.py create --title "Starbucks" --trigger-on store-journal \\
        --strict --triggers '[{"type":"description_contains","value":"STARBUCKS"}]' \\
        --actions '[{"type":"set_category","value":"Food & Dining"},{"type":"add_tag","value":"coffee"}]'

Output: JSON result
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


TRIGGER_KEYWORDS = sorted([
    "from_account_starts", "from_account_ends", "from_account_is", "from_account_contains",
    "to_account_starts", "to_account_ends", "to_account_is", "to_account_contains",
    "amount_less", "amount_exactly", "amount_more",
    "description_starts", "description_ends", "description_contains", "description_is",
    "transaction_type",
    "category_is", "budget_is", "tag_is", "currency_is",
    "has_attachments", "has_no_category", "has_any_category",
    "has_no_budget", "has_any_budget", "has_no_tag", "has_any_tag",
    "notes_contains", "notes_start", "notes_end", "notes_are", "no_notes", "any_notes",
])

ACTION_KEYWORDS = sorted([
    "set_category", "clear_category", "set_budget", "clear_budget",
    "add_tag", "remove_tag", "remove_all_tags", "link_to_bill",
    "set_description", "append_description", "prepend_description",
    "set_source_account", "set_destination_account",
    "set_notes", "append_notes", "prepend_notes", "clear_notes",
    "convert_withdrawal", "convert_deposit", "convert_transfer",
    "delete_transaction",
])


def compact_rule(data: dict) -> dict:
    """Extract compact rule info from API response."""
    attrs = data["attributes"]
    triggers = [
        {"type": t["type"], "value": t.get("value", ""), "prohibited": t.get("prohibited", False)}
        for t in attrs.get("triggers", [])
        if t.get("active", True)
    ]
    actions = [
        {"type": a["type"], "value": a.get("value", "")}
        for a in attrs.get("actions", [])
        if a.get("active", True)
    ]
    return {
        "id": int(data["id"]),
        "title": attrs["title"],
        "active": attrs.get("active", True),
        "trigger_on": attrs.get("trigger", "store-journal"),
        "strict": attrs.get("strict", True),
        "group": attrs.get("rule_group_title", ""),
        "triggers": triggers,
        "actions": actions,
    }


def find_or_create_rule_group(client, group_title: str) -> int:
    """Find a rule group by title, or create it."""
    data = client.get("/rule-groups")
    for g in data.get("data", []):
        if g["attributes"]["title"].lower() == group_title.lower():
            return int(g["id"])
    result = client.post("/rule-groups", json_data={"title": group_title})
    return int(result["data"]["id"])


def main():
    parser = argparse.ArgumentParser(description="Manage Firefly III automation rules")
    parser.add_argument(
        "action",
        choices=["list", "get", "create", "update", "delete", "enable", "disable",
                 "test", "fire", "test-group", "fire-group", "context"],
        help="Action to perform",
    )
    parser.add_argument("--rule-id", type=int, help="Rule ID")
    parser.add_argument("--group-id", type=int, help="Rule group ID")
    parser.add_argument("--title", help="Rule title")
    parser.add_argument("--rule-group", help="Rule group name (auto-creates if needed)")
    parser.add_argument("--trigger-on", choices=["store-journal", "update-journal"])
    parser.add_argument("--strict", action="store_true", default=None, help="ALL triggers must match")
    parser.add_argument("--no-strict", action="store_true", help="ANY trigger can match")
    parser.add_argument("--stop-processing", action="store_true", help="Stop processing subsequent rules")
    parser.add_argument("--triggers", help="JSON array of trigger objects")
    parser.add_argument("--actions", help="JSON array of action objects")
    parser.add_argument("--file", help="JSON file with full rule definition")
    args = parser.parse_args()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    action = args.action

    if action == "context":
        data = client.get("/rule-groups")
        groups = [
            {"id": int(g["id"]), "title": g["attributes"]["title"]}
            for g in data.get("data", [])
        ]
        output_json({
            "trigger_keywords": TRIGGER_KEYWORDS,
            "action_keywords": ACTION_KEYWORDS,
            "trigger_types": ["store-journal", "update-journal"],
            "rule_groups": groups,
            "known_quirks": [
                {
                    "action": "convert_transfer",
                    "issue": "Firefly III often rejects convert_transfer in rules. Use set_destination_account instead.",
                    "workaround": {"type": "set_destination_account", "value": "<asset account name>"},
                },
            ],
        })
        return

    if action == "list":
        all_items = client.get_all_pages("/rules")
        rules = [compact_rule(item) for item in all_items]
        output_json({"rules": rules, "total": len(rules)})
        return

    if action == "get":
        if not args.rule_id:
            output_error("--rule-id is required for 'get'")
        data = client.get(f"/rules/{args.rule_id}")
        output_json(compact_rule(data["data"]))
        return

    if action == "create":
        rule_def: dict = {}
        if args.file:
            rule_def = json.loads(Path(args.file).read_text())
        else:
            if not args.title:
                output_error("--title is required for 'create'")
            if not args.triggers or not args.actions:
                output_error("--triggers and --actions are required for 'create'")

            triggers = json.loads(args.triggers)
            actions = json.loads(args.actions)

            strict = True
            if args.no_strict:
                strict = False
            elif args.strict:
                strict = True

            rule_def = {
                "title": args.title,
                "trigger": args.trigger_on or "store-journal",
                "strict": strict,
                "stop_processing": args.stop_processing,
                "triggers": [
                    {"type": t["type"], "value": t.get("value", ""), "active": True,
                     "prohibited": t.get("prohibited", False)}
                    for t in triggers
                ],
                "actions": [
                    {"type": a["type"], "value": a.get("value", ""), "active": True}
                    for a in actions
                ],
            }

        group_name = args.rule_group or rule_def.get("rule_group", "Default")
        group_id = find_or_create_rule_group(client, group_name)
        rule_def["rule_group_id"] = str(group_id)
        rule_def["active"] = True

        data = client.post("/rules", json_data=rule_def)
        output_json({"created": "rule", **compact_rule(data["data"])})
        return

    if action == "update":
        if not args.rule_id:
            output_error("--rule-id is required for 'update'")
        payload: dict = {}
        if args.title:
            payload["title"] = args.title
        if args.trigger_on:
            payload["trigger"] = args.trigger_on
        if args.strict is not None:
            payload["strict"] = args.strict
        if args.no_strict:
            payload["strict"] = False
        if args.stop_processing:
            payload["stop_processing"] = True
        if args.rule_group:
            gid = find_or_create_rule_group(client, args.rule_group)
            payload["rule_group_id"] = str(gid)
        if args.triggers:
            triggers = json.loads(args.triggers)
            payload["triggers"] = [
                {"type": t["type"], "value": t.get("value", ""), "active": True,
                 "prohibited": t.get("prohibited", False)}
                for t in triggers
            ]
        if args.actions:
            actions = json.loads(args.actions)
            payload["actions"] = [
                {"type": a["type"], "value": a.get("value", ""), "active": True}
                for a in actions
            ]
        if not payload:
            output_error("No fields provided to update")
        data = client.put(f"/rules/{args.rule_id}", json_data=payload)
        output_json({"updated": "rule", **compact_rule(data["data"])})
        return

    if action == "delete":
        if not args.rule_id:
            output_error("--rule-id is required for 'delete'")
        client.delete(f"/rules/{args.rule_id}")
        output_json({"deleted": "rule", "rule_id": args.rule_id})
        return

    if action in ("enable", "disable"):
        if not args.rule_id:
            output_error(f"--rule-id is required for '{action}'")
        active = action == "enable"
        client.put(f"/rules/{args.rule_id}", json_data={"active": active})
        output_json({f"{action}d": "rule", "rule_id": args.rule_id})
        return

    if action == "test":
        if not args.rule_id:
            output_error("--rule-id is required for 'test'")
        data = client.get(f"/rules/{args.rule_id}/test")
        matched = [
            {
                "id": int(t["id"]),
                "description": t["attributes"]["transactions"][0]["description"],
                "amount": float(t["attributes"]["transactions"][0]["amount"]),
                "date": t["attributes"]["transactions"][0]["date"][:10],
            }
            for t in data.get("data", [])
        ]
        output_json({"rule_id": args.rule_id, "matched_transactions": matched, "count": len(matched)})
        return

    if action == "fire":
        if not args.rule_id:
            output_error("--rule-id is required for 'fire'")
        client.post(f"/rules/{args.rule_id}/trigger")
        output_json({"triggered": "rule", "rule_id": args.rule_id})
        return

    if action == "test-group":
        if not args.group_id:
            output_error("--group-id is required for 'test-group'")
        data = client.get(f"/rule-groups/{args.group_id}/test")
        matched = [
            {
                "id": int(t["id"]),
                "description": t["attributes"]["transactions"][0]["description"],
                "amount": float(t["attributes"]["transactions"][0]["amount"]),
                "date": t["attributes"]["transactions"][0]["date"][:10],
            }
            for t in data.get("data", [])
        ]
        output_json({"rule_group_id": args.group_id, "matched_transactions": matched, "count": len(matched)})
        return

    if action == "fire-group":
        if not args.group_id:
            output_error("--group-id is required for 'fire-group'")
        client.post(f"/rule-groups/{args.group_id}/trigger")
        output_json({"triggered": "rule_group", "rule_group_id": args.group_id})
        return


if __name__ == "__main__":
    main()
