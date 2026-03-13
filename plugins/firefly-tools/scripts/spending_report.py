#!/usr/bin/env python3
"""Generate a comprehensive spending report as Markdown.

New data processing script (not in MCP server).

Usage:
    python spending_report.py                                    # This month
    python spending_report.py --period 2026-02                   # Specific month
    python spending_report.py --period 2026-01-01:2026-03-31     # Custom range
    python spending_report.py --output report.md                 # Save to file

Output: Markdown report to stdout or file
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error


def resolve_period(period: str) -> tuple[str, str, str]:
    """Convert period to (start, end, label)."""
    today = date.today()

    if period == "this_month":
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
        label = today.strftime("%B %Y")
    elif period == "last_month":
        first_of_this = today.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        start = last_of_prev.replace(day=1)
        end = last_of_prev
        label = last_of_prev.strftime("%B %Y")
    elif ":" in period:
        parts = period.split(":", 1)
        return parts[0], parts[1], f"{parts[0]} to {parts[1]}"
    else:
        # Assume YYYY-MM format
        try:
            year, month = int(period[:4]), int(period[5:7])
            start = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end = date(year, month, last_day)
            label = start.strftime("%B %Y")
        except (ValueError, IndexError):
            start = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day)
            label = today.strftime("%B %Y")

    return start.isoformat(), end.isoformat(), label


def get_prior_period(start: str, end: str) -> tuple[str, str]:
    """Calculate the prior period."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    delta = (e - s).days + 1
    prior_end = s - timedelta(days=1)
    prior_start = prior_end - timedelta(days=delta - 1)
    return prior_start.isoformat(), prior_end.isoformat()


def main():
    parser = argparse.ArgumentParser(description="Generate Firefly III spending report")
    parser.add_argument("--period", default="this_month",
                        help="Period: 'this_month', 'last_month', 'YYYY-MM', or 'YYYY-MM-DD:YYYY-MM-DD'")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    args = parser.parse_args()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    start, end, label = resolve_period(args.period)
    prior_start, prior_end = get_prior_period(start, end)

    # Fetch all data
    cat_data = client.get("/insight/expense/category", params={"start": start, "end": end})
    budget_data = client.get("/insight/expense/budget", params={"start": start, "end": end})
    tag_data = client.get("/insight/expense/tag", params={"start": start, "end": end})
    prior_cat_data = client.get("/insight/expense/category", params={"start": prior_start, "end": prior_end})
    budgets_meta = client.get("/budgets")

    # Fetch top transactions
    all_txns = client.get_all_pages(
        "/transactions",
        params={"type": "withdrawal", "start": start, "end": end},
    )

    # Process categories
    categories = []
    for item in cat_data:
        categories.append({
            "name": item.get("name", "Unknown"),
            "total": abs(float(item.get("difference_float", 0))),
            "currency": item.get("currency_code", ""),
        })
    categories.sort(key=lambda x: x["total"], reverse=True)
    grand_total = sum(c["total"] for c in categories)

    # Prior period lookup
    prior_lookup = {}
    for item in prior_cat_data:
        prior_lookup[item.get("name", "Unknown")] = abs(float(item.get("difference_float", 0)))

    # Process budgets
    budget_limits: dict[str, float] = {}
    for b in budgets_meta.get("data", []):
        auto = b["attributes"].get("auto_budget_amount")
        if auto:
            budget_limits[b["attributes"]["name"]] = float(auto)

    budgets = []
    for item in budget_data:
        name = item.get("name", "Unknown")
        total = abs(float(item.get("difference_float", 0)))
        entry: dict = {"name": name, "total": total}
        if name in budget_limits:
            entry["limit"] = budget_limits[name]
            entry["remaining"] = budget_limits[name] - total
        budgets.append(entry)
    budgets.sort(key=lambda x: x["total"], reverse=True)

    # Top transactions
    txn_list = []
    for item in all_txns:
        attrs = item["attributes"]["transactions"][0]
        txn_list.append({
            "date": attrs["date"][:10],
            "description": attrs["description"],
            "amount": float(attrs["amount"]),
            "category": attrs.get("category_name", ""),
        })
    txn_list.sort(key=lambda x: x["amount"], reverse=True)
    top_txns = txn_list[:10]

    # Tags
    tags = []
    for item in tag_data:
        tags.append({
            "name": item.get("name", "Unknown"),
            "total": abs(float(item.get("difference_float", 0))),
        })
    tags.sort(key=lambda x: x["total"], reverse=True)

    # Build Markdown report
    lines = [
        f"# Spending Report: {label}",
        f"**Period:** {start} to {end}",
        f"**Total Spending:** {grand_total:,.2f}",
        "",
        "---",
        "",
        "## Category Breakdown",
        "",
        "| Category | Amount | % of Total | vs Prior Period |",
        "|----------|-------:|----------:|----------------:|",
    ]

    for cat in categories:
        pct = (cat["total"] / grand_total * 100) if grand_total > 0 else 0
        prior = prior_lookup.get(cat["name"], 0)
        if prior > 0:
            change = ((cat["total"] - prior) / prior) * 100
            change_str = f"{change:+.1f}%"
        else:
            change_str = "new"
        lines.append(f"| {cat['name']} | {cat['total']:,.2f} | {pct:.1f}% | {change_str} |")

    lines.extend(["", "---", "", "## Budget Performance", ""])

    if budgets:
        lines.append("| Budget | Spent | Limit | Remaining | Status |")
        lines.append("|--------|------:|------:|----------:|--------|")
        for b in budgets:
            if "limit" in b:
                status = "Over budget" if b["remaining"] < 0 else ("Warning" if b["remaining"] < b["limit"] * 0.1 else "On track")
                lines.append(f"| {b['name']} | {b['total']:,.2f} | {b['limit']:,.2f} | {b['remaining']:,.2f} | {status} |")
            else:
                lines.append(f"| {b['name']} | {b['total']:,.2f} | - | - | No limit |")
    else:
        lines.append("*No budget data available.*")

    lines.extend(["", "---", "", "## Top Transactions", ""])
    lines.append("| Date | Description | Amount | Category |")
    lines.append("|------|-------------|-------:|----------|")
    for txn in top_txns:
        lines.append(f"| {txn['date']} | {txn['description']} | {txn['amount']:,.2f} | {txn['category']} |")

    if tags:
        lines.extend(["", "---", "", "## Tag Summary", ""])
        lines.append("| Tag | Amount |")
        lines.append("|-----|-------:|")
        for tag in tags[:15]:
            lines.append(f"| {tag['name']} | {tag['total']:,.2f} |")

    lines.extend(["", "---", f"*Generated from Firefly III data. {len(all_txns)} transactions analyzed.*"])

    report = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(report)
        print(json.dumps({"file": args.output, "transactions_analyzed": len(all_txns)}))
    else:
        print(report)


if __name__ == "__main__":
    main()
