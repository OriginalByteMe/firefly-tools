from __future__ import annotations

from typing import Annotated

from pydantic import Field

from firefly_mcp.client import FireflyClient
from firefly_mcp.models import CompactTransaction


def _build_search_query(
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    account: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    budget: str | None = None,
    type: str = "all",
) -> str:
    """Build Firefly III search query string from natural parameters."""
    parts: list[str] = []

    if query:
        parts.append(query)
    if date_from:
        parts.append(f"date_after:{date_from}")
    if date_to:
        parts.append(f"date_before:{date_to}")
    if amount_min is not None:
        parts.append(f"amount_more:{amount_min}")
    if amount_max is not None:
        parts.append(f"amount_less:{amount_max}")
    if account:
        parts.append(f'source_account_is:"{account}"')
    if category:
        parts.append(f'category_is:"{category}"')
    if tag:
        parts.append(f'tag_is:"{tag}"')
    if budget:
        parts.append(f'budget_is:"{budget}"')
    if type != "all":
        parts.append(f"type:{type}")

    return " ".join(parts)


async def search_transactions(
    query: Annotated[str | None, Field(description="Free-text description search")] = None,
    date_from: Annotated[str | None, Field(description="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, Field(description="End date (YYYY-MM-DD)")] = None,
    amount_min: Annotated[float | None, Field(description="Minimum amount")] = None,
    amount_max: Annotated[float | None, Field(description="Maximum amount")] = None,
    account: Annotated[str | None, Field(description="Account name")] = None,
    category: Annotated[str | None, Field(description="Category name")] = None,
    tag: Annotated[str | None, Field(description="Tag name")] = None,
    budget: Annotated[str | None, Field(description="Budget name")] = None,
    type: Annotated[str, Field(description="Transaction type: 'withdrawal', 'deposit', 'transfer', 'all'")] = "all",
    *,
    client: FireflyClient,
) -> list[CompactTransaction]:
    """Search transactions with natural parameters."""
    search_query = _build_search_query(
        query=query, date_from=date_from, date_to=date_to,
        amount_min=amount_min, amount_max=amount_max, account=account,
        category=category, tag=tag, budget=budget, type=type,
    )

    if not search_query:
        return []

    results: list[CompactTransaction] = []
    page = 1

    while True:
        data = await client.search_transactions(search_query, page=page)
        for item in data.get("data", []):
            results.append(CompactTransaction.from_api(item))

        total_pages = data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return results
