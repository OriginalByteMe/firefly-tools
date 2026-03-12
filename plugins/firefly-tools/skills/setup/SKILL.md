---
name: setup
description: Set up Firefly III credentials for this plugin. Run this first after installing.
user-invocable: true
allowed-tools: Read, Write, AskUserQuestion
---

# Firefly III Setup

Guide the user through connecting to their Firefly III instance. Credentials are NEVER entered in chat — they are written to a local file that the user edits externally in their own editor.

## IMPORTANT: Security Rules

- **NEVER ask the user to paste secrets, tokens, or passwords in chat**
- **NEVER display or echo credential values in output**
- **NEVER try to open editors, browsers, or other programs on the user's machine**
- If the user accidentally pastes a secret in chat, warn them and suggest they rotate the token

## Step 1: Check Existing Configuration

Read the file `${CLAUDE_PLUGIN_ROOT}/.env`.

- If it exists and values are NOT placeholders (don't contain `REPLACE_WITH`):
  - Try calling `firefly:get_financial_context` to verify the connection
  - **Success:** Tell the user they're already connected, show their account names, and stop
  - **Failure:** Tell them the connection failed, show the file path, and suggest they double-check the values in their editor. Stop.
- If the file doesn't exist or has placeholder values, continue to Step 2

## Step 2: Create the Template .env File

Write a `.env` file at `${CLAUDE_PLUGIN_ROOT}/.env` with placeholder values:

```
# Firefly III MCP Server Configuration
# =====================================
# Edit this file with your actual credentials.
# Do NOT paste these values in the Claude chat window.
#
# This file is gitignored and stays local to this directory.
#
# WHERE TO FIND EACH VALUE:
#
# FIREFLY_URL
#   The URL you use to access Firefly III in your browser.
#   Example: http://192.168.1.100:8080 or https://firefly.yourdomain.com
#
# FIREFLY_TOKEN
#   A Personal Access Token from Firefly III.
#   Go to: Firefly III → Options (top-right) → Profile
#   Scroll to "Personal Access Tokens" → Create New Token
#   Copy the token immediately — it's only shown once.
#
# FIREFLY_IMPORTER_URL
#   The URL of your Firefly III Data Importer instance.
#   Example: http://192.168.1.100:8081
#
# FIREFLY_IMPORTER_SECRET
#   The AUTO_IMPORT_SECRET from your Data Importer's config.
#   Must be at least 16 characters.

FIREFLY_URL=REPLACE_WITH_YOUR_FIREFLY_URL
FIREFLY_TOKEN=REPLACE_WITH_YOUR_API_TOKEN
FIREFLY_IMPORTER_URL=REPLACE_WITH_YOUR_IMPORTER_URL
FIREFLY_IMPORTER_SECRET=REPLACE_WITH_YOUR_IMPORTER_SECRET
```

## Step 3: Tell the User What to Do

Display this clearly:

> **I've created your config file at:**
>
> `<absolute path to .env file>`
>
> Open that file in your text editor (VS Code, Notepad, vim, etc.) and replace the four `REPLACE_WITH_...` values with your actual credentials. The file itself has comments explaining where to find each value.
>
> Once you've saved it, come back here and let me know — I'll verify the connection works.

Then use `AskUserQuestion` to ask: "Let me know when you've saved your credentials and I'll verify the connection."

## Step 4: Verify

Once the user confirms:
1. Read the `.env` file — check if any `REPLACE_WITH` placeholders remain (do NOT display the actual values)
2. If placeholders remain, tell the user which specific fields still need to be filled in
3. If all fields are filled, call `firefly:get_financial_context` to test the connection
   - **Success:** Show their account names and suggest trying `/firefly-tools:import-and-review`
   - **Failure:** Show the error message (without exposing credentials) and suggest what to check:
     - "Connection refused" → wrong URL or service not running
     - "401/403" → invalid or expired token
     - "Importer error" → check importer URL and secret
