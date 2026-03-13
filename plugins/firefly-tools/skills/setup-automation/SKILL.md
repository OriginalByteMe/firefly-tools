---
name: setup-automation
description: Interactive session to create automation rules that auto-categorize transactions in Firefly III
user-invocable: true
allowed-tools: Agent, AskUserQuestion, Bash, Read
argument-hint: [description of what to automate]
---

# Setup Automation Rule

Interactive workflow for creating automation rules in Firefly III that fire when transactions are created or updated.

## Prerequisites

Before starting, read `${CLAUDE_PLUGIN_ROOT}/.env` to check it exists and has no `REPLACE_WITH` placeholders.
If credentials are missing, tell the user to run `/firefly-tools:setup` first and stop.

## Input

`$ARGUMENTS` optionally describes what the user wants to automate (e.g., "tag all Grab transactions as transport").

## Cowork Mode (Script Fallback)

If MCP tools (`firefly:*`) are not available (e.g., in Cowork mode), use the equivalent scripts in `${CLAUDE_PLUGIN_ROOT}/scripts/` via Bash:
- `firefly:get_automation_context` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py context`
- `firefly:get_financial_context` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/get_context.py [--cache]`
- `firefly:manage_automations` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py <action> [options]`
- `firefly:test_automation` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py test --rule-id <id>`
- `firefly:manage_metadata` → `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_metadata.py <action> --name "..."`

All scripts output JSON to stdout.

## Step 1: Gather Context

1. Call `firefly:get_automation_context` (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py context`) to load available trigger keywords, action keywords, and rule groups
2. Call `firefly:get_financial_context("all")` (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/get_context.py --cache`) to load existing categories, tags, budgets, accounts
3. Call `firefly:manage_automations` with action "list" (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py list`) to see existing rules (avoid duplicates)

## Step 2: Design the Rule

If `$ARGUMENTS` provided a description, translate it directly. Otherwise, ask the user.

Map the user's intent to:
- **Triggers**: conditions that must match (description_contains, amount_more, from_account_is, etc.)
- **Actions**: what happens when matched (set_category, add_tag, set_budget, link_to_bill, etc.)
- **Logic**: AND (strict=true, all must match) or OR (strict=false, any suffices)
- **When**: on transaction create (store-journal) or update (update-journal) — default to store-journal
- **Group**: which rule group to place it in

Present the proposed rule clearly:
```
Rule: "Starbucks → Coffee"
Group: Auto-categorize
When: Transaction is created
If ALL match:
  - Description contains "STARBUCKS"
  - Type is withdrawal
Then:
  - Set category to "Food & Dining"
  - Add tag "coffee"
```

## Step 3: Create Missing Entities

If the rule references categories, tags, or budgets that don't exist yet:
1. List what needs to be created
2. Confirm with the user
3. Call `firefly:manage_metadata` (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_metadata.py`) for each

## Step 4: Create and Test

1. Call `firefly:manage_automations` with action "create" (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py create --title "..." --triggers '[...]' --actions '[...]'`)
2. Call `firefly:test_automation` with the new rule_id (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py test --rule-id <id>`) with execute=false to dry-run
3. Show results: "This rule would match X existing transactions"
4. Ask if the user wants to apply it to existing transactions
5. If yes, call `firefly:test_automation` with execute=true (or `python ${CLAUDE_PLUGIN_ROOT}/scripts/manage_rules.py fire --rule-id <id>`)

## Step 5: Summary

Report:
- Rule created: name, group, triggers, actions
- X existing transactions matched (if tested)
- X transactions updated (if executed)
- Remind the user the rule will auto-fire on future transactions
