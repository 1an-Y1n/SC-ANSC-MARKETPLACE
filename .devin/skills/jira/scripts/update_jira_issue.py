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
Jira Issue Field Update - Change editable fields on one issue

Status is deliberately not editable here: Jira only accepts status changes
through the workflow engine, and a plain PUT silently fails or is rejected.
Use transition_jira_issue.py for that.

Usage:
    python update_jira_issue.py <ISSUE_KEY> --field <KEY>=<VALUE> [--field ...]
    python update_jira_issue.py <ISSUE_KEY> --json '<FIELDS_JSON>' [--dry-run]

Example:
    python update_jira_issue.py DUZ01-1560 --field summary="Fix HS-mode EQ span"
    python update_jira_issue.py DUZ01-1560 --field labels='["mamba","eq"]'
    python update_jira_issue.py DUZ01-1560 --json '{"assignee":{"name":"argon_cheng"}}'

Options:
    --field         Repeatable KEY=VALUE; VALUE is parsed as JSON when valid
                    (["a","b"], true, 123, {"name":"x"}), otherwise kept as text
    --json          Whole fields object as JSON (mutually exclusive with --field)
    --dry-run       Print the payload without sending it
    --json-output   Print the result as JSON
"""

import argparse
import json
import sys
import warnings
from typing import Any, Dict, Tuple

from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

from config_loader import load_jira_config, validate_jira_config
from jira_client import JiraClient, JiraError

# Load configuration
JIRA_CONFIG = load_jira_config()

# Fields Jira does not accept through a plain field update. `status` and
# `resolution` belong to the workflow engine; the rest identify the issue and
# would either be ignored or corrupt the record.
PROTECTED_FIELDS = {
    "key": "the issue key identifies the record",
    "project": "use create_jira_issue.py to move an issue to another project",
    "issuetype": "the issue type is fixed after creation",
    "status": "status changes must go through transition_jira_issue.py",
    "resolution": "resolution is set by the closing transition, not by a field update",
}


def parse_field(raw: str) -> Tuple[str, Any]:
    """Split ``KEY=VALUE`` and JSON-decode VALUE when it is valid JSON."""
    if "=" not in raw:
        raise ValueError("--field expects KEY=VALUE, got: %r" % (raw,))
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError("--field has an empty key: %r" % (raw,))
    try:
        return key, json.loads(value)
    except ValueError:
        return key, value


def build_fields(args) -> Dict[str, Any]:
    """Build the fields payload from either --json or repeated --field."""
    if args.json and args.field:
        raise ValueError("--json and --field are mutually exclusive")

    if args.json:
        try:
            fields = json.loads(args.json)
        except ValueError as exc:
            raise ValueError("--json is not valid JSON: %s" % (exc,))
        if not isinstance(fields, dict):
            raise ValueError("--json must be a JSON object of field -> value")
        return fields

    fields = {}
    for raw in args.field or []:
        key, value = parse_field(raw)
        fields[key] = value
    return fields


def check_protected(fields: Dict[str, Any]) -> None:
    """Reject fields that must not be written through a plain update."""
    blocked = [key for key in fields if key in PROTECTED_FIELDS]
    if not blocked:
        return
    lines = ["refusing to update protected field(s): %s" % ", ".join(sorted(blocked))]
    for key in sorted(blocked):
        lines.append("  %-12s %s" % (key, PROTECTED_FIELDS[key]))
    lines.append("")
    lines.append("For a status change run:")
    lines.append("  python transition_jira_issue.py <ISSUE_KEY> --list")
    raise ValueError("\n".join(lines))


def update_issue(client: JiraClient, issue_key: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """PUT the field payload; Jira answers 204 No Content on success."""
    client.request("PUT", "/issue/%s" % issue_key, data={"fields": fields})
    return {
        "status": "success",
        "issue_key": issue_key,
        "updated_fields": sorted(fields.keys()),
        "url": client.browse_url(issue_key),
    }


def main():
    parser = argparse.ArgumentParser(description="Update editable fields on a Jira issue.")
    parser.add_argument("issue_key", help="Jira issue key (e.g., DUZ01-1560)")
    parser.add_argument("--field", "-f", action="append", metavar="KEY=VALUE",
                        help="Field to set; repeatable. VALUE is JSON-parsed when valid")
    parser.add_argument("--json", dest="json", help="Whole fields object as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print the payload without sending")
    parser.add_argument("--json-output", action="store_true", help="Output the result as JSON")
    args = parser.parse_args()

    valid, error_msg = validate_jira_config(JIRA_CONFIG)
    if not valid:
        print("Error: %s" % error_msg)
        sys.exit(1)

    try:
        fields = build_fields(args)
        check_protected(fields)
    except ValueError as exc:
        print("Error: %s" % exc)
        sys.exit(1)

    if not fields:
        parser.error("nothing to update: pass --field KEY=VALUE or --json '<object>'")

    issue_key = args.issue_key.upper()

    if args.dry_run:
        payload = {"issue_key": issue_key, "fields": fields}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    client = JiraClient(JIRA_CONFIG)
    try:
        result = update_issue(client, issue_key, fields)
    except JiraError as exc:
        print("Error: %s" % exc)
        sys.exit(1)

    if args.json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("ISSUE UPDATED")
        print("=" * 60)
        print("Issue Key:       %s" % issue_key)
        print("Updated Fields:  %s" % ", ".join(result["updated_fields"]))
        print("URL:             %s" % result["url"])
        print("=" * 60)


if __name__ == "__main__":
    main()
