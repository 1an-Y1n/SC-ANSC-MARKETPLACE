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
Jira Comment Adder - Add comments to Jira issues

Usage:
    python add_jira_comment.py <ISSUE_KEY> --comment "<COMMENT>"
    
Example:
    python add_jira_comment.py DUZ01-1560 --comment "Design document added"
"""

import sys
import json
import argparse
import requests
import warnings
from typing import Dict, Any

# Disable SSL warnings for internal servers
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

from config_loader import load_jira_config, get_jira_auth_header, validate_jira_config

# Load configuration
JIRA_CONFIG = load_jira_config()


def get_auth_header() -> Dict[str, str]:
    """Get authentication header based on auth type"""
    return get_jira_auth_header(JIRA_CONFIG)


def add_comment(issue_key: str, comment: str) -> Dict[str, Any]:
    """Add a comment to a Jira issue"""
    base_url = JIRA_CONFIG["jira_url"]
    headers = get_auth_header()
    headers['Content-Type'] = 'application/json'
    
    url = f"{base_url}/rest/api/2/issue/{issue_key}/comment"
    data = {"body": comment}
    
    try:
        resp = requests.post(
            url,
            headers=headers,
            json=data,
            verify=JIRA_CONFIG["ssl_verify"],
            timeout=JIRA_CONFIG["timeout"]
        )
        
        if resp.status_code in [200, 201]:
            result = resp.json()
            return {
                "success": True,
                "comment_id": result.get("id"),
                "issue_key": issue_key
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:500]}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Add comment to Jira issue")
    parser.add_argument("issue_key", help="Jira issue key (e.g., DUZ01-1560)")
    parser.add_argument("--comment", "-c", required=True, help="Comment text (Jira markup supported)")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    args = parser.parse_args()
    
    print(f"Adding comment to {args.issue_key}...")
    
    result = add_comment(args.issue_key, args.comment)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(f"\n{'='*60}")
            print("COMMENT ADDED SUCCESSFULLY")
            print(f"{'='*60}")
            print(f"Issue Key:  {args.issue_key}")
            print(f"Comment ID: {result.get('comment_id')}")
            print(f"{'-'*60}")
            print(f"URL: {JIRA_CONFIG['jira_url']}/browse/{args.issue_key}")
            print(f"{'='*60}")
        else:
            print(f"\nError: {result['error']}")
            sys.exit(1)


if __name__ == "__main__":
    main()
