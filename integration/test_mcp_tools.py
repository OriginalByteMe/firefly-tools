"""Integration tests for Firefly III MCP tools against a real Firefly III instance.

Prerequisites:
    1. Run `./bootstrap.sh` to start Docker services and generate .env.test
    2. Run this script: `uv run --extra dev pytest integration/test_mcp_tools.py -v`

These tests exercise every MCP tool against the live Firefly III API
to validate that the MCP server can actually communicate with Firefly III.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load integration test .env
_env_path = Path(__file__).parent / ".env.test"
if not _env_path.exists():
    pytest.skip(
        "Integration .env.test not found. Run bootstrap.sh first.",
        allow_module_level=True,
    )
load_dotenv(_env_path)

from firefly_mcp.client import FireflyClient


@pytest.fixture
async def client():
    """Create a real FireflyClient connected to the Docker Firefly III instance."""
    c = FireflyClient(
        firefly_url=os.environ["FIREFLY_URL"],
        token=os.environ["FIREFLY_TOKEN"],
        importer_url=os.environ.get("FIREFLY_IMPORTER_URL", ""),
        importer_secret=os.environ.get("FIREFLY_IMPORTER_SECRET", ""),
    )
    yield c
    await c.close()


# ---- Smoke Test: API connectivity ----


@pytest.mark.asyncio
async def test_api_connectivity(client):
    """Verify basic API connectivity to Firefly III."""
    resp = await client._firefly.get("/about")
    resp.raise_for_status()
    data = resp.json()["data"]
    assert "version" in data
    print(f"Connected to Firefly III {data['version']}")


# ---- get_financial_context ----


@pytest.mark.asyncio
async def test_get_financial_context(client):
    """get_financial_context should return all reference data types."""
    from firefly_mcp.tools.metadata import get_financial_context

    result = await get_financial_context(what="all", client=client)
    assert "categories" in result
    assert "tags" in result
    assert "budgets" in result
    assert "accounts" in result
    assert "bills" in result
    # All should be lists (possibly empty in a fresh install)
    for key in ("categories", "tags", "budgets", "accounts", "bills"):
        assert isinstance(result[key], list)


# ---- manage_metadata: create/read/delete cycle ----


@pytest.mark.asyncio
async def test_manage_metadata_tag_lifecycle(client):
    """Create, verify, and delete a tag."""
    from firefly_mcp.tools.metadata import get_financial_context, manage_metadata

    # Create
    result = await manage_metadata(action="create_tag", name="integration-test-tag", client=client)
    assert result.get("created") == "tag"
    tag_id = int(result["id"])

    # Verify it shows up
    ctx = await get_financial_context(what="tags", client=client)
    tag_names = [t["name"] for t in ctx["tags"]]
    assert "integration-test-tag" in tag_names

    # Delete
    result = await manage_metadata(action="delete_tag", entity_id=tag_id, client=client)
    assert result.get("deleted") == "tag"


@pytest.mark.asyncio
async def test_manage_metadata_category_lifecycle(client):
    """Create, verify, and delete a category."""
    from firefly_mcp.tools.metadata import get_financial_context, manage_metadata

    result = await manage_metadata(action="create_category", name="Integration Test Category", client=client)
    assert result.get("created") == "category"
    cat_id = int(result["id"])

    ctx = await get_financial_context(what="categories", client=client)
    cat_names = [c["name"] for c in ctx["categories"]]
    assert "Integration Test Category" in cat_names

    result = await manage_metadata(action="delete_category", entity_id=cat_id, client=client)
    assert result.get("deleted") == "category"


@pytest.mark.asyncio
async def test_manage_metadata_account_lifecycle(client):
    """Create, verify, and delete an asset account."""
    from firefly_mcp.tools.metadata import get_financial_context, manage_metadata

    result = await manage_metadata(
        action="create_account",
        name="Integration Test Account",
        account_type="asset",
        currency_code="USD",
        client=client,
    )
    assert result.get("created") == "account"
    acct_id = int(result["id"])

    ctx = await get_financial_context(what="accounts", client=client)
    acct_names = [a["name"] for a in ctx["accounts"]]
    assert "Integration Test Account" in acct_names

    result = await manage_metadata(action="delete_account", entity_id=acct_id, client=client)
    assert result.get("deleted") == "account"


@pytest.mark.asyncio
async def test_manage_metadata_bill_lifecycle(client):
    """Create, verify, and delete a bill."""
    from firefly_mcp.tools.metadata import get_financial_context, manage_metadata

    result = await manage_metadata(
        action="create_bill",
        name="Integration Test Bill",
        amount_min=9.99,
        amount_max=9.99,
        repeat_freq="monthly",
        currency_code="USD",
        client=client,
    )
    assert result.get("created") == "bill"
    bill_id = int(result["id"])

    ctx = await get_financial_context(what="bills", client=client)
    bill_names = [b["name"] for b in ctx["bills"]]
    assert "Integration Test Bill" in bill_names

    result = await manage_metadata(action="delete_bill", entity_id=bill_id, client=client)
    assert result.get("deleted") == "bill"


@pytest.mark.asyncio
async def test_manage_metadata_budget_lifecycle(client):
    """Create, verify, and delete a budget."""
    from firefly_mcp.tools.metadata import get_financial_context, manage_metadata

    result = await manage_metadata(action="create_budget", name="Integration Test Budget", client=client)
    assert result.get("created") == "budget"
    budget_id = int(result["id"])

    ctx = await get_financial_context(what="budgets", client=client)
    budget_names = [b["name"] for b in ctx["budgets"]]
    assert "Integration Test Budget" in budget_names

    result = await manage_metadata(action="delete_budget", entity_id=budget_id, client=client)
    assert result.get("deleted") == "budget"


# ---- search_transactions (on a fresh DB, likely empty) ----


@pytest.mark.asyncio
async def test_search_transactions_no_crash(client):
    """search_transactions should not crash on a fresh instance."""
    from firefly_mcp.tools.search import search_transactions

    result = await search_transactions(query="nonexistent", client=client)
    assert isinstance(result, list)


# ---- get_review_queue (on a fresh DB, likely empty) ----


@pytest.mark.asyncio
async def test_get_review_queue_no_crash(client):
    """get_review_queue should not crash on a fresh instance."""
    from firefly_mcp.tools.review import get_review_queue

    result = await get_review_queue(days_back=30, filter="all_unreviewed", client=client)
    assert isinstance(result, list)


# ---- get_spending_summary ----


@pytest.mark.asyncio
async def test_get_spending_summary_no_crash(client):
    """get_spending_summary should not crash on a fresh instance."""
    from firefly_mcp.tools.insights import get_spending_summary

    result = await get_spending_summary(period="this_month", group_by="category", client=client)
    assert isinstance(result, dict)


# ---- manage_automations: create/list/test/delete cycle ----


@pytest.mark.asyncio
async def test_manage_automations_lifecycle(client):
    """Create a rule, list it, test it, and delete it."""
    from firefly_mcp.models import RuleActionInput, RuleTriggerInput
    from firefly_mcp.tools.automations import manage_automations, test_automation

    # Create
    result = await manage_automations(
        action="create",
        title="Integration Test Rule",
        rule_group="Integration Tests",
        triggers=[RuleTriggerInput(type="description_contains", value="INTEGRATION-TEST")],
        actions=[RuleActionInput(type="add_tag", value="auto-tagged")],
        client=client,
    )
    assert result.get("created") == "rule"
    rule_id = result["id"]

    # List
    result = await manage_automations(action="list", client=client)
    rule_titles = [r["title"] for r in result["rules"]]
    assert "Integration Test Rule" in rule_titles

    # Test (dry run) — shouldn't crash even with no matching transactions
    result = await test_automation(rule_id=rule_id, execute=False, client=client)
    assert "matched_transactions" in result

    # Delete
    result = await manage_automations(action="delete", rule_id=rule_id, client=client)
    assert result.get("deleted") == "rule"


# ---- get_automation_context ----


@pytest.mark.asyncio
async def test_get_automation_context(client):
    """get_automation_context should return keywords and quirks."""
    from firefly_mcp.tools.automations import get_automation_context

    result = await get_automation_context(client=client)
    assert "trigger_keywords" in result
    assert "action_keywords" in result
    assert "known_quirks" in result
    assert "description_contains" in result["trigger_keywords"]
    assert "set_category" in result["action_keywords"]


# ---- discover_recurring (fresh DB, empty) ----


@pytest.mark.asyncio
async def test_discover_recurring_no_crash(client):
    """discover_recurring should not crash on a fresh instance."""
    from firefly_mcp.tools.recurring import discover_recurring

    result = await discover_recurring(days_back=30, min_occurrences=2, client=client)
    assert isinstance(result, dict)
    assert "recurring" in result
    assert "total_found" in result


# ---- End-to-end: create transaction, categorize, update, search ----


@pytest.mark.asyncio
async def test_transaction_full_lifecycle(client):
    """Create a transaction via the API, then exercise categorize, update, and search tools."""
    from firefly_mcp.models import BulkTransactionUpdate, TransactionUpdate
    from firefly_mcp.tools.metadata import manage_metadata
    from firefly_mcp.tools.review import categorize_transactions, update_transactions
    from firefly_mcp.tools.search import search_transactions

    # First, ensure we have an expense account to use as destination
    # and create the transaction directly via the client
    payload = {
        "transactions": [
            {
                "type": "withdrawal",
                "date": "2026-03-01",
                "amount": "42.50",
                "description": "INTEGRATION TEST COFFEE SHOP",
                "source_name": "Integration Source",
                "destination_name": "Integration Coffee Shop",
            }
        ],
        "error_if_duplicate_hash": False,
    }

    resp = await client._firefly.post("/transactions", json=payload)
    # Accept both 200 and 422 (duplicate) — we just need a transaction to exist
    if resp.status_code == 200:
        txn_data = resp.json()
        txn_id = int(txn_data["data"]["id"])
    else:
        # Search for it
        results = await search_transactions(query="INTEGRATION TEST COFFEE", client=client)
        if results:
            txn_id = results[0].id
        else:
            pytest.skip("Could not create test transaction")

    # Create a test category and tag for categorization
    cat_result = await manage_metadata(action="create_category", name="Test Coffee", client=client)
    cat_id = int(cat_result["id"])

    tag_result = await manage_metadata(action="create_tag", name="test-beverage", client=client)
    tag_id = int(tag_result["id"])

    try:
        # Categorize the transaction
        cat_update = [TransactionUpdate(
            transaction_id=txn_id,
            category="Test Coffee",
            tags=["test-beverage"],
        )]
        result = await categorize_transactions(cat_update, client=client)
        assert result["succeeded"] == 1

        # Verify via search
        results = await search_transactions(query="INTEGRATION TEST COFFEE", client=client)
        found = [r for r in results if r.id == txn_id]
        assert len(found) == 1
        assert found[0].category == "Test Coffee"

        # Update the transaction description
        bulk_update = [BulkTransactionUpdate(
            transaction_id=txn_id,
            description="INTEGRATION TEST UPDATED COFFEE SHOP",
            notes="Updated by integration test",
        )]
        result = await update_transactions(bulk_update, client=client)
        assert result["succeeded"] == 1

        # Verify update took effect
        txn = await client.get_transaction(txn_id)
        attrs = txn["data"]["attributes"]["transactions"][0]
        assert attrs["description"] == "INTEGRATION TEST UPDATED COFFEE SHOP"
        assert attrs["notes"] == "Updated by integration test"

    finally:
        # Clean up
        try:
            await client._firefly.delete(f"/transactions/{txn_id}")
        except Exception:
            pass
        await manage_metadata(action="delete_category", entity_id=cat_id, client=client)
        await manage_metadata(action="delete_tag", entity_id=tag_id, client=client)


# ---- Transfer conversion test ----


@pytest.mark.asyncio
async def test_update_transactions_convert_to_transfer(client):
    """Test converting a withdrawal to a transfer using update_transactions."""
    from firefly_mcp.models import BulkTransactionUpdate
    from firefly_mcp.tools.metadata import manage_metadata
    from firefly_mcp.tools.review import update_transactions

    # Create two asset accounts (source and destination)
    src_result = await manage_metadata(
        action="create_account",
        name="Transfer Test Source",
        account_type="asset",
        currency_code="USD",
        client=client,
    )
    src_id = int(src_result["id"])

    dst_result = await manage_metadata(
        action="create_account",
        name="Transfer Test Destination",
        account_type="asset",
        currency_code="USD",
        client=client,
    )
    dst_id = int(dst_result["id"])

    # Create a withdrawal transaction from source
    payload = {
        "transactions": [
            {
                "type": "withdrawal",
                "date": "2026-03-01",
                "amount": "100.00",
                "description": "INTEGRATION TRANSFER TEST",
                "source_id": src_id,
                "destination_name": "Some Expense",
            }
        ],
        "error_if_duplicate_hash": False,
    }

    resp = await client._firefly.post("/transactions", json=payload)
    txn_id = None
    if resp.status_code == 200:
        txn_id = int(resp.json()["data"]["id"])

    try:
        if txn_id is None:
            pytest.skip("Could not create test withdrawal for transfer conversion")

        # Convert to transfer using update_transactions
        result = await update_transactions(
            [BulkTransactionUpdate(
                transaction_id=txn_id,
                type="transfer",
                destination_id=dst_id,
            )],
            client=client,
        )
        assert result["succeeded"] == 1

        # Verify the transaction is now a transfer
        txn = await client.get_transaction(txn_id)
        attrs = txn["data"]["attributes"]["transactions"][0]
        assert attrs["type"] == "transfer"
        assert int(attrs["destination_id"]) == dst_id

    finally:
        # Clean up
        if txn_id:
            try:
                await client._firefly.delete(f"/transactions/{txn_id}")
            except Exception:
                pass
        await manage_metadata(action="delete_account", entity_id=src_id, client=client)
        await manage_metadata(action="delete_account", entity_id=dst_id, client=client)
