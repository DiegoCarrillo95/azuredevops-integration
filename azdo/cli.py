import argparse
import json
import logging
import sys


def base_parser(description):
    """Create an ArgumentParser with common arguments shared by all scripts."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--org", help="Azure DevOps organization (default: env AZDO_ORG)")
    parser.add_argument("--project", help="Project name (default: env AZDO_PROJECT)")
    parser.add_argument("--team", help="Team name (default: env AZDO_TEAM)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate the operation without making changes (default for write commands)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute the operation (required for write commands)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable detailed logs on stderr",
    )
    return parser


def setup_logging(verbose=False):
    """Configure logging to stderr (stdout is reserved for JSON output)."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def output_json(data):
    """Print JSON result to stdout and exit with code 0."""
    result = {"ok": True, **data}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


def output_error(message):
    """Print JSON error to stdout and exit with code 1."""
    result = {"ok": False, "error": message}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1)
