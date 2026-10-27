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

"""Upload a file as an attachment to a Confluence page (preview by default; pass --yes to upload).

The source file must reside inside the attachment sandbox (attach_sandbox.py),
and credential-like filenames (.env*, *.pem, *.key, ...) are rejected before
any bytes leave the machine.

Usage:
    python upload_confluence_attachment.py <PAGE_ID_OR_URL> --file <FILE_PATH> [--yes]

Example:
    python upload_confluence_attachment.py 12345678 --file .devin/TmpWorkDir/attach_root/arch.png --yes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from typing import Any, Dict, Optional

import requests
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attach_sandbox
from config_loader import (
    get_confluence_auth_header,
    load_confluence_config,
    validate_confluence_config,
)
from confluence_client import ConfluenceClient, ConfluenceError, extract_static_page_id

CONFLUENCE_CONFIG = load_confluence_config()


def upload_attachment(
    page_id: str,
    file_path: str,
    comment: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Upload a file as an attachment to a Confluence page."""
    cfg = config if config is not None else CONFLUENCE_CONFIG
    base_url = (cfg.get("confluence_url") or "").rstrip("/")
    headers = get_confluence_auth_header(cfg)
    # Required by Atlassian multipart upload endpoints to pass XSRF check
    headers["X-Atlassian-Token"] = "no-check"

    url = "%s/rest/api/content/%s/child/attachment" % (base_url, page_id)
    if not os.path.exists(file_path):
        return {"success": False, "error": "File not found: %s" % file_path}

    filename = os.path.basename(file_path)
    form_data = {"comment": comment} if comment else None
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            resp = requests.post(
                url,
                headers=headers,
                files=files,
                data=form_data,
                verify=cfg.get("ssl_verify", False),
                timeout=cfg.get("timeout", 30) * 2,
            )

        if resp.status_code in (200, 201):
            payload = resp.json()
            results = payload.get("results") if isinstance(payload, dict) else payload
            if isinstance(results, list) and results:
                att = results[0]
                size = (att.get("extensions") or {}).get("fileSize", os.path.getsize(file_path))
                return {
                    "success": True,
                    "attachment_id": att.get("id"),
                    "filename": att.get("title") or filename,
                    "size": size,
                    "page_id": str(page_id),
                }
            return {
                "success": True,
                "page_id": str(page_id),
                "filename": filename,
                "response": payload,
            }
        return {
            "success": False,
            "error": "HTTP %s: %s" % (resp.status_code, (resp.text or "")[:500]),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload an attachment to a Confluence page (preview by default; pass --yes to upload)."
    )
    parser.add_argument("page", help="Confluence page ID or URL")
    parser.add_argument(
        "--file", "-f", required=True, help="File to upload; must be inside the attachment sandbox"
    )
    parser.add_argument(
        "--attach-root",
        metavar="DIR",
        help="Sandbox root (default: <repo>/.devin/TmpWorkDir/attach_root)",
    )
    parser.add_argument("--comment", "-c", help="Optional attachment comment")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually upload; without --yes the script only prints a preview",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    valid, error_msg = validate_confluence_config(CONFLUENCE_CONFIG)
    if not valid:
        print("Error: %s" % error_msg)
        sys.exit(1)

    root = attach_sandbox.resolve_root(args.attach_root)
    try:
        source = attach_sandbox.check_upload_path(root, args.file)
    except attach_sandbox.SandboxError as exc:
        print("Error: %s" % exc)
        sys.exit(1)

    client = ConfluenceClient(CONFLUENCE_CONFIG)
    try:
        page_id = extract_static_page_id(args.page) if not args.yes else None
        if not page_id:
            page_id = client.resolve_page_id(args.page)
    except (ValueError, ConfluenceError) as exc:
        print("Error: %s" % exc)
        sys.exit(1)

    preview = {
        "page_id": page_id,
        "file": source,
        "filename": os.path.basename(source),
        "size": os.path.getsize(source),
        "attach_root": root,
        "comment": args.comment or "",
    }

    if not args.yes:
        if args.json:
            preview["status"] = "preview"
            print(json.dumps(preview, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("PREVIEW ONLY - NOTHING UPLOADED")
            print("=" * 60)
            print("Page ID:     %s" % page_id)
            print("File:        %s" % source)
            print("Size:        %d bytes" % preview["size"])
            print("Sandbox:     %s" % root)
            if args.comment:
                print("Comment:     %s" % args.comment)
            print("-" * 60)
            print("Re-run with --yes to upload.")
            print("=" * 60)
        return

    print("Uploading %s to Confluence page %s..." % (source, page_id))
    result = upload_attachment(page_id, source, comment=args.comment, config=CONFLUENCE_CONFIG)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            print("\n" + "=" * 60)
            print("CONFLUENCE ATTACHMENT UPLOADED SUCCESSFULLY")
            print("=" * 60)
            print("Page ID:       %s" % page_id)
            print("Filename:      %s" % result.get("filename", "N/A"))
            print("Attachment ID: %s" % result.get("attachment_id", "N/A"))
            print("Size:          %s bytes" % result.get("size", "N/A"))
            print("-" * 60)
            print("URL: %s" % client.page_url(page_id))
            print("=" * 60)
        else:
            print("\nError: %s" % result["error"])
            sys.exit(1)


if __name__ == "__main__":
    main()
