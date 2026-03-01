# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI toolkit for Azure DevOps automation via REST API. Scripts are designed to be consumed by AI agents (OpenClaw) and humans alike, outputting structured JSON on stdout.

## Running Scripts

```bash
# Install dependencies
pip install -r requirements.txt

# Run with environment variables
export AZDO_PAT="..."
export AZDO_ORG="my-org"
export AZDO_PROJECT="my-project"
export AZDO_TEAM="my-project Team"
python scripts/sprint_tasks.py
python scripts/sprint_tasks.py --assigned-to "John" --type bug --type pbi
```

There is no build step, test suite, or linter configured.

## Architecture

```
azdo/           → Shared library (imported by all scripts)
  client.py     → AzDoClient class: auth, session, API calls
  cli.py        → base_parser(), output_json(), output_error(), setup_logging()
scripts/        → CLI entry points (one per capability)
README.md       → Full usage documentation and API reference
```

**Data flow in every script:**
`parse args` → `AzDoClient(env + overrides)` → `API calls` → `filter/transform` → `output_json()` on stdout

## CLI Contract (all scripts must follow)

- **Input:** `argparse` only — no `input()`, no interactivity
- **stdout:** JSON with `"ok": true/false` — nothing else
- **stderr:** `logging` messages (enable DEBUG with `--verbose`)
- **Exit codes:** `0` success, `1` error
- **Env vars for secrets:** `AZDO_PAT`, `AZDO_ORG`, `AZDO_PROJECT`, `AZDO_TEAM`
- **Write operations** require `--apply`; default to `--dry-run`
- **Read operations** are naturally idempotent

## Adding a New Script

1. Create `scripts/<name>.py` with `#!/usr/bin/env python3`
2. Add `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))` for imports
3. Use `base_parser()` from `azdo.cli` for argument parsing (gives you `--org`, `--project`, `--team`, `--dry-run`, `--apply`, `--verbose` for free)
4. Use `AzDoClient` from `azdo.client` for API access
5. End with `output_json(data)` or `output_error(message)` — never `print()` to stdout directly
6. Add the script to the "Available Scripts" section in `README.md`
