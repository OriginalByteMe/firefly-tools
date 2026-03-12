---
name: monthly-review
description: Conduct an end-of-month financial review with spending analysis, budget performance, and transaction audit
user-invocable: true
allowed-tools: Agent, AskUserQuestion
argument-hint: [YYYY-MM]
---

# Monthly Financial Review

Guided end-of-month financial review workflow.

## Prerequisites

Before starting, read `${CLAUDE_PLUGIN_ROOT}/.env` to check it exists and has no `REPLACE_WITH` placeholders.
If credentials are missing, tell the user to run `/firefly-tools:setup` first and stop.

## Input

`$ARGUMENTS` optionally specifies the month to review (format: YYYY-MM). Defaults to the previous month.

## Date Handling

Convert the target month to the date range format the MCP tools expect:
- Start date: `YYYY-MM-01`
- End date: `YYYY-MM-{last day}` (28/29/30/31 depending on month)
- Use period format `YYYY-MM-DD:YYYY-MM-DD` when calling `firefly:get_spending_summary`
- For the previous month comparison, calculate the month before the target month the same way

## Phase 1: Data Collection

Call these (they can run in parallel):
1. `firefly:get_spending_summary` with period `{start}:{end}`, grouped by `category`
2. `firefly:get_spending_summary` with period `{start}:{end}`, grouped by `budget`
3. `firefly:get_spending_summary` with period `{start}:{end}`, grouped by `tag`
4. `firefly:get_review_queue` with enough `days_back` to cover the target month

Also fetch prior month data for comparison:
5. `firefly:get_spending_summary` with prior month period, grouped by `category`

## Phase 2: Unclassified Check

If there are unclassified transactions from the review period:
1. Tell the user: "Found X unclassified transactions from {month}. These won't appear in the spending breakdown."
2. Use `AskUserQuestion`: "Want to classify them now, or continue with the review as-is?"
3. If they want to classify, tell them to run `/firefly-tools:classify-unknowns` and come back to this review after

## Phase 3: Spending Report

Present a clear breakdown. Use tables for readability:

**Top Categories:**
| Category | Amount | % of Total | vs Last Month |
|----------|--------|------------|---------------|
| Food & Dining | $450 | 28% | +12% |
| Transport | $200 | 12% | -5% |

**Budget Performance:**
| Budget | Spent | Limit | Remaining | Status |
|--------|-------|-------|-----------|--------|
| Groceries | $380 | $400 | $20 | On track |
| Eating Out | $450 | $300 | -$150 | Over budget |

**Largest Transactions** (top 5 by amount — for awareness, not judgment):
| Date | Description | Amount | Category |
|------|-------------|--------|----------|

## Phase 4: Discussion

Present 2-3 observations based on the data. Focus on what's actionable:
- Budgets that went over or are close to the limit
- Categories with big month-over-month changes
- Any surprising large transactions

Use `AskUserQuestion` to discuss. This is a conversation — ask what they think, not just dump data. Examples:
- "Eating out was $150 over budget this month. Was that expected, or something to adjust?"
- "Transport dropped 5% — anything change there?"

Keep it to 2-3 questions max. Don't interrogate the user about every category.

## Phase 5: Actions

Based on the discussion, offer concrete next steps (only suggest what's relevant):
- Adjust a budget limit: "Want me to raise the Eating Out budget to $400?"
- Create a new tag for tracking: "Want to start tagging delivery vs dine-in?"
- Note for next month: summarize any goals the user mentioned

Only call `firefly:manage_metadata` if the user agrees to a specific change. Don't make changes without confirmation.
