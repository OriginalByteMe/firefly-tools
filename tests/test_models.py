import pytest
from firefly_mcp.models import TransactionUpdate, CompactTransaction
from tests.conftest import SAMPLE_TRANSACTION


def test_transaction_update_valid():
    update = TransactionUpdate(
        transaction_id=1,
        category="Dining",
        tags=["restaurant", "grab"],
        budget="Eating Out",
        notes="Grab Food order",
    )
    assert update.transaction_id == 1
    assert update.tags == ["restaurant", "grab"]


def test_transaction_update_minimal():
    update = TransactionUpdate(transaction_id=42)
    assert update.category is None
    assert update.tags is None


def test_compact_transaction():
    txn = CompactTransaction(
        id=1,
        date="2026-03-01",
        amount=-25.50,
        description="GRAB FOOD",
        source_account="HSBC Checking",
        destination="Grab Food",
        category=None,
        budget=None,
        tags=[],
        notes=None,
    )
    assert txn.id == 1
    assert txn.amount == -25.50


def test_compact_transaction_from_api():
    txn = CompactTransaction.from_api(SAMPLE_TRANSACTION)
    assert txn.id == 1
    assert txn.description == "GRAB FOOD"
    assert txn.amount == 25.50
    assert txn.category is None
    assert txn.tags == []
