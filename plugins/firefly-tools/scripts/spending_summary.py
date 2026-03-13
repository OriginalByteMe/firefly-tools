#!/usr/bin/env python3
"""Get aggregated spending summary grouped by category/tag/budget/account.

Replaces MCP tool: get_spending_summary

Usage:
    python spending_summary.py                                  # This month by category
    python spending_summary.py --period last_month              # Last month
    python spending_summary.py --period 2026-01-01:2026-01-31   # Custom range
    python spending_summary.py --group-by budget                # By budget (includes limits)
    python spending_summary.py --group-by tag                   # By tag
    python spending_summary.py --compare                        # Include prior period comparison

Output: JSON to stdout
"""

from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


INSIGHT_GROUPS = {
    "category": "category",
    "tag": "tag",
    "budget": "budget",
    "account": "asset",
}


def resolve_period(period: str) -> tuple[str, str]:
    """Convert a period string to (start_date, end_date) ISO strings."""
    today = date.today()

    if period == "this_month":
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
    elif period == "last_month":
        first_of_this = today.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        start = last_of_prev.replace(day=1)
        end = last_of_prev
    elif period == "this_year":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
    elif ":" in period:
        parts = period.split(":", 1)
        return parts[0], parts[1]
    else:
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)

    return start.isoformat(), end.isoformat()


def get_prior_period(start: str, end: str) -> tuple[str, str]:
    """Calculate the equivalent prior period for comparison."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    delta = (e - s).days + 1
    prior_end = s - timedelta(days=1)
    prior_start = prior_end - timedelta(days=delta - 1)
    return prior_start.isoformat(), prior_end.isoformat()


def fetch_summary(client, start: str, end: str, group_by: str) -> dict:
    """Fetch spending summary for a period."""
    insight_group = INSIGHT_GROUPS.get(group_by, "category")
    data = client.get(f"/insight/expense/{insight_group}", params={"start": start, "end": end})

    groups: list[dict] = []
    for item in data:
        entry = {
            "name": item.get("name", "Unknown"),
            "total": abs(float(item.get("difference_float", 0))),
            "currency": item.get("currency_code", ""),
        }
        groups.append(entry)

    groups.sort(key=lambda x: x["total"], reverse=True)

    result: dict = {
        "period": f"{start} to {end}",
        "group_by": group_by,
        "groups": groups,
        "grand_total": round(sum(g["total"] for g in groups), 2),
    }

    # Enrich budget view with limits
    if group_by == "budget":
        budgets_data = client.get("/budgets")
        budget_limits: dict[str, float] = {}
        for b in budgets_data.get("data", []):
            name = b["attributes"]["name"]
            auto_amount = b["attributes"].get("auto_budget_amount")
            if auto_amount:
                budget_limits[name] = float(auto_amount)

        for group in result["groups"]:
            limit = budget_limits.get(group["name"])
            if limit:
                group["limit"] = limit
                group["remaining"] = round(limit - group["total"], 2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Get Firefly III spending summary")
    parser.add_argument(
        "--period",
        default="this_month",
        help="Period: 'this_month', 'last_month', 'this_year', or 'YYYY-MM-DD:YYYY-MM-DD'",
    )
    parser.add_argument(
        "--group-by",
        default="category",
        choices=["category", "tag", "budget", "account"],
        help="Group spending by (default: category)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Include comparison with prior period",
    )
    args = parser.parse_args()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    start, end = resolve_period(args.period)
    result = fetch_summary(client, start, end, args.group_by)

    if args.compare:
        prior_start, prior_end = get_prior_period(start, end)
        prior = fetch_summary(client, prior_start, prior_end, args.group_by)

        # Build a lookup for comparison
        prior_lookup = {g["name"]: g["total"] for g in prior["groups"]}
        for group in result["groups"]:
            prev_total = prior_lookup.get(group["name"], 0)
            group["prior_period_total"] = prev_total
            if prev_total > 0:
                group["change_pct"] = round(
                    ((group["total"] - prev_total) / prev_total) * 100, 1
                )
            else:
                group["change_pct"] = None

        result["comparison_period"] = f"{prior_start} to {prior_end}"

    output_json(result)


if __name__ == "__main__":
    main()
