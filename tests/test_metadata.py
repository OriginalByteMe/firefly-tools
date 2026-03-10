import pytest
from unittest.mock import AsyncMock

from firefly_mcp.tools.metadata import get_financial_context, manage_metadata


@pytest.mark.asyncio
async def test_get_financial_context_tags():
    mock_client = AsyncMock()
    mock_client.list_tags.return_value = {
        "data": [
            {"id": "1", "attributes": {"tag": "restaurant", "date": None}},
            {"id": "2", "attributes": {"tag": "transport", "date": None}},
        ]
    }

    result = await get_financial_context(what="tags", client=mock_client)
    assert "tags" in result
    assert len(result["tags"]) == 2
    assert result["tags"][0]["name"] == "restaurant"


@pytest.mark.asyncio
async def test_get_financial_context_all():
    mock_client = AsyncMock()
    mock_client.list_tags.return_value = {"data": []}
    mock_client.list_categories.return_value = {"data": []}
    mock_client.list_budgets.return_value = {"data": []}
    mock_client.list_accounts.return_value = {"data": []}
    mock_client.list_bills.return_value = {"data": []}

    result = await get_financial_context(what="all", client=mock_client)
    assert "tags" in result
    assert "categories" in result
    assert "budgets" in result
    assert "accounts" in result
    assert "bills" in result


@pytest.mark.asyncio
async def test_manage_metadata_create_tag():
    mock_client = AsyncMock()
    mock_client.create_tag.return_value = {"data": {"id": "5"}}

    result = await manage_metadata(action="create_tag", name="gaming", client=mock_client)
    assert result["created"] == "tag"
    assert result["name"] == "gaming"


@pytest.mark.asyncio
async def test_manage_metadata_create_category():
    mock_client = AsyncMock()
    mock_client.create_category.return_value = {"data": {"id": "3"}}

    result = await manage_metadata(action="create_category", name="Dining", client=mock_client)
    assert result["created"] == "category"
    mock_client.create_category.assert_called_once_with("Dining")


@pytest.mark.asyncio
async def test_manage_metadata_create_budget():
    mock_client = AsyncMock()
    mock_client.create_budget.return_value = {"data": {"id": "2"}}

    result = await manage_metadata(action="create_budget", name="Transport", client=mock_client)
    assert result["created"] == "budget"


@pytest.mark.asyncio
async def test_manage_metadata_update_budget_limit():
    mock_client = AsyncMock()
    mock_client.list_budgets.return_value = {
        "data": [{"id": "1", "attributes": {"name": "Eating Out"}}]
    }
    mock_client.create_budget_limit.return_value = {"data": {"id": "10"}}

    result = await manage_metadata(
        action="update_budget_limit",
        name="Eating Out",
        amount=500.0,
        period="monthly",
        client=mock_client,
    )
    assert result["updated"] == "budget_limit"
    assert result["amount"] == 500.0
    assert result["period"] == "monthly"
    mock_client.create_budget_limit.assert_called_once()


@pytest.mark.asyncio
async def test_manage_metadata_update_budget_limit_not_found():
    mock_client = AsyncMock()
    mock_client.list_budgets.return_value = {"data": []}

    result = await manage_metadata(
        action="update_budget_limit", name="Nonexistent", amount=100.0, client=mock_client
    )
    assert "error" in result
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_manage_metadata_unknown_action():
    mock_client = AsyncMock()
    result = await manage_metadata(action="delete_everything", name="x", client=mock_client)
    assert "error" in result
