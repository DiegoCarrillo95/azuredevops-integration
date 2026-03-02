#!/usr/bin/env python3
"""List pull requests from an Azure DevOps project with weekly aggregations.

Required environment variables:
    AZDO_PAT      Personal Access Token
    AZDO_ORG      Organization name
    AZDO_PROJECT  Project name

Examples:
    python scripts/pull_requests.py
    python scripts/pull_requests.py --status completed --since 2026-01-01
    python scripts/pull_requests.py --created-by "John"
    python scripts/pull_requests.py --repository "my-repo"
"""
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# Allow importing the azdo package from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from azdo.cli import base_parser, output_error, output_json, setup_logging
from azdo.client import AzDoClient

log = logging.getLogger(__name__)


def parse_args():
    parser = base_parser("List pull requests with weekly aggregations")
    parser.add_argument(
        "--status",
        action="append",
        help="Filter by status: active, completed, abandoned, all (can be repeated). Default: all",
    )
    parser.add_argument(
        "--since",
        help="Start date (YYYY-MM-DD). Default: 30 days ago",
    )
    parser.add_argument(
        "--until",
        help="End date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--created-by",
        help="Filter by author name (substring, case-insensitive)",
    )
    parser.add_argument(
        "--repository",
        help="Filter to a specific repository name",
    )
    return parser.parse_args()


def monday_of_week(dt):
    """Return the Monday (start of ISO week) for a given datetime."""
    return (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")


def parse_date(date_str):
    """Parse an ISO datetime string from the API into a datetime object."""
    if not date_str:
        return None
    # Handle both "2026-02-15T10:30:00Z" and "2026-02-15T10:30:00.000Z"
    date_str = date_str.replace("Z", "+00:00")
    return datetime.fromisoformat(date_str)


def compute_weekly_aggregation(items):
    """Compute opened and closed PR counts grouped by ISO week (Monday)."""
    opened = defaultdict(int)
    closed = defaultdict(int)

    for item in items:
        created = parse_date(item["created_date"])
        if created:
            opened[monday_of_week(created)] += 1

        closed_dt = parse_date(item["closed_date"])
        if closed_dt:
            closed[monday_of_week(closed_dt)] += 1

    all_weeks = sorted(set(opened) | set(closed))
    return [
        {"week": w, "opened": opened[w], "closed": closed[w]}
        for w in all_weeks
    ]


def format_pr(pr):
    """Convert an API pull request into a clean dict for JSON output."""
    created_by = pr.get("createdBy", {})
    repo = pr.get("repository", {})
    source = pr.get("sourceRefName", "")
    target = pr.get("targetRefName", "")

    return {
        "id": pr.get("pullRequestId"),
        "title": pr.get("title", ""),
        "status": pr.get("status", ""),
        "repository": repo.get("name", ""),
        "source_branch": source.removeprefix("refs/heads/"),
        "target_branch": target.removeprefix("refs/heads/"),
        "created_by": created_by.get("displayName", ""),
        "created_date": pr.get("creationDate", ""),
        "closed_date": pr.get("closedDate", ""),
    }


def main():
    args = parse_args()
    setup_logging(args.verbose)

    try:
        client = AzDoClient(org=args.org, project=args.project, team=args.team)
    except ValueError as e:
        output_error(str(e))

    # Date range
    now = datetime.now(timezone.utc)
    if args.since:
        since = args.since
    else:
        since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    until = args.until or now.strftime("%Y-%m-%d")
    min_time = f"{since}T00:00:00Z"
    max_time = f"{until}T23:59:59Z"

    log.info("Date range: %s → %s", since, until)

    # Resolve repository name → ID
    repo_id = None
    if args.repository:
        log.info("Resolving repository '%s'...", args.repository)
        repos = client.get_repositories()
        match = [r for r in repos if r["name"].lower() == args.repository.lower()]
        if not match:
            available = [r["name"] for r in repos]
            output_error(f"Repository '{args.repository}' not found. Available: {available}")
        repo_id = match[0]["id"]

    # Fetch PRs
    statuses = args.status or ["all"]
    all_prs = []
    for status in statuses:
        log.info("Fetching PRs with status '%s'...", status)
        prs = client.get_pull_requests(
            status=status,
            min_time=min_time,
            max_time=max_time,
            repository_id=repo_id,
        )
        all_prs.extend(prs)

    # Deduplicate (in case "all" overlaps with specific statuses)
    seen = set()
    unique_prs = []
    for pr in all_prs:
        pr_id = pr["pullRequestId"]
        if pr_id not in seen:
            seen.add(pr_id)
            unique_prs.append(pr)

    log.info("Total PRs fetched: %d", len(unique_prs))

    # Filter by author
    if args.created_by:
        search = args.created_by.lower()
        unique_prs = [
            pr for pr in unique_prs
            if search in pr.get("createdBy", {}).get("displayName", "").lower()
        ]
        log.info("After author filter: %d", len(unique_prs))

    # Format
    items = [format_pr(pr) for pr in unique_prs]

    # Aggregations
    by_status = defaultdict(int)
    by_repo = defaultdict(int)
    for item in items:
        by_status[item["status"]] += 1
        by_repo[item["repository"]] += 1

    by_week = compute_weekly_aggregation(items)

    output_json({
        "since": since,
        "until": until,
        "total": len(items),
        "by_week": by_week,
        "by_status": dict(by_status),
        "by_repository": dict(by_repo),
        "items": items,
    })


if __name__ == "__main__":
    main()
