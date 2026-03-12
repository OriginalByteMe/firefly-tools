---
name: import-and-review
description: Import a bank statement (CSV or PDF) and interactively review/categorize the imported transactions
user-invocable: true
allowed-tools: Read, Write, Agent, AskUserQuestion
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

## Phase 2: Import

1. Call `firefly:import_bank_statement` with the CSV file path
   - The tool auto-detects the bank from CSV content (looks for "maybank" in the header, defaults to HSBC otherwise)
   - If the user knows it's wrong, they can re-run specifying the bank
2. Report: how many rows were in the CSV, the detected bank, and the import result
3. If the import fails, show the error and stop — don't proceed to review

## Phase 3: Review & Categorize

1. Call `firefly:get_financial_context` to load available categories, tags, budgets, and accounts
2. Call `firefly:get_review_queue` with `days_back=7` to get recently imported transactions
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
7. Call `firefly:categorize_transactions` with the confirmed classifications
   - If any new categories or tags are needed, call `firefly:manage_metadata` to create them first

## Phase 4: Summary

Report:
- Total transactions imported
- How many were auto-categorized (high confidence, user approved)
- How many the user manually classified
- Any left unclassified (suggest running `/firefly-tools:classify-unknowns` later)
