# 🔥 Firefly Tools

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
4. **Build your ledger** — clean, consistent, tagged, budgeted

What used to take an evening now takes a few minutes of confirming suggestions.

---

## What's Inside

This repo has two parts that work together:

### MCP Server (`src/firefly_mcp/`)

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives Claude direct access to your Firefly III instance. Seven tools covering the full workflow:

| Tool | What it does |
|------|-------------|
| `import_bank_statement` | Upload a CSV + bank config to the Data Importer |
| `get_review_queue` | Find transactions missing categories, tags, or budgets |
| `categorize_transactions` | Batch-apply classifications to transactions |
| `search_transactions` | Query transactions with natural filters |
| `get_spending_summary` | Spending breakdown by category, tag, budget, or account |
| `get_financial_context` | List your existing categories, tags, budgets, and accounts |
| `manage_metadata` | Create new tags, categories, budgets, or adjust budget limits |

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

**Agents (the workers):**

| Agent | Model | Role |
|-------|-------|------|
| `csv-parser` | Sonnet | Extracts transactions from PDF statements → CSV |
| `merchant-classifier` | Haiku | Batch-identifies merchants and suggests categories |

---

## Installation

### Prerequisites

Before you start, you'll need:

- [Firefly III](https://www.firefly-iii.org/) running somewhere (Docker, Unraid, bare metal, etc.)
- [Firefly III Data Importer](https://docs.firefly-iii.org/how-to/data-importer/installation/docker/) running alongside it
- [uv](https://docs.astral.sh/uv/) installed (for running the Python MCP server)

Pick your setup below based on how you use Claude.

---

### Option A: Claude Code (CLI)

The full experience — plugin with skills, agents, and automated workflows.

**1. Install the plugin:**

```bash
claude plugin install OriginalByteMe/firefly-tools
```

**2. Run setup:**

Start Claude Code and run:

```
/firefly-tools:setup
```

This creates a `.env` file in the plugin directory and tells you exactly where it is. Open that file in your text editor and fill in your credentials — **you never type secrets into the chat**.

**3. Start importing:**

```
/firefly-tools:import-and-review ~/Downloads/march-2026-statement.pdf
```

Done. Claude parses the PDF, imports the transactions, classifies them, and asks you about the ambiguous ones.

---

### Option B: Claude Desktop (GUI)

Claude Desktop doesn't support third-party plugins from GitHub yet (only the official marketplace). But you can use the MCP server directly, which gives you all 7 tools — just without the automated skill workflows.

**1. Download this repo:**

Go to the [GitHub repo](https://github.com/OriginalByteMe/firefly-tools) and click **Code → Download ZIP**, or clone it:

```bash
git clone https://github.com/OriginalByteMe/firefly-tools.git
```

Unzip or clone it somewhere permanent — Claude Desktop will reference this folder. For example:
- macOS: `~/claude-plugins/firefly-tools/`
- Windows: `C:\Users\YourName\claude-plugins\firefly-tools\`

**2. Configure your credentials:**

Copy the example config and fill in your values:

```bash
cd firefly-tools
cp .env.example .env
```

Open `.env` in your text editor and replace the placeholder values:

```env
FIREFLY_URL=http://your-server:8080
FIREFLY_TOKEN=your-personal-access-token
FIREFLY_IMPORTER_URL=http://your-server:8081
FIREFLY_IMPORTER_SECRET=your-auto-import-secret
```

**3. Add the MCP server to Claude Desktop:**

Open Claude Desktop settings → **Developer** → **Edit Config** and add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "firefly": {
      "command": "uv",
      "args": ["run", "--directory", "/full/path/to/firefly-tools", "firefly-mcp"]
    }
  }
}
```

> Replace `/full/path/to/firefly-tools` with the actual path where you downloaded the repo.
>
> **Windows users:** Use forward slashes or escaped backslashes in the path:
> `"C:/Users/YourName/claude-plugins/firefly-tools"` or `"C:\\Users\\YourName\\claude-plugins\\firefly-tools"`

**4. Restart Claude Desktop.**

The Firefly tools should now appear in Claude's available tools. You can ask Claude things like:
- "Import my bank statement from ~/Downloads/hsbc-march.csv"
- "Show me uncategorized transactions from the last 2 weeks"
- "Give me a spending summary for February"

> **Note:** Claude Desktop gives you the MCP tools but not the plugin skills (slash commands) or agents. You'll be talking to Claude directly and it will use the tools as needed. When plugin marketplace support expands, you'll get the full automated workflow experience.

---

### Option C: Other MCP Clients (Codex, Open Code, etc.)

The MCP server uses stdio transport and works with any MCP-compatible client. The command to start it is:

```bash
uvx --from git+https://github.com/OriginalByteMe/firefly-tools firefly-mcp
```

Or if you've cloned the repo locally:

```bash
uv run firefly-mcp
```

You'll need the four environment variables set (`FIREFLY_URL`, `FIREFLY_TOKEN`, `FIREFLY_IMPORTER_URL`, `FIREFLY_IMPORTER_SECRET`) either in a `.env` file in your working directory or in your shell environment. Refer to your MCP client's docs for how to configure server connections.

---

### Credential Reference

Whichever installation method you use, you'll need these four values:

| Value | Where to find it |
|-------|-----------------|
| `FIREFLY_URL` | The URL you use to open Firefly III in your browser |
| `FIREFLY_TOKEN` | Firefly III → Options → Profile → Personal Access Tokens → Create New Token |
| `FIREFLY_IMPORTER_URL` | The URL of your Data Importer instance |
| `FIREFLY_IMPORTER_SECRET` | The `AUTO_IMPORT_SECRET` in your Data Importer's config (min 16 characters) |

---

## Usage

Once installed, here's what you can do.

### Import and categorize a bank statement

**Claude Code:**
```
/firefly-tools:import-and-review ~/Downloads/hsbc-march.csv
```

**Claude Desktop / other clients:**
> "Import my bank statement at ~/Downloads/hsbc-march.csv into Firefly and help me categorize the transactions"

Works with both CSV and PDF files. PDFs are parsed by Claude, which handles multi-page statements and extracts transaction data into a clean CSV before importing.

### Clean up uncategorized transactions

**Claude Code:**
```
/firefly-tools:classify-unknowns 14
```

**Claude Desktop / other clients:**
> "Find my uncategorized transactions from the last 14 days and help me classify them"

Groups similar transactions together, suggests classifications, and asks you about the ambiguous ones in batches — not one-by-one.

### Monthly spending review

**Claude Code:**
```
/firefly-tools:monthly-review 2026-02
```

**Claude Desktop / other clients:**
> "Give me a spending review for February 2026 with budget comparisons"

Pulls your spending data, compares against budgets, shows month-over-month trends, and has a conversation with you about what to adjust.

---

## Supported Banks

The import tool auto-detects your bank from the CSV content. Currently ships with configs for:

- **HSBC** (Malaysia)
- **Maybank**

But there's no hard lock to these banks. The PDF parser agent uses Claude's understanding of document structure, so it can handle most bank statement formats. For CSVs, the Firefly III Data Importer is flexible about column formats — as long as your CSV has dates, descriptions, and amounts, it should work.

Want to add your bank? Drop a Data Importer config JSON in `src/firefly_mcp/configs/` and update the detection logic in `src/firefly_mcp/tools/import_tool.py`.

---

## Project Structure

```
firefly-tools/
├── .claude-plugin/plugin.json    # Plugin manifest
├── .mcp.json                     # MCP server registration
├── skills/                       # Slash command workflows
│   ├── setup/                    # /firefly-tools:setup
│   ├── import-and-review/        # /firefly-tools:import-and-review
│   ├── classify-unknowns/        # /firefly-tools:classify-unknowns
│   └── monthly-review/           # /firefly-tools:monthly-review
├── agents/                       # Subagent definitions
│   ├── csv-parser.md             # PDF → CSV extraction
│   └── merchant-classifier.md    # Merchant identification
├── hooks/                        # Lifecycle hooks
│   ├── hooks.json                # Hook configuration
│   └── check-setup.sh            # Nudges setup on session start
├── src/firefly_mcp/              # MCP server (Python)
│   ├── server.py                 # FastMCP server + tool registration
│   ├── client.py                 # Firefly III API client
│   ├── models.py                 # Pydantic models
│   ├── tools/                    # Tool implementations
│   └── configs/                  # Bank-specific import configs
└── tests/                        # Test suite
```

---

## Development

```bash
# Clone and install dependencies
git clone https://github.com/OriginalByteMe/firefly-tools.git
cd firefly-tools
uv sync --dev

# Copy and configure environment
cp .env.example .env
# Edit .env with your Firefly III credentials

# Run the MCP server directly
uv run firefly-mcp

# Run tests
uv run pytest

# Test the plugin locally
claude --plugin-dir .
```

---

## License

MIT
