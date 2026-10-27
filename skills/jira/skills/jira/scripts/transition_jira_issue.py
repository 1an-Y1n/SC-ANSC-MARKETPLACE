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
Jira Workflow Transition - List and apply status transitions

Jira refuses to change "status" through a plain field update: every status
change must go through the workflow engine, which only accepts a transition id
that is valid *right now* for that issue. This script lists those ids and
applies one.

Usage:
    python transition_jira_issue.py <ISSUE_KEY> --list
    python transition_jira_issue.py <ISSUE_KEY> --to <ID|NAME> [--comment "<TEXT>"]

Example:
    python transition_jira_issue.py DUZ01-1560 --list
    python transition_jira_issue.py DUZ01-1560 --to "In Progress" --comment "Starting work"

Options:
    --list          List the transitions available for the issue right now
    --to            Transition id, transition name, or target status name
    --comment       Comment added together with the transition (optional)
    --json          Output in JSON format
"""

import argparse
import json
import sys
import warnings
from typing import Any, Dict, List, Optional, Tuple

from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

from config_loader import load_jira_config, validate_jira_config
from jira_client import JiraClient, JiraError

# Load configuration
JIRA_CONFIG = load_jira_config()


def fetch_transitions(client: JiraClient, issue_key: str) -> List[Dict[str, Any]]:
    """Return the transitions currently available for ``issue_key``."""
    data = client.request("GET", "/issue/%s/transitions" % issue_key)
    transitions = []
    for item in (data or {}).get("transitions", []):
        target = (item.get("to") or {}).get("name", "")
        transitions.append({
            "id": str(item.get("id", "")),
            "name": item.get("name", ""),
            "to": target,
        })
    return transitions


def _candidate_text(transitions: List[Dict[str, Any]]) -> str:
    """Render the available transitions as a copy-pasteable list."""
    if not transitions:
        return "  (no transitions available — check the issue's workflow state)"
    return "\n".join(
        "  %-4s %-28s -> %s" % (t["id"], t["name"], t["to"]) for t in transitions
    )


def resolve_transition(
    transitions: List[Dict[str, Any]], wanted: str
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Resolve ``--to`` against ids, transition names, and target status names.

    Matching order matters: an exact id must win over a name, and an exact name
    over a prefix. Prefixes are only accepted when unambiguous, because
    "In Progress" and "In Review" share the prefix "In ".
    """
    key = str(wanted).strip()
    lowered = key.lower()

    for item in transitions:
        if item["id"] == key:
            return item, ""

    for field in ("name", "to"):
        exact = [t for t in transitions if t[field].lower() == lowered]
        if len(exact) == 1:
            return exact[0], ""

    for field in ("name", "to"):
        prefix = [t for t in transitions if t[field].lower().startswith(lowered)]
        if len(prefix) == 1:
            return prefix[0], ""

    return None, (
        "No transition matches %r (ambiguous or unknown).\n"
        "Available transitions for this issue:\n%s" % (wanted, _candidate_text(transitions))
    )


def apply_transition(
    client: JiraClient, issue_key: str, transition_id: str, comment: Optional[str] = None
) -> Dict[str, Any]:
    """Apply one transition, optionally attaching a comment to it."""
    payload: Dict[str, Any] = {"transition": {"id": str(transition_id)}}
    if comment:
        # Jira Server API v2: the comment must ride along with the transition,
        # otherwise it would be a separate POST and could land even if the
        # transition itself fails.
        payload["update"] = {"comment": [{"add": {"body": comment}}]}
    client.request("POST", "/issue/%s/transitions" % issue_key, data=payload)
    return {"status": "success", "issue_key": issue_key, "transition_id": str(transition_id)}


def _current_status(client: JiraClient, issue_key: str) -> str:
    """Best-effort read of the issue status after a transition."""
    try:
        data = client.request("GET", "/issue/%s" % issue_key, params={"fields": "status"})
        return ((data or {}).get("fields") or {}).get("status", {}).get("name", "")
    except JiraError:
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="List or apply Jira workflow transitions (status changes)."
    )
    parser.add_argument("issue_key", help="Jira issue key (e.g., DUZ01-1560)")
    parser.add_argument("--list", action="store_true", help="List available transitions")
    parser.add_argument("--to", help="Transition id, transition name, or target status name")
    parser.add_argument("--comment", "-c", help="Comment to add together with the transition")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    valid, error_msg = validate_jira_config(JIRA_CONFIG)
    if not valid:
        print("Error: %s" % error_msg)
        sys.exit(1)

    if not args.list and not args.to:
        parser.error("one of --list or --to is required")

    issue_key = args.issue_key.upper()
    client = JiraClient(JIRA_CONFIG)

    try:
        transitions = fetch_transitions(client, issue_key)
    except JiraError as exc:
        print("Error: %s" % exc)
        sys.exit(1)

    if args.list:
        result = {
            "status": "success",
            "issue_key": issue_key,
            "current_status": _current_status(client, issue_key),
            "transitions": transitions,
        }
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("TRANSITIONS FOR %s" % issue_key)
            print("=" * 60)
            print("Current status: %s" % (result["current_status"] or "unknown"))
            print("-" * 60)
            print(_candidate_text(transitions))
            print("=" * 60)
        return

    transition, error = resolve_transition(transitions, args.to)
    if transition is None:
        print("Error: %s" % error)
        sys.exit(1)

    try:
        result = apply_transition(client, issue_key, transition["id"], args.comment)
    except JiraError as exc:
        print("Error: %s" % exc)
        sys.exit(1)

    result["transition_name"] = transition["name"]
    result["target_status"] = transition["to"]
    result["new_status"] = _current_status(client, issue_key)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("TRANSITION APPLIED")
        print("=" * 60)
        print("Issue Key:    %s" % issue_key)
        print("Transition:   %s (id %s)" % (transition["name"], transition["id"]))
        print("New Status:   %s" % (result["new_status"] or transition["to"]))
        print("URL:          %s" % client.browse_url(issue_key))
        print("=" * 60)


if __name__ == "__main__":
    main()
