#!/usr/bin/env python3
"""List active work items from the current sprint of a team in Azure DevOps.

Required environment variables:
    AZDO_PAT      Personal Access Token
    AZDO_ORG      Organization name
    AZDO_PROJECT  Project name
    AZDO_TEAM     Team name

Examples:
    python scripts/sprint_tasks.py
    python scripts/sprint_tasks.py --assigned-to "John"
    python scripts/sprint_tasks.py --state "In Progress" --state "To Do"
    python scripts/sprint_tasks.py --type Task --type Bug
"""
import logging
import os
import sys

# Allow importing the azdo package from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from azdo.cli import base_parser, output_error, output_json, setup_logging
from azdo.client import AzDoClient

log = logging.getLogger(__name__)

ACTIVE_STATES = {"New", "Active", "In Progress", "Committed", "To Do", "Doing"}

# Shortcuts for --type (accepts short or full name)
TYPE_ALIASES = {
    "pbi": "Product Backlog Item",
    "product backlog item": "Product Backlog Item",
    "task": "Task",
    "bug": "Bug",
    "feature": "Feature",
    "epic": "Epic",
}


def parse_args():
    parser = base_parser("List active work items from the current sprint")
    parser.add_argument(
        "--assigned-to",
        help="Filter by assignee (substring, case-insensitive)",
    )
    parser.add_argument(
        "--state",
        action="append",
        help="Filter by state (can be used multiple times). Default: all active states",
    )
    parser.add_argument(
        "--type",
        action="append",
        dest="wi_type",
        help="Filter by type: task, bug, pbi, feature, epic (can be used multiple times)",
    )
    return parser.parse_args()


def format_work_item(wi):
    """Convert an API work item into a clean dict for JSON output."""
    fields = wi["fields"]
    assigned = fields.get("System.AssignedTo", {})
    assigned_name = (
        assigned.get("displayName", "")
        if isinstance(assigned, dict)
        else ""
    )
    wi_type = fields.get("System.WorkItemType", "")

    item = {
        "id": fields["System.Id"],
        "type": wi_type,
        "state": fields.get("System.State", ""),
        "title": fields.get("System.Title", ""),
        "assigned_to": assigned_name,
        "priority": fields.get("Microsoft.VSTS.Common.Priority"),
        "effort": fields.get("Microsoft.VSTS.Scheduling.Effort"),
        "tags": fields.get("System.Tags", ""),
    }

    # Severity only applies to Bugs
    if wi_type == "Bug":
        item["severity"] = fields.get("Microsoft.VSTS.Common.Severity", "")

    return item


def main():
    args = parse_args()
    setup_logging(args.verbose)

    try:
        client = AzDoClient(org=args.org, project=args.project, team=args.team)
    except ValueError as e:
        output_error(str(e))

    # Current sprint
    log.info("Fetching current sprint...")
    iteration = client.get_current_iteration()
    if not iteration:
        output_error("No current sprint found for the team.")

    sprint_name = iteration["name"]
    attrs = iteration.get("attributes", {})
    start_date = (attrs.get("startDate") or "")[:10]
    end_date = (attrs.get("finishDate") or "")[:10]
    log.info("Sprint: %s (%s → %s)", sprint_name, start_date, end_date)

    # Work items in sprint
    log.info("Fetching work items...")
    ids = client.get_iteration_work_item_ids(iteration["id"])
    total_in_sprint = len(ids)
    log.info("Total work items in sprint: %d", total_in_sprint)

    if not ids:
        output_json({
            "sprint": sprint_name,
            "start_date": start_date,
            "end_date": end_date,
            "total_in_sprint": 0,
            "matched": 0,
            "items": [],
        })

    work_items = client.get_work_items_batch(ids)

    # Filter by active states
    allowed_states = set(args.state) if args.state else ACTIVE_STATES
    items = [
        wi for wi in work_items
        if wi["fields"].get("System.State") in allowed_states
    ]

    # Filter by type (resolve aliases: pbi → Product Backlog Item)
    if args.wi_type:
        resolved_types = {
            TYPE_ALIASES.get(t.lower(), t) for t in args.wi_type
        }
        items = [
            wi for wi in items
            if wi["fields"].get("System.WorkItemType", "") in resolved_types
        ]

    # Filter by assignee
    if args.assigned_to:
        search = args.assigned_to.lower()
        items = [
            wi for wi in items
            if search in (
                wi["fields"]
                .get("System.AssignedTo", {})
                .get("displayName", "")
                .lower()
                if isinstance(wi["fields"].get("System.AssignedTo"), dict)
                else ""
            )
        ]

    formatted = [format_work_item(wi) for wi in items]
    log.info("Matched work items: %d", len(formatted))

    output_json({
        "sprint": sprint_name,
        "start_date": start_date,
        "end_date": end_date,
        "total_in_sprint": total_in_sprint,
        "matched": len(formatted),
        "items": formatted,
    })


if __name__ == "__main__":
    main()
