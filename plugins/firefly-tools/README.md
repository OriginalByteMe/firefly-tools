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
