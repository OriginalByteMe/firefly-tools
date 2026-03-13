---
name: import-and-review
description: Import a bank statement (CSV or PDF) and interactively review/categorize the imported transactions
user-invocable: true
allowed-tools: Read, Write, Agent, AskUserQuestion, Bash
argument-hint: <path-to-statement>
---

# Import & Review Workflow

Full workflow for importing a bank statement and categorizing all transactions.

## Prerequisites

Before starting, read `${CLAUDE_PLUGIN_ROOT}/.env` to check it exists and has no `REPLACE_WITH` placeholders.
If credentials are missing, tell the user to run `/firefly-tools:setup` first and stop.

## Input

The user provides a file path via `$ARGUMENTS`. This can be:
- A **CSV file** from a supported bank (HSBC, Maybank)
- A **PDF bank statement** that needs conversion first

If no path is provided, use `AskUserQuestion` to ask for one.

## Phase 1: File Preparation

Check the file extension:

**If PDF:**
1. Dispatch the `csv-parser` agent with the file path
2. The agent will produce a CSV file in the same directory
3. Continue to Phase 2 with the generated CSV path

**If CSV:**
Skip directly to Phase 2.

**If anything else:**
Tell the user only CSV and PDF files are supported and stop.

## Cowork Mode (Script Fallback)

If MCP tools (`firefly:*`) are not available (e.g., in Cowork mode), use the equivalent scripts in `${CLAUDE_PLUGIN_ROOT}/scripts/` via Bash. The script equivalents are:
- `firefly:import_bank_statement` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/import_csv.py <path> [--bank hsbc|maybank] [--dry-run]`
- `firefly:get_financial_context` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/get_context.py [--cache]`
- `firefly:get_review_queue` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/review_queue.py --days 7`
- `firefly:categorize_transactions` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/categorize.py --file updates.json`
- `firefly:manage_metadata` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_metadata.py <action> --name "..."`

All scripts output JSON to stdout. You can optionally pre-validate CSVs with `python ${CLAUDE_PLUGIN_ROOT}/scripts/validate_import.py <path> --check-duplicates`.

## Phase 2: Import

1. Call `firefly:import_bank_statement` with the CSV file path (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/import_csv.py <path>` in Cowork mode)
   - The tool auto-detects the bank from CSV content (looks for "maybank" in the header, defaults to HSBC otherwise)
   - If the user knows it's wrong, they can re-run specifying the bank
2. Report: how many rows were in the CSV, the detected bank, and the import result
3. If the import fails, show the error and stop — don't proceed to review

## Phase 3: Review & Categorize

1. Call `firefly:get_financial_context` (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/get_context.py --cache`) to load available categories, tags, budgets, and accounts
2. Call `firefly:get_review_queue` with `days_back=7` (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/review_queue.py --days 7`) to get recently imported transactions
   - Using 7 days instead of 1 to catch imports that span midnight or take time to process
3. Collect ALL transaction descriptions from the queue into a single list
4. Dispatch the `merchant-classifier` agent ONCE with the full batch of descriptions plus the financial context
   - Do NOT dispatch per-transaction — one call with all descriptions is faster and cheaper
5. Present the results to the user in a table format, grouped by confidence:

   **High confidence (auto-apply these?):**
   | # | Description | Amount | Category | Tags |
   |---|-------------|--------|----------|------|
   | 1 | Starbucks   | $5.20  | Food & Dining | cafe |
   | 2 | Shell       | $45.00 | Transport | fuel |

   **Needs your input:**
   | # | Description | Amount | Suggestion | Why uncertain |
   |---|-------------|--------|------------|---------------|
   | 3 | GRAB*2847   | $12.50 | Transport OR Food & Dining | Could be ride or GrabFood |

6. Use `AskUserQuestion` to let the user:
   - Approve all high-confidence suggestions at once ("yes, apply all")
   - Correct specific ones by number ("change #3 to Food & Dining")
   - Skip ambiguous ones for later
7. Call `firefly:categorize_transactions` (or write a JSON file and run `python ${CLAUDE_PLUGIN_ROOT}/scripts/categorize.py --file updates.json`) with the confirmed classifications
   - If any new categories or tags are needed, call `firefly:manage_metadata` (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_metadata.py`) to create them first

## Phase 4: Summary

Report:
- Total transactions imported
- How many were auto-categorized (high confidence, user approved)
- How many the user manually classified
- Any left unclassified (suggest running `/firefly-tools:classify-unknowns` later)
