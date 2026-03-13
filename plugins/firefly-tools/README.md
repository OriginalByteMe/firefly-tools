# Firefly Tools

**Stop manually categorizing bank transactions. Life's too short.**

A Claude Code plugin + MCP server that turns your messy bank statements into a clean, categorized ledger in [Firefly III](https://www.firefly-iii.org/) — the open-source personal finance manager.

---

## Why This Exists

I use Firefly III to track every ringgit I spend. I love that it's open-source, self-hosted, and my financial data stays on my own server — not in some bank's "insights" dashboard I didn't ask for.

But here's the problem: **Malaysian banks are painful.**

No open banking APIs. No CSV exports that just work. You get a PDF statement (if you're lucky), and then you're staring at 200 transactions trying to remember if "POS DEBIT 29481 KL" was groceries or that birthday dinner. Every month. For every account.

This tool fixes that. Drop in a PDF or CSV bank statement, and Claude will:

1. **Parse it** — Claude is surprisingly good at extracting transaction data from PDFs
2. **Import it** — straight into Firefly III via the Data Importer
3. **Categorize everything** — batch-classifying merchants with high confidence, then asking you about the ambiguous ones
4. **Automate it** — set up rules so future transactions are categorized automatically
5. **Build your ledger** — clean, consistent, tagged, budgeted

What used to take an evening now takes a few minutes of confirming suggestions.

---

## What's Inside

This plugin has two parts that work together:

### MCP Server (`src/firefly_mcp/`)

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives Claude direct access to your Firefly III instance. Ten tools covering the full workflow:

| Tool | What it does |
|------|-------------|
| `import_bank_statement` | Upload a CSV + bank config to the Data Importer |
| `get_review_queue` | Find transactions missing categories, tags, or budgets |
| `categorize_transactions` | Batch-apply classifications to transactions |
| `search_transactions` | Query transactions with natural filters |
| `get_spending_summary` | Spending breakdown by category, tag, budget, or account |
| `get_financial_context` | List your existing categories, tags, budgets, and accounts |
| `manage_metadata` | Create, update, or delete tags, categories, budgets, accounts, and bills |
| `manage_automations` | Create, update, delete, enable/disable automation rules |
| `test_automation` | Dry-run or fire automation rules against existing transactions |
| `get_automation_context` | List available trigger keywords, action keywords, and rule groups |

The MCP server works standalone with any MCP-compatible client — Claude Code, Claude Desktop, or others.

### Cowork Scripts (`scripts/`)

> **Disclaimer:** Claude Code's Cowork mode does not currently support loading MCP servers that aren't configured as ACP (Agent Communication Protocol) or SSE (Server-Sent Events) endpoints with OAuth authentication. While you *can* technically ask Cowork to load the MCP server and it may work, it won't do so automatically — it's a known limitation and can be unreliable. The scripts below are the recommended workaround for Cowork mode. They provide the same functionality as the MCP server, are more efficient for agent execution, and include additional data processing capabilities not available in the MCP server.

A complete set of standalone Python scripts that replicate every MCP tool as a CLI command. These scripts are designed for use in **Claude Code Cowork mode** and by **other AI agents** that can execute shell commands but can't load MCP servers.

**API Operation Scripts** (1:1 replacements for MCP tools):

| Script | Replaces MCP Tool | What it does |
|--------|------------------|-------------|
| `firefly_client.py` | *(core module)* | Shared HTTP client, auth, retry logic. Run standalone to test connection. |
| `get_context.py` | `get_financial_context` | Fetch categories, tags, budgets, accounts, bills. Supports caching. |
| `search_transactions.py` | `search_transactions` | Flexible transaction search with all filter options. |
| `spending_summary.py` | `get_spending_summary` | Aggregated spending by category/tag/budget/account with period comparison. |
| `review_queue.py` | `get_review_queue` | Find transactions missing categories, tags, or budgets. |
| `categorize.py` | `categorize_transactions` | Batch-apply categories/tags/budgets from JSON. Supports `--dry-run`. |
| `update_transactions.py` | `update_transactions` | Bulk-update any transaction fields. Supports `--dry-run`. |
| `manage_metadata.py` | `manage_metadata` | CRUD for tags, categories, budgets, accounts, bills. |
| `manage_rules.py` | `manage_automations` / `test_automation` / `get_automation_context` | Full rule management: list, create, test, fire, enable/disable. |
| `discover_recurring.py` | `discover_recurring` | Detect subscription and recurring payment patterns. |
| `import_csv.py` | `import_bank_statement` | Upload CSV + bank config to the Data Importer. |

**Data Processing Scripts** (new — not available in the MCP server):

| Script | What it does |
|--------|-------------|
| `export_transactions.py` | Export transactions to CSV or JSON for external analysis. |
| `spending_report.py` | Generate a full Markdown spending report with category breakdown, budget performance, and trends. |
| `validate_import.py` | Pre-validate a CSV before importing: date/amount parsing, duplicate detection. |
| `detect_duplicates.py` | Scan Firefly for duplicate transactions by date + amount + description similarity. |
| `budget_forecast.py` | Project spending to end of month/quarter using historical trends. |
| `normalize_merchants.py` | Detect inconsistent merchant names and suggest consolidations. |

All scripts output JSON to stdout (except `spending_report.py` which outputs Markdown). They read credentials from the same `.env` file used by the MCP server.

### Claude Code Plugin (`skills/`, `agents/`, `hooks/`)

Workflow automation built on top of the MCP server. This is where the magic happens.

**Skills (slash commands):**

| Command | What it does |
|---------|-------------|
| `/firefly-tools:setup` | Guided first-time setup — creates your config file safely |
| `/firefly-tools:import-and-review` | Full pipeline: parse statement → import → categorize |
| `/firefly-tools:classify-unknowns` | Review and classify uncategorized transactions |
| `/firefly-tools:monthly-review` | End-of-month spending analysis with budget comparison |
| `/firefly-tools:setup-automation` | Interactive rule builder for auto-categorizing transactions |

**Agents (the workers):**

| Agent | Model | Role |
|-------|-------|------|
| `csv-parser` | Sonnet | Extracts transactions from PDF statements → CSV |
| `merchant-classifier` | Haiku | Batch-identifies merchants and suggests categories |

---

## Installation

### From the Claude Open Finance marketplace

```bash
/plugin marketplace add OriginalByteMe/claude-open-finance
/plugin install firefly-tools@claude-open-finance
```

Then run `/firefly-tools:setup` to configure your credentials.

### Prerequisites

- [Firefly III](https://www.firefly-iii.org/) running somewhere (Docker, Unraid, bare metal, etc.)
- [Firefly III Data Importer](https://docs.firefly-iii.org/how-to/data-importer/installation/docker/) running alongside it
- [uv](https://docs.astral.sh/uv/) installed (for running the Python MCP server)

### Claude Desktop (standalone MCP)

Claude Desktop doesn't support third-party plugin marketplaces yet. You can use the MCP server directly:

1. Clone the repo: `git clone https://github.com/OriginalByteMe/claude-open-finance.git`
2. Copy `plugins/firefly-tools/.env.example` to `.env` in the repo root and fill in your credentials
3. Add to Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "firefly": {
      "command": "uv",
      "args": ["run", "--directory", "/full/path/to/claude-open-finance", "firefly-mcp"]
    }
  }
}
```

### Credential Reference

| Value | Where to find it |
|-------|-----------------|
| `FIREFLY_URL` | The URL you use to open Firefly III in your browser |
| `FIREFLY_TOKEN` | Firefly III → Options → Profile → Personal Access Tokens → Create New Token |
| `FIREFLY_IMPORTER_URL` | The URL of your Data Importer instance |
| `FIREFLY_IMPORTER_SECRET` | The `AUTO_IMPORT_SECRET` in your Data Importer's config (min 16 characters) |

---

## Usage

### Import and categorize a bank statement

```
/firefly-tools:import-and-review ~/Downloads/hsbc-march.csv
```

### Clean up uncategorized transactions

```
/firefly-tools:classify-unknowns 14
```

### Set up automation rules

```
/firefly-tools:setup-automation tag all Grab transactions as transport
```

### Monthly spending review

```
/firefly-tools:monthly-review 2026-02
```

### Cowork Mode / Script Usage

All skills work in Cowork mode automatically — they detect when MCP tools are unavailable and fall back to the bundled scripts. You can also use the scripts directly:

```bash
# Test your connection
python scripts/firefly_client.py

# Get your financial context (categories, tags, budgets, accounts)
python scripts/get_context.py --cache

# Search transactions
python scripts/search_transactions.py --query "grab" --date-from 2026-01-01

# Generate a spending report
python scripts/spending_report.py --period 2026-02

# Forecast budget performance
python scripts/budget_forecast.py

# Check for duplicates
python scripts/detect_duplicates.py --days 60

# Export transactions to CSV
python scripts/export_transactions.py --date-from 2026-01-01 --date-to 2026-03-31 --format csv --output q1.csv

# Validate a CSV before importing
python scripts/validate_import.py ~/Downloads/statement.csv --check-duplicates

# Find inconsistent merchant names
python scripts/normalize_merchants.py --days 180
```

The scripts only require Python 3.10+ and `requests` — no additional dependencies beyond what's in the standard library. They use the same `.env` credentials as the MCP server.

---

## Supported Banks

- **HSBC** (Malaysia)
- **Maybank**

The PDF parser agent uses Claude's understanding of document structure, so it handles most bank statement formats. For CSVs, the Data Importer is flexible about column formats.

Want to add your bank? Drop a Data Importer config JSON in `src/firefly_mcp/configs/` and update the detection logic in `src/firefly_mcp/tools/import_tool.py`.

---

## Development

```bash
# From the repo root (MCP server lives at root level)
uv sync --dev
cp plugins/firefly-tools/.env.example .env
# Edit .env with your Firefly III credentials

uv run firefly-mcp      # Run the MCP server
uv run pytest            # Run tests
```

---

## License

MIT
