#!/usr/bin/env python3
"""Compute team productivity metrics from completed pull requests.

Metrics:
    - PR Cycle Time: median, average, and p90 time from creation to merge
    - Throughput: completed PRs per author per month
    - Cycle Time Distribution: fast (<4h), normal (4-24h), slow (24-72h), very slow (>72h)
    - Per-Author breakdown: completed count and median cycle time

Required environment variables:
    AZDO_PAT      Personal Access Token
    AZDO_ORG      Organization name
    AZDO_PROJECT  Project name

Examples:
    python scripts/team_metrics.py
    python scripts/team_metrics.py --since 2025-06-01 --until 2025-12-31
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
    parser = base_parser("Compute team productivity metrics from completed PRs")
    parser.add_argument(
        "--since",
        help="Start date (YYYY-MM-DD). Default: 90 days ago",
    )
    parser.add_argument(
        "--until",
        help="End date (YYYY-MM-DD). Default: today",
    )
    return parser.parse_args()


def parse_date(date_str):
    """Parse an ISO datetime string from the API into a datetime object."""
    if not date_str:
        return None
    date_str = date_str.replace("Z", "+00:00")
    return datetime.fromisoformat(date_str)


def median(values):
    """Return the median of a sorted list of values."""
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def percentile(values, pct):
    """Return the given percentile of a sorted list of values."""
    if not values:
        return 0
    s = sorted(values)
    idx = int(len(s) * pct / 100)
    return s[min(idx, len(s) - 1)]


def compute_cycle_times(prs):
    """Compute cycle time in hours for each completed PR."""
    cycle_times = []
    for pr in prs:
        created = parse_date(pr.get("creationDate", ""))
        closed = parse_date(pr.get("closedDate", ""))
        if created and closed:
            delta = (closed - created).total_seconds() / 3600
            cycle_times.append(delta)
    return cycle_times


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
        since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
    until = args.until or now.strftime("%Y-%m-%d")
    min_time = f"{since}T00:00:00Z"
    max_time = f"{until}T23:59:59Z"

    log.info("Date range: %s to %s", since, until)

    # Fetch completed PRs
    log.info("Fetching completed PRs...")
    prs = client.get_pull_requests(
        status="completed",
        min_time=min_time,
        max_time=max_time,
    )
    log.info("Completed PRs found: %d", len(prs))

    if not prs:
        output_json({
            "since": since,
            "until": until,
            "total_completed": 0,
            "cycle_time": {"median_hours": 0, "avg_hours": 0, "p90_hours": 0},
            "throughput_per_month": [],
            "cycle_time_distribution": {
                "fast_under_4h": 0,
                "normal_4h_to_24h": 0,
                "slow_24h_to_72h": 0,
                "very_slow_over_72h": 0,
            },
            "by_author": [],
        })

    # ── Cycle Time (global) ────────────────────────────────────────────
    cycle_times = compute_cycle_times(prs)

    cycle_time_stats = {
        "median_hours": round(median(cycle_times), 1),
        "avg_hours": round(sum(cycle_times) / len(cycle_times), 1) if cycle_times else 0,
        "p90_hours": round(percentile(cycle_times, 90), 1),
    }

    # ── Cycle Time Distribution ────────────────────────────────────────
    dist = {"fast_under_4h": 0, "normal_4h_to_24h": 0, "slow_24h_to_72h": 0, "very_slow_over_72h": 0}
    for h in cycle_times:
        if h < 4:
            dist["fast_under_4h"] += 1
        elif h < 24:
            dist["normal_4h_to_24h"] += 1
        elif h < 72:
            dist["slow_24h_to_72h"] += 1
        else:
            dist["very_slow_over_72h"] += 1

    # ── Throughput per month ───────────────────────────────────────────
    monthly = defaultdict(lambda: {"authors": set(), "count": 0})
    for pr in prs:
        closed = pr.get("closedDate", "")
        if not closed:
            continue
        month = closed[:7]
        author = pr.get("createdBy", {}).get("displayName", "unknown")
        monthly[month]["authors"].add(author)
        monthly[month]["count"] += 1

    throughput = []
    for month in sorted(monthly):
        count = monthly[month]["count"]
        authors = len(monthly[month]["authors"])
        throughput.append({
            "month": month,
            "completed": count,
            "authors": authors,
            "per_author": round(count / authors, 1) if authors else 0,
        })

    # ── Per-author breakdown ───────────────────────────────────────────
    author_prs = defaultdict(list)
    for pr in prs:
        author = pr.get("createdBy", {}).get("displayName", "unknown")
        created = parse_date(pr.get("creationDate", ""))
        closed = parse_date(pr.get("closedDate", ""))
        if created and closed:
            hours = (closed - created).total_seconds() / 3600
            author_prs[author].append(hours)

    by_author = []
    for author in sorted(author_prs, key=lambda a: len(author_prs[a]), reverse=True):
        times = author_prs[author]
        by_author.append({
            "author": author,
            "completed": len(times),
            "median_hours": round(median(times), 1),
        })

    output_json({
        "since": since,
        "until": until,
        "total_completed": len(prs),
        "cycle_time": cycle_time_stats,
        "throughput_per_month": throughput,
        "cycle_time_distribution": dist,
        "by_author": by_author,
    })


if __name__ == "__main__":
    main()
