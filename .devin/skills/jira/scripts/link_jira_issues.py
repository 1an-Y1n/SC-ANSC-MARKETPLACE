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
Jira Issue Link - Link two issues with any link type

`link_tasks_to_epic.py` only writes the Epic Link custom field; this script
covers the general "issue link" relation (Blocks / Relates / Duplicates ...)
that lives under a different REST endpoint.

Direction matters and is easy to get backwards:
    --outward KEY  the issue that "does" the action (e.g. the one that blocks)
    --inward  KEY  the issue the action is done to (e.g. the one being blocked)
So "A blocks B" is:  --type Blocks --outward A --inward B

Usage:
    python link_jira_issues.py --list-types
    python link_jira_issues.py --type <NAME> --outward <KEY> --inward <KEY>

Example:
    python link_jira_issues.py --type Blocks --outward DUZ01-1600 --inward DUZ01-1560

Options:
    --list-types    List the link types available on this Jira instance
    --type          Link type name (e.g. Blocks, Cloners, Relates)
    --outward       Outward issue key
    --inward        Inward issue key
    --dry-run       Print the payload without sending it
    --json          Output in JSON format
"""

import argparse
import json
import sys
import warnings
from typing import Any, Dict, List

from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

from config_loader import load_jira_config, validate_jira_config
from jira_client import JiraClient, JiraError

# Load configuration
JIRA_CONFIG = load_jira_config()


def list_link_types(client: JiraClient) -> List[Dict[str, Any]]:
    """Return the link types defined on this Jira instance."""
    data = client.request("GET", "/issueLinkType")
    return [
        {
            "id": str(item.get("id", "")),
            "name": item.get("name", ""),
            "inward": item.get("inward", ""),
            "outward": item.get("outward", ""),
        }
        for item in (data or {}).get("issueLinkTypes", [])
    ]


def create_link(client: JiraClient, link_type: str, outward_key: str, inward_key: str) -> Dict[str, Any]:
    """Create one issue link between two issues."""
    payload = {
        "type": {"name": link_type},
        "outwardIssue": {"key": outward_key},
        "inwardIssue": {"key": inward_key},
    }
    client.request("POST", "/issueLink", data=payload)
    return {
        "status": "success",
        "link_type": link_type,
        "outward": outward_key,
        "inward": inward_key,
    }


def main():
    parser = argparse.ArgumentParser(description="Link two Jira issues with a named link type.")
    parser.add_argument("--list-types", action="store_true", help="List available link types")
    parser.add_argument("--type", "-t", help="Link type name (e.g. Blocks)")
    parser.add_argument("--outward", "-o", help="Outward issue key")
    parser.add_argument("--inward", "-i", help="Inward issue key")
    parser.add_argument("--dry-run", action="store_true", help="Print the payload without sending")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    valid, error_msg = validate_jira_config(JIRA_CONFIG)
    if not valid:
        print("Error: %s" % error_msg)
        sys.exit(1)

    client = JiraClient(JIRA_CONFIG)

    if args.list_types:
        try:
            types = list_link_types(client)
        except JiraError as exc:
            print("Error: %s" % exc)
            sys.exit(1)
        if args.json:
            print(json.dumps(types, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("AVAILABLE LINK TYPES")
            print("=" * 60)
            for item in types:
                print("%-16s outward: %-24s inward: %s"
                      % (item["name"], item["outward"], item["inward"]))
            print("=" * 60)
        return

    missing = [name for name in ("type", "outward", "inward") if not getattr(args, name)]
    if missing:
        parser.error("--list-types or all of --type/--outward/--inward are required (missing: %s)"
                     % ", ".join("--" + name for name in missing))

    outward_key = args.outward.upper()
    inward_key = args.inward.upper()

    if args.dry_run:
        print(json.dumps({
            "type": {"name": args.type},
            "outwardIssue": {"key": outward_key},
            "inwardIssue": {"key": inward_key},
        }, indent=2, ensure_ascii=False))
        return

    try:
        result = create_link(client, args.type, outward_key, inward_key)
    except JiraError as exc:
        print("Error: %s" % exc)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("ISSUE LINK CREATED")
        print("=" * 60)
        print("Link Type:  %s" % result["link_type"])
        print("Outward:    %s" % outward_key)
        print("Inward:     %s" % inward_key)
        print("URL:        %s" % client.browse_url(outward_key))
        print("=" * 60)


if __name__ == "__main__":
    main()
