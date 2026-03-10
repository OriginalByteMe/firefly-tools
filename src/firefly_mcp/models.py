from __future__ import annotations

from pydantic import BaseModel


class TransactionUpdate(BaseModel):
    """Input model for categorize_transactions tool."""

    transaction_id: int
    category: str | None = None
    tags: list[str] | None = None
    budget: str | None = None
    notes: str | None = None


class CompactTransaction(BaseModel):
    """Compact representation of a transaction for LLM consumption."""

    id: int
    date: str
    amount: float
    description: str
    source_account: str
    destination: str
    category: str | None = None
    budget: str | None = None
    tags: list[str] = []
    notes: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> CompactTransaction:
        """Parse a Firefly API transaction response into compact form."""
        attrs = data["attributes"]["transactions"][0]
        return cls(
            id=int(data["id"]),
            date=attrs["date"][:10],
            amount=float(attrs["amount"]),
            description=attrs["description"],
            source_account=attrs.get("source_name", ""),
            destination=attrs.get("destination_name", ""),
            category=attrs.get("category_name"),
            budget=attrs.get("budget_name"),
            tags=attrs.get("tags", []),
            notes=attrs.get("notes"),
        )
