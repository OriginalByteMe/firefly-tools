#!/usr/bin/env python3
"""Forecast budget performance based on spending trends.

New data processing script (not in MCP server).

Uses historical spending data to project where you'll land by end of month/quarter.

Usage:
    python budget_forecast.py                        # This month projection
    python budget_forecast.py --months 3             # Use 3 months of history
    python budget_forecast.py --target end_of_month  # Project to end of month
    python budget_forecast.py --target end_of_quarter

Output: JSON forecast
"""

from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from firefly_client import get_client, output_error, output_json


def main():
    parser = argparse.ArgumentParser(description="Forecast Firefly III budget performance")
    parser.add_argument("--months", type=int, default=3, help="Months of history to use (default: 3)")
    parser.add_argument("--target", default="end_of_month",
                        choices=["end_of_month", "end_of_quarter", "end_of_year"],
                        help="Forecast target (default: end_of_month)")
    args = parser.parse_args()

    try:
        client = get_client()
    except (FileNotFoundError, ValueError) as e:
        output_error(str(e))

    today = date.today()

    # Calculate target date
    if args.target == "end_of_month":
        last_day = calendar.monthrange(today.year, today.month)[1]
        target_date = today.replace(day=last_day)
    elif args.target == "end_of_quarter":
        quarter_end_month = ((today.month - 1) // 3 + 1) * 3
        last_day = calendar.monthrange(today.year, quarter_end_month)[1]
        target_date = date(today.year, quarter_end_month, last_day)
    else:  # end_of_year
        target_date = date(today.year, 12, 31)

    days_remaining = (target_date - today).days
    month_start = today.replace(day=1)
    days_elapsed = (today - month_start).days + 1
    total_days_in_month = calendar.monthrange(today.year, today.month)[1]

    # Fetch current month spending by category
    current_data = client.get(
        "/insight/expense/category",
        params={"start": month_start.isoformat(), "end": today.isoformat()},
    )

    # Fetch historical monthly averages
    history_start = today.replace(day=1) - timedelta(days=args.months * 31)
    history_end = month_start - timedelta(days=1)

    hist_data = client.get(
        "/insight/expense/category",
        params={"start": history_start.isoformat(), "end": history_end.isoformat()},
    )

    # Fetch budgets
    budgets_data = client.get("/budgets")
    budget_limits: dict[str, float] = {}
    for b in budgets_data.get("data", []):
        auto = b["attributes"].get("auto_budget_amount")
        if auto:
            budget_limits[b["attributes"]["name"]] = float(auto)

    # Build current spending by category
    current_spending: dict[str, float] = {}
    for item in current_data:
        current_spending[item.get("name", "Unknown")] = abs(float(item.get("difference_float", 0)))

    # Build historical monthly average by category
    hist_monthly: dict[str, float] = {}
    for item in hist_data:
        total = abs(float(item.get("difference_float", 0)))
        hist_monthly[item.get("name", "Unknown")] = total / max(args.months, 1)

    # Build forecasts
    all_categories = set(current_spending.keys()) | set(hist_monthly.keys())
    forecasts: list[dict] = []

    for cat in sorted(all_categories):
        spent = current_spending.get(cat, 0)
        hist_avg = hist_monthly.get(cat, 0)

        # Linear projection: current daily rate * total days in month
        if days_elapsed > 0:
            daily_rate = spent / days_elapsed
            linear_projection = daily_rate * total_days_in_month
        else:
            linear_projection = 0

        # Weighted projection: blend linear + historical (more weight on actual as month progresses)
        progress = days_elapsed / total_days_in_month
        if hist_avg > 0:
            weighted_projection = (progress * linear_projection) + ((1 - progress) * hist_avg)
        else:
            weighted_projection = linear_projection

        entry: dict = {
            "category": cat,
            "spent_so_far": round(spent, 2),
            "daily_rate": round(daily_rate, 2) if days_elapsed > 0 else 0,
            "linear_projection": round(linear_projection, 2),
            "historical_monthly_avg": round(hist_avg, 2),
            "weighted_projection": round(weighted_projection, 2),
        }

        # Budget comparison
        if cat in budget_limits:
            limit = budget_limits[cat]
            entry["budget_limit"] = limit
            entry["projected_vs_budget"] = round(weighted_projection - limit, 2)
            entry["on_track"] = weighted_projection <= limit
            if limit > 0:
                entry["projected_utilization_pct"] = round((weighted_projection / limit) * 100, 1)

        forecasts.append(entry)

    forecasts.sort(key=lambda x: x["weighted_projection"], reverse=True)

    total_spent = sum(f["spent_so_far"] for f in forecasts)
    total_projected = sum(f["weighted_projection"] for f in forecasts)

    # Budget summary
    budgets_over = [f for f in forecasts if f.get("on_track") is False]
    budgets_ok = [f for f in forecasts if f.get("on_track") is True]

    output_json({
        "forecast_date": target_date.isoformat(),
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "total_days_in_month": total_days_in_month,
        "progress_pct": round((days_elapsed / total_days_in_month) * 100, 1),
        "total_spent_so_far": round(total_spent, 2),
        "total_projected": round(total_projected, 2),
        "history_months_used": args.months,
        "categories": forecasts,
        "budget_summary": {
            "on_track": len(budgets_ok),
            "projected_over": len(budgets_over),
            "over_budget_categories": [f["category"] for f in budgets_over],
        },
    })


if __name__ == "__main__":
    main()
