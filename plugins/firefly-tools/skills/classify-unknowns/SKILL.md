---
name: classify-unknowns
description: Interactive session to categorize transactions that are missing tags, categories, or budgets
user-invocable: true
allowed-tools: Agent, AskUserQuestion
argument-hint: [days]
---

# Classify Unknown Transactions

Interactive workflow for reviewing and classifying transactions that are missing metadata.

## Prerequisites

Before starting, read `${CLAUDE_PLUGIN_ROOT}/.env` to check it exists and has no `REPLACE_WITH` placeholders.
If credentials are missing, tell the user to run `/firefly-tools:setup` first and stop.

## Input

`$ARGUMENTS` optionally specifies the number of days to look back (default: 30).

## Step 1: Gather Context

1. Call `firefly:get_financial_context` to load all available categories, tags, budgets
2. Call `firefly:get_review_queue` with the specified days parameter
3. If the queue is empty, tell the user everything is classified and stop
4. Tell the user how many unclassified transactions were found

## Step 2: Batch Classify

1. Collect ALL transaction descriptions from the queue into a single list
2. Dispatch the `merchant-classifier` agent ONCE with the full batch plus the financial context
   - Do NOT dispatch per-transaction or per-group — one call handles everything
3. Group the results by similarity:
   - Same merchant appearing multiple times (e.g., 3x "GRAB*" transactions)
   - Same suggested category
   - Similar descriptions

## Step 3: Interactive Review

Present grouped results to the user. For each group:

**Clear matches (high confidence):**
```
STARBUCKS x3 ($5.20, $4.80, $6.10) → Food & Dining [cafe]
SHELL x2 ($45.00, $52.30) → Transport [fuel]
Apply all? (yes / or correct by name)
```

**Ambiguous (medium/low confidence):**
```
GRAB*2847 ($12.50) → Transport or Food & Dining?
POS DEBIT 29481 ($89.00) → Unknown merchant
```
For these, use `AskUserQuestion` to ask the user directly. Keep questions short and specific:
- "Was this GRAB charge a ride or food delivery?"
- "What was this $89 purchase at POS DEBIT 29481?"

**Batch the interaction.** Present all high-confidence items together for bulk approval, then walk through ambiguous ones. Don't ask one-by-one for clear matches.

## Step 4: Apply

1. If the user wants new categories or tags that don't exist yet, call `firefly:manage_metadata` to create them
2. Call `firefly:categorize_transactions` with all confirmed classifications
3. Summarize:
   - X transactions categorized
   - Y new tags/categories created (if any)
   - Z deferred for later review (if any)
