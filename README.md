# Azure DevOps Integration

CLI scripts for automated access to Azure DevOps via REST API.
Designed for consumption by AI agents or humans via terminal.

---

## Table of Contents

- [Configuration](#configuration)
- [Conventions](#conventions)
- [Available Scripts](#available-scripts)
  - [sprint_tasks.py](#sprint_taskspy)
- [Internal Modules](#internal-modules)
  - [azdo.client.AzDoClient](#azdoclientazdoclient)
  - [azdo.cli](#azdocli)

---

## Configuration

### Environment Variables

| Variable       | Required | Description                                         |
|----------------|----------|-----------------------------------------------------|
| `AZDO_PAT`     | Yes      | Personal Access Token for authentication            |
| `AZDO_ORG`     | Yes      | Organization name (`dev.azure.com/{ORG}`)           |
| `AZDO_PROJECT` | Yes      | Project name                                        |
| `AZDO_TEAM`    | No       | Team name (required for sprint queries)             |

### Dependencies

```bash
pip install -r requirements.txt
```

Only external dependency: `requests`.

---

## Conventions

All scripts follow the same contract:

| Aspect             | Behavior                                                          |
|--------------------|-------------------------------------------------------------------|
| **Input**          | `argparse` — no `input()`, no interactivity                      |
| **Output (stdout)**| Structured JSON with `"ok": true/false` field                    |
| **Logs (stderr)**  | Via `logging` — use `--verbose` / `-v` for DEBUG level           |
| **Exit code**      | `0` = success, `1` = error                                       |
| **Secrets**        | Via environment variables (`AZDO_*`), never hardcoded            |
| **Idempotency**    | Reads are naturally idempotent; writes check state before acting |
| **Dry-run**        | `--dry-run` simulates without changes; `--apply` executes        |

### Output Format

**Success:**
```json
{
  "ok": true,
  "...": "command-specific fields"
}
```

**Error:**
```json
{
  "ok": false,
  "error": "Descriptive error message"
}
```

### Global Arguments

Available in all scripts via `azdo.cli.base_parser()`:

| Argument     | Type   | Description                                          |
|--------------|--------|------------------------------------------------------|
| `--org`      | string | Organization override (default: `$AZDO_ORG`)        |
| `--project`  | string | Project override (default: `$AZDO_PROJECT`)          |
| `--team`     | string | Team override (default: `$AZDO_TEAM`)                |
| `--dry-run`  | flag   | Simulate operation without side effects              |
| `--apply`    | flag   | Execute the operation (required for writes)          |
| `--verbose`  | flag   | Enable detailed logs on stderr                       |

---

## Available Scripts

### `sprint_tasks.py`

> **Location:** `scripts/sprint_tasks.py`
> **Type:** Read-only
> **Description:** List work items from the current sprint with optional filters.

#### Script-Specific Arguments

| Argument        | Type              | Description                                                    |
|-----------------|-------------------|----------------------------------------------------------------|
| `--assigned-to` | string            | Filter by assignee (substring, case-insensitive)               |
| `--state`       | string (multiple) | Filter by state. Can be repeated. Default: all active states   |
| `--type`        | string (multiple) | Filter by work item type. Can be repeated.                     |

#### Type Shortcuts (`--type`)

| Shortcut   | Resolved Value          |
|------------|-------------------------|
| `pbi`      | Product Backlog Item    |
| `task`     | Task                    |
| `bug`      | Bug                     |
| `feature`  | Feature                 |
| `epic`     | Epic                    |

#### Active States (default filter)

`New`, `Active`, `In Progress`, `Committed`, `To Do`, `Doing`

#### Usage Examples

```bash
# All active work items in the current sprint
python scripts/sprint_tasks.py

# Work items assigned to a person
python scripts/sprint_tasks.py --assigned-to "John"

# Bugs only
python scripts/sprint_tasks.py --type bug

# PBIs and Bugs together
python scripts/sprint_tasks.py --type pbi --type bug

# Only "In Progress" items
python scripts/sprint_tasks.py --state "In Progress"

# Combine filters: John's Bugs that are "New"
python scripts/sprint_tasks.py --assigned-to "John" --type bug --state "New"

# Override project via CLI
python scripts/sprint_tasks.py --project "other-project" --team "other-project Team"

# With detailed logs
python scripts/sprint_tasks.py -v 2>logs.txt
```

#### Output Format

```json
{
  "ok": true,
  "sprint": "Sprint 03-2026",
  "start_date": "2026-02-23",
  "end_date": "2026-03-09",
  "total_in_sprint": 105,
  "matched": 4,
  "items": [
    {
      "id": 12345,
      "type": "Product Backlog Item",
      "state": "Committed",
      "title": "Implement feature X",
      "assigned_to": "John Smith",
      "priority": 4,
      "effort": null,
      "tags": ""
    },
    {
      "id": 12346,
      "type": "Bug",
      "state": "New",
      "title": "Fix error message on screen Y",
      "assigned_to": "John Smith",
      "priority": 2,
      "effort": null,
      "tags": "",
      "severity": "3 - Medium"
    }
  ]
}
```

#### Item Fields

| Field         | Type         | Present In  | Description                            |
|---------------|--------------|-------------|----------------------------------------|
| `id`          | int          | All         | Work item ID                           |
| `type`        | string       | All         | Type (Task, Bug, PBI, etc.)            |
| `state`       | string       | All         | Current state                          |
| `title`       | string       | All         | Item title                             |
| `assigned_to` | string       | All         | Assignee name (empty if unassigned)    |
| `priority`    | int \| null  | All         | Priority (1=critical, 4=low)           |
| `effort`      | float \| null| All         | Effort / story points                  |
| `tags`        | string       | All         | Tags separated by `;`                  |
| `severity`    | string       | Bug only    | Severity (e.g. `"3 - Medium"`)        |

---

## Internal Modules

### `azdo.client.AzDoClient`

> **Location:** `azdo/client.py`

Azure DevOps REST API client. Manages authentication, HTTP session, and API calls.

#### Constructor

```python
AzDoClient(*, org=None, project=None, team=None, pat=None)
```

Explicit parameters take priority over environment variables.

#### Public Methods

| Method                                  | Return        | Description                                       |
|-----------------------------------------|---------------|---------------------------------------------------|
| `get_current_iteration()`               | `dict \| None`| Return the current sprint/iteration for the team  |
| `get_iteration_work_item_ids(id)`       | `list[int]`   | Work item IDs in an iteration                     |
| `get_work_items_batch(ids, fields=None)`| `list[dict]`  | Work item details in batch (max 200/call)         |

#### Default Fields (`get_work_items_batch`)

When `fields=None`, fetches:

- `System.Id`
- `System.Title`
- `System.State`
- `System.WorkItemType`
- `System.AssignedTo`
- `System.Tags`
- `Microsoft.VSTS.Common.Priority`
- `Microsoft.VSTS.Common.Severity`
- `Microsoft.VSTS.Scheduling.Effort`

---

### `azdo.cli`

> **Location:** `azdo/cli.py`

Shared CLI utilities for all scripts.

#### Functions

| Function                     | Description                                                    |
|------------------------------|----------------------------------------------------------------|
| `base_parser(description)`   | Create `ArgumentParser` with global arguments (`--org`, etc.) |
| `setup_logging(verbose)`     | Configure `logging` to stderr                                 |
| `output_json(data)`          | Print `{"ok": true, ...}` to stdout and call `sys.exit(0)`   |
| `output_error(message)`      | Print `{"ok": false, ...}` to stdout and call `sys.exit(1)`  |

---

## Project Structure

```
azuredevops_integration/
├── README.md                   # This documentation
├── requirements.txt            # Dependencies (requests)
├── azdo/
│   ├── __init__.py
│   ├── client.py               # AzDoClient — authentication and API calls
│   └── cli.py                  # Base parser, JSON output, logging
└── scripts/
    └── sprint_tasks.py         # List work items from the current sprint
```
