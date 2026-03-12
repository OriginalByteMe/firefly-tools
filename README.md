# Claude Open Finance

A Claude Code plugin marketplace for open-source personal finance tools.

Browse available plugins, install the ones you need, and automate your financial workflows with Claude.

---

## Quick Start

**1. Add the marketplace:**

```bash
/plugin marketplace add OriginalByteMe/claude-open-finance
```

**2. Browse available plugins:**

```bash
/plugin search @claude-open-finance
```

**3. Install a plugin:**

```bash
/plugin install firefly-tools@claude-open-finance
```

---

## Available Plugins

### Firefly Tools

Automate personal finance with [Firefly III](https://www.firefly-iii.org/) — the open-source budgeting app.

- Import bank statements (PDF or CSV) into Firefly III
- AI-powered transaction categorization with batch classification
- Automation rules that auto-categorize future transactions
- Monthly spending reviews with budget comparisons
- Supports HSBC Malaysia and Maybank out of the box

**Install:**

```bash
/plugin install firefly-tools@claude-open-finance
```

Then run `/firefly-tools:setup` to configure your Firefly III credentials.

See [`plugins/firefly-tools/README.md`](plugins/firefly-tools/README.md) for full documentation.

---

## For Contributors

Want to add a new finance tool to the marketplace? Each plugin lives in its own directory under `plugins/` and must be fully self-contained:

```
plugins/your-tool/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── .mcp.json                # MCP server config (if applicable)
├── skills/                  # Slash command workflows
├── agents/                  # Subagent definitions
├── hooks/                   # Lifecycle hooks
├── src/                     # Source code
└── tests/                   # Test suite
```

Then add an entry to `.claude-plugin/marketplace.json` to register it in the marketplace.

---

## License

MIT
