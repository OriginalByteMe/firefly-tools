from __future__ import annotations

from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient


async def _fetch_tags(client: FireflyClient) -> list[dict]:
    data = await client.list_tags()
    return [{"name": t["attributes"]["tag"]} for t in data.get("data", [])]


async def _fetch_categories(client: FireflyClient) -> list[dict]:
    data = await client.list_categories()
    return [{"name": c["attributes"]["name"]} for c in data.get("data", [])]


async def _fetch_budgets(client: FireflyClient) -> list[dict]:
    data = await client.list_budgets()
    results = []
    for b in data.get("data", []):
        attrs = b["attributes"]
        entry = {"id": int(b["id"]), "name": attrs["name"]}
        if attrs.get("auto_budget_amount"):
            entry["auto_budget_amount"] = attrs["auto_budget_amount"]
            entry["auto_budget_period"] = attrs.get("auto_budget_period", "monthly")
        results.append(entry)
    return results


async def _fetch_accounts(client: FireflyClient) -> list[dict]:
    data = await client.list_accounts()
    return [
        {
            "name": a["attributes"]["name"],
            "type": a["attributes"]["type"],
            "balance": a["attributes"].get("current_balance"),
            "currency": a["attributes"].get("currency_code"),
        }
        for a in data.get("data", [])
    ]


async def _fetch_bills(client: FireflyClient) -> list[dict]:
    data = await client.list_bills()
    return [
        {
            "name": b["attributes"]["name"],
            "amount_min": b["attributes"].get("amount_min"),
            "amount_max": b["attributes"].get("amount_max"),
            "repeat_freq": b["attributes"].get("repeat_freq"),
        }
        for b in data.get("data", [])
    ]


FETCHERS = {
    "tags": _fetch_tags,
    "categories": _fetch_categories,
    "budgets": _fetch_budgets,
    "accounts": _fetch_accounts,
    "bills": _fetch_bills,
}


async def get_financial_context(
    what: Annotated[
        str,
        Field(description="What to fetch: 'accounts', 'budgets', 'categories', 'tags', 'bills', or 'all'"),
    ] = "all",
    *,
    client: FireflyClient,
) -> dict:
    """Get reference data for making categorization decisions."""
    result: dict = {}

    if what == "all":
        for key, fetcher in FETCHERS.items():
            result[key] = await fetcher(client)
    elif what in FETCHERS:
        result[what] = await FETCHERS[what](client)
    else:
        return {"error": f"Unknown type '{what}'. Available: {', '.join(FETCHERS)}, all"}

    return result


async def manage_metadata(
    action: Annotated[
        str,
        Field(description="Action: 'create_tag', 'create_category', 'create_budget', 'update_budget_limit'"),
    ],
    name: Annotated[str, Field(description="Name of the tag, category, or budget")],
    amount: Annotated[float | None, Field(description="Budget limit amount (for budget operations)")] = None,
    period: Annotated[str | None, Field(description="Budget period: 'monthly', 'weekly', 'yearly'")] = None,
    *,
    client: FireflyClient,
) -> dict:
    """Create or update tags, categories, and budgets."""
    if action == "create_tag":
        data = await client.create_tag(name)
        return {"created": "tag", "name": name, "id": data["data"]["id"]}

    elif action == "create_category":
        data = await client.create_category(name)
        return {"created": "category", "name": name, "id": data["data"]["id"]}

    elif action == "create_budget":
        data = await client.create_budget(name)
        return {"created": "budget", "name": name, "id": data["data"]["id"]}

    elif action == "update_budget_limit":
        if amount is None:
            return {"error": "amount is required for update_budget_limit"}

        budgets = await client.list_budgets()
        budget_id = None
        for b in budgets.get("data", []):
            if b["attributes"]["name"].lower() == name.lower():
                budget_id = int(b["id"])
                break

        if budget_id is None:
            return {"error": f"Budget '{name}' not found"}

        from datetime import date, timedelta
        import calendar

        today = date.today()
        start = today.replace(day=1)

        effective_period = period or "monthly"
        if effective_period == "weekly":
            start = today - timedelta(days=today.weekday())
            end_date = start + timedelta(days=6)
        elif effective_period == "yearly":
            start = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        else:  # monthly
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = today.replace(day=last_day)

        data = await client.create_budget_limit(
            budget_id, amount, start.isoformat(), end_date.isoformat()
        )
        return {
            "updated": "budget_limit",
            "name": name,
            "amount": amount,
            "period": effective_period,
            "id": data["data"]["id"],
        }

    return {"error": f"Unknown action '{action}'"}
