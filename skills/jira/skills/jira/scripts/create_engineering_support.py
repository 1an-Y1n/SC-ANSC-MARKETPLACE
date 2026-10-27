#!/usr/bin/env python3
# Copyright (c) 2026 SerComm Corporation. All Rights Reserved.
#
# SerComm Corporation reserves the right to make changes to this document
# without notice. SerComm Corporation makes no warranty, representation or
# guarantee regarding the suitability of its products for any particular
# purpose.
#
# SerComm Corporation assumes no liability arising out of the application or
# use of any product or circuit.
#
# SerComm Corporation specifically disclaims any and all liability, including
# without limitation consequential or incidental damages; neither does it convey
# any license under its patent rights, nor the rights of others.

"""
Jira Engineering Support Task Creator

Creates Engineering Support tasks in Jira. This issue type has special requirements
and does not support the standard priority field.

Usage:
    python create_engineering_support.py --project <PROJECT_KEY> --summary "<SUMMARY>" --description "<DESCRIPTION>"

Example:
    python create_engineering_support.py --project SWP00 --summary "Modem Service Meeting or Support" --epic "SWP00-186"

Options:
    --project       Project key (e.g., SWP00, DUZ01)
    --summary       Issue summary/title
    --description   Issue description (Jira markup format)
    --epic          Epic key to link this task to (e.g., SWP00-186)
    --assignee      Assignee username (optional)
    --labels        Comma-separated labels (optional)
    --estimate      Original estimate in hours (optional)
    --json          Output result in JSON format
"""

import argparse
import json
import sys
import warnings
from types import SimpleNamespace
from typing import Any, Dict, Optional

# Disable SSL warnings for internal servers
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

from config_loader import load_jira_config, validate_jira_config
from issue_creator import build_payload, create_issue
from jira_client import JiraClient, JiraError

# Load configuration
JIRA_CONFIG = load_jira_config()

ENGINEERING_SUPPORT_TYPE = "Engineering Support"


def create_engineering_support(
    project_key: str,
    summary: str,
    description: str,
    epic_key: Optional[str] = None,
    assignee: Optional[str] = None,
    labels: Optional[list] = None,
    original_estimate: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an Engineering Support task in Jira

    Args:
        project_key: Jira project key
        summary: Issue summary
        description: Issue description in Jira markup
        epic_key: Epic key to link to (optional)
        assignee: Assignee username (optional)
        labels: List of labels (optional)
        original_estimate: Time estimate like "2h", "1d" (optional)

    Returns:
        Dictionary with status and issue details
    """
    client = JiraClient(JIRA_CONFIG)
    args = SimpleNamespace(
        project=project_key,
        summary=summary,
        description=description,
        assignee=assignee,
        labels=labels,
        estimate=original_estimate,
        epic=epic_key,
    )

    try:
        fields, _ = build_payload(
            client, args, ENGINEERING_SUPPORT_TYPE, include_priority=False
        )
        result = create_issue(client, fields, epic_key=epic_key, verify=True)
    except JiraError as exc:
        return {"status": "error", "error": str(exc)}

    return {
        "status": "success",
        "issue_key": result["key"],
        "issue_id": result["id"],
        "issue_url": result["url"],
        "epic_link": result["epic_applied"],
        "epic_key": epic_key if result["epic_applied"] else None,
        "post_create_fixups": result["fixups"],
        "unapplied_fields": result["unapplied"],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create Jira Engineering Support task",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--project", "-p", required=True, help="Project key (e.g., SWP00, DUZ01)"
    )
    parser.add_argument("--summary", "-s", required=True, help="Issue summary/title")
    parser.add_argument(
        "--description", "-d", default="", help="Issue description (Jira markup)"
    )
    parser.add_argument("--epic", "-e", help="Epic key to link to (e.g., SWP00-186)")
    parser.add_argument("--assignee", "-a", help="Assignee username")
    parser.add_argument("--labels", "-l", help="Comma-separated labels")
    parser.add_argument("--estimate", help="Original estimate (e.g., 2h, 1d)")
    parser.add_argument("--json", action="store_true", help="Output result in JSON format")

    args = parser.parse_args()

    # Parse labels
    labels = [l.strip() for l in args.labels.split(",")] if args.labels else None

    # Validate config
    ok, config_error = validate_jira_config(JIRA_CONFIG)
    if not ok:
        result = {"status": "error", "error": config_error}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("Error: %s" % result["error"])
        sys.exit(1)

    # Create issue
    print("Creating Engineering Support task in project '%s'..." % args.project)
    if not args.json:
        print()

    result = create_engineering_support(
        project_key=args.project,
        summary=args.summary,
        description=args.description,
        epic_key=args.epic,
        assignee=args.assignee,
        labels=labels,
        original_estimate=args.estimate,
    )

    # Output result
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "success":
            print("=" * 60)
            print("JIRA ENGINEERING SUPPORT TASK CREATED SUCCESSFULLY")
            print("=" * 60)
            print("Issue Key:  %s" % result["issue_key"])
            print("Issue ID:   %s" % result["issue_id"])
            print("Project:    %s" % args.project)
            print("Type:       Engineering Support")
            print("Summary:    %s" % args.summary)
            if result.get("epic_key"):
                print("Epic:       %s" % result["epic_key"])
            print("-" * 60)
            print("URL: %s" % result["issue_url"])
            print("=" * 60)
        else:
            print("Error: %s" % result["error"])
            sys.exit(1)


if __name__ == "__main__":
    main()
