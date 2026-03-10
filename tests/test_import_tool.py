import pytest
from unittest.mock import AsyncMock
from pathlib import Path

from firefly_mcp.tools.import_tool import import_bank_statement


@pytest.mark.asyncio
async def test_import_bank_statement_hsbc(tmp_path):
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text("date,description,amount\n2026-03-01,GRAB FOOD,-25.50\n")

    mock_client = AsyncMock()
    mock_client.upload_csv.return_value = (
        "Import complete. 1 transaction(s) imported. 0 duplicate(s) skipped."
    )

    result = await import_bank_statement(
        csv_path=str(csv_file),
        bank="hsbc",
        dry_run=False,
        client=mock_client,
    )
    assert "1 transaction" in result
    mock_client.upload_csv.assert_called_once()
