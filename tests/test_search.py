import pytest
from unittest.mock import AsyncMock
from tests.conftest import SAMPLE_TRANSACTION

from firefly_mcp.tools.search import _build_search_query, search_transactions


def test_build_query_description_only():
    q = _build_search_query(query="grab food")
    assert q == "grab food"


def test_build_query_with_filters():
    q = _build_search_query(
        query="food",
        date_from="2026-03-01",
        date_to="2026-03-31",
        amount_min=10.0,
        category="Dining",
        type="withdrawal",
    )
    assert "food" in q
    assert "date_after:2026-03-01" in q
    assert "date_before:2026-03-31" in q
    assert "amount_more:10.0" in q
    assert 'category_is:"Dining"' in q
    assert "type:withdrawal" in q


def test_build_query_no_params():
    q = _build_search_query()
    assert q == ""


@pytest.mark.asyncio
async def test_search_transactions_with_results():
    mock_client = AsyncMock()
    mock_client.search_transactions.return_value = {
        "data": [SAMPLE_TRANSACTION],
        "meta": {"pagination": {"total_pages": 1}},
    }

    result = await search_transactions(
        query="grab", type="withdrawal", client=mock_client
    )
    assert len(result) == 1
    assert result[0].description == "GRAB FOOD"


@pytest.mark.asyncio
async def test_search_transactions_empty_params():
    mock_client = AsyncMock()
    result = await search_transactions(client=mock_client)
    assert result == []
    mock_client.search_transactions.assert_not_called()
