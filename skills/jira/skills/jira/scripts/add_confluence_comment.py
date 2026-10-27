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

"""Add a comment to a Confluence page (preview by default; pass --yes to post).

Usage:
    python add_confluence_comment.py <PAGE_ID_OR_URL> --comment "<TEXT>" [--yes]
    python add_confluence_comment.py <PAGE_ID_OR_URL> --comment-file comment.md [--yes]

Examples:
    python add_confluence_comment.py 12345678 --comment "Reviewed and verified."
    python add_confluence_comment.py 12345678 --comment "Reviewed and verified." --yes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from typing import Any, Dict

from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_confluence_config, validate_confluence_config
from confluence_client import (
    VALID_FORMATS,
    ConfluenceClient,
    ConfluenceError,
    extract_static_page_id,
    load_text_source,
    prepare_body,
)

CONFLUENCE_CONFIG = load_confluence_config()


def build_comment_payload(page_id: str, body_value: str, representation: str) -> Dict[str, Any]:
    """Build the Confluence REST API POST payload for a page comment."""
    return {
        "type": "comment",
        "container": {"id": str(page_id), "type": "page"},
        "body": {
            representation: {
                "value": body_value,
                "representation": representation,
            }
        },
    }


def add_comment(
    client: ConfluenceClient,
    page_id: str,
    body_value: str,
    representation: str,
) -> Dict[str, Any]:
    """Post a comment on a Confluence page (retry_5xx=False to avoid duplicates)."""
    payload = build_comment_payload(page_id, body_value, representation)
    created = client.request("POST", "/content", data=payload, retry_5xx=False)
    comment_id = str(created.get("id", ""))
    return {
        "status": "success",
        "page_id": str(page_id),
        "comment_id": comment_id,
        "url": client.page_url(str(page_id)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a comment to a Confluence page (preview by default; pass --yes to post)."
    )
    parser.add_argument("page", help="Confluence page ID or URL")
    parser.add_argument("--comment", "-c", help="Comment text")
    parser.add_argument("--comment-file", help="Path to UTF-8 file containing comment text")
    parser.add_argument(
        "--format",
        choices=VALID_FORMATS,
        default="markdown",
        help="Input comment format: markdown (default), storage (XHTML), or wiki",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually post the comment; without --yes the script only prints a preview",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    valid, error_msg = validate_confluence_config(CONFLUENCE_CONFIG)
    if not valid:
        print("Error: %s" % error_msg, file=sys.stderr)
        sys.exit(1)

    try:
        raw_comment = load_text_source(
            args.comment, args.comment_file, "--comment", "--comment-file"
        )
        body_value, representation = prepare_body(raw_comment, args.format)
    except ValueError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    client = ConfluenceClient(CONFLUENCE_CONFIG)
    try:
        page_id = extract_static_page_id(args.page) if not args.yes else None
        if not page_id:
            page_id = client.resolve_page_id(args.page)
    except (ValueError, ConfluenceError) as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    if not args.yes:
        preview = {
            "status": "preview",
            "action": "comment",
            "page_id": page_id,
            "format": args.format,
            "representation": representation,
            "comment_length": len(body_value),
            "comment_preview": body_value[:500],
            "url": client.page_url(page_id),
        }
        if args.json:
            print(json.dumps(preview, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("PREVIEW ONLY - COMMENT NOT POSTED")
            print("=" * 60)
            print("Page ID:        %s" % page_id)
            print("Input Format:   %s -> %s" % (args.format, representation))
            print("Comment Length: %d chars" % len(body_value))
            print("-" * 60)
            print("COMMENT PREVIEW:")
            print(body_value[:500])
            print("-" * 60)
            print("Re-run with --yes to post this comment.")
            print("=" * 60)
        return

    try:
        result = add_comment(client, page_id, body_value, representation)
    except ConfluenceError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("CONFLUENCE COMMENT ADDED SUCCESSFULLY")
        print("=" * 60)
        print("Page ID:     %s" % result["page_id"])
        print("Comment ID:  %s" % result["comment_id"])
        print("-" * 60)
        print("URL: %s" % result["url"])
        print("=" * 60)


if __name__ == "__main__":
    main()
