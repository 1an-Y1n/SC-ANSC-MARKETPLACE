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
Jira Attachment Uploader - Upload files as attachments to Jira issues

Uploads are gated: without --yes the script only prints what would be sent.
The source file must live inside the attachment sandbox, and credential-like
names (.env*, *.pem, *.key, ...) are refused before anything reaches Jira.

Usage:
    python upload_jira_attachment.py <ISSUE_KEY> --file <FILE_PATH> [--yes]

Example:
    python upload_jira_attachment.py DUZ01-1560 --file .devin/TmpWorkDir/attach_root/design.md --yes

Options:
    --file          Source file; must be inside the attachment sandbox
    --attach-root   Sandbox root (default: <repo>/.devin/TmpWorkDir/attach_root)
    --yes           Actually upload; without it the script only previews
    --json          Output in JSON format
"""

import os
import sys
import json
import argparse
import requests
import warnings
from typing import Dict, Any

# Disable SSL warnings for internal servers
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attach_sandbox
from config_loader import load_jira_config, get_jira_auth_header, validate_jira_config

# Load configuration
JIRA_CONFIG = load_jira_config()


def get_auth_header() -> Dict[str, str]:
    """Get authentication header based on auth type"""
    return get_jira_auth_header(JIRA_CONFIG)


def upload_attachment(issue_key: str, file_path: str) -> Dict[str, Any]:
    """Upload a file as attachment to a Jira issue"""
    base_url = JIRA_CONFIG["jira_url"]
    headers = get_auth_header()
    # Note: Do NOT set Content-Type for multipart/form-data, requests will handle it
    headers['X-Atlassian-Token'] = 'no-check'  # Required for file uploads
    
    url = f"{base_url}/rest/api/2/issue/{issue_key}/attachments"
    
    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }
    
    filename = os.path.basename(file_path)    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            resp = requests.post(
                url,
                headers=headers,
                files=files,
                verify=JIRA_CONFIG["ssl_verify"],
                timeout=JIRA_CONFIG["timeout"] * 2  # Longer timeout for uploads
            )
        
        if resp.status_code in [200, 201]:
            result = resp.json()
            if isinstance(result, list) and len(result) > 0:
                attachment = result[0]
                return {
                    "success": True,
                    "attachment_id": attachment.get("id"),
                    "filename": attachment.get("filename"),
                    "size": attachment.get("size"),
                    "issue_key": issue_key
                }
            return {
                "success": True,
                "issue_key": issue_key,
                "response": result
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
    parser = argparse.ArgumentParser(description="Upload attachment to Jira issue")
    parser.add_argument("issue_key", help="Jira issue key (e.g., DUZ01-1560)")
    parser.add_argument("--file", "-f", required=True,
                        help="File to upload; must be inside the attachment sandbox")
    parser.add_argument("--attach-root", metavar="DIR",
                        help="Sandbox root (default: <repo>/.devin/TmpWorkDir/attach_root)")
    parser.add_argument("--yes", action="store_true",
                        help="Actually upload; without it the script only previews")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    valid, error_msg = validate_jira_config(JIRA_CONFIG)
    if not valid:
        print(f"Error: {error_msg}")
        sys.exit(1)

    root = attach_sandbox.resolve_root(args.attach_root)
    try:
        source = attach_sandbox.check_upload_path(root, args.file)
    except attach_sandbox.SandboxError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    issue_key = args.issue_key.upper()
    preview = {
        "issue_key": issue_key,
        "file": source,
        "filename": os.path.basename(source),
        "size": os.path.getsize(source),
        "attach_root": root,
    }

    # Confirmation gate: uploading is the one direction that can leak data to
    # the server, so nothing is sent unless --yes is passed explicitly.
    if not args.yes:
        if args.json:
            preview["status"] = "preview"
            print(json.dumps(preview, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("PREVIEW ONLY - NOTHING UPLOADED")
            print("=" * 60)
            print(f"Issue Key:   {issue_key}")
            print(f"File:        {source}")
            print(f"Size:        {preview['size']} bytes")
            print(f"Sandbox:     {root}")
            print("-" * 60)
            print("Re-run with --yes to upload.")
            print("=" * 60)
        return

    print(f"Uploading {source} to {issue_key}...")

    result = upload_attachment(issue_key, source)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(f"\n{'='*60}")
            print("ATTACHMENT UPLOADED SUCCESSFULLY")
            print(f"{'='*60}")
            print(f"Issue Key:     {issue_key}")
            print(f"Filename:      {result.get('filename', 'N/A')}")
            print(f"Attachment ID: {result.get('attachment_id', 'N/A')}")
            print(f"Size:          {result.get('size', 'N/A')} bytes")
            print(f"{'-'*60}")
            print(f"URL: {JIRA_CONFIG['jira_url']}/browse/{issue_key}")
            print(f"{'='*60}")
        else:
            print(f"\nError: {result['error']}")
            sys.exit(1)


if __name__ == "__main__":
    main()
