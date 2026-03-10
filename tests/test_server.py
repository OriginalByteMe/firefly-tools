import asyncio
import pytest


def test_server_has_correct_name():
    from firefly_mcp.server import mcp
    assert mcp.name == "firefly"


@pytest.mark.asyncio
async def test_server_has_all_tools():
    from firefly_mcp.server import mcp

    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}
    expected_tools = {
        "import_bank_statement",
        "get_review_queue",
        "categorize_transactions",
        "search_transactions",
        "get_spending_summary",
        "get_financial_context",
        "manage_metadata",
    }
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"


@pytest.mark.asyncio
async def test_server_has_prompts():
    from firefly_mcp.server import mcp

    prompts = await mcp.list_prompts()
    prompt_names = {p.name for p in prompts}
    expected_prompts = {"review_imports", "monthly_review"}
    assert expected_prompts.issubset(prompt_names), f"Missing prompts: {expected_prompts - prompt_names}"


@pytest.mark.asyncio
async def test_server_has_resources():
    from firefly_mcp.server import mcp

    templates = await mcp.list_resource_templates()
    template_uris = {t.uri_template for t in templates}
    assert any("config" in str(t) for t in template_uris), f"Missing config resource. Found: {template_uris}"


def test_server_has_instructions():
    from firefly_mcp.server import mcp
    assert "Firefly III" in mcp.instructions
    assert "get_financial_context" in mcp.instructions
