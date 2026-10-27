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

"""Create a new Confluence page (preview by default; pass --yes to create).

Usage:
    python create_confluence_page.py --space <SPACE_KEY> --title "<TITLE>" --body "<TEXT>" [--yes]
    python create_confluence_page.py --parent <PAGE_ID_OR_URL> --title "<TITLE>" --body-file page.md [--yes]

Examples:
    python create_confluence_page.py --space ANSC --title "Design Notes" --body-file notes.md
    python create_confluence_page.py --space ANSC --parent 123456 --title "Subpage" --body "# Hello" --yes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from typing import Any, Dict, Optional, Tuple

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


def build_create_payload(
    space_key: str,
    title: str,
    body_value: str,
    representation: str,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the Confluence REST API POST payload for creating a page."""
    if not space_key or not space_key.strip():
        raise ValueError("space_key must not be empty")
    if not title or not title.strip():
        raise ValueError("title must not be empty")

    payload: Dict[str, Any] = {
        "type": "page",
        "title": title.strip(),
        "space": {"key": space_key.strip()},
        "body": {
            representation: {
                "value": body_value,
                "representation": representation,
            }
        },
    }
    if parent_id:
        payload["ancestors"] = [{"id": str(parent_id)}]
    return payload


def create_page(
    client: ConfluenceClient,
    space_key: str,
    title: str,
    body_value: str,
    representation: str,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Send POST /rest/api/content (retry_5xx=False to prevent duplicate pages)."""
    payload = build_create_payload(space_key, title, body_value, representation, parent_id)
    created = client.request("POST", "/content", data=payload, retry_5xx=False)
    page_id = str(created.get("id", ""))
    version = (created.get("version") or {}).get("number", 1)
    return {
        "status": "success",
        "page_id": page_id,
        "title": created.get("title", title.strip()),
        "space": ((created.get("space") or {}).get("key")) or space_key.strip(),
        "parent_id": parent_id,
        "version": version,
        "url": client.page_url(page_id) if page_id else "",
    }


def _resolve_parent_and_space(
    client: ConfluenceClient,
    raw_space: Optional[str],
    raw_parent: Optional[str],
    allow_network: bool,
) -> Tuple[str, Optional[str]]:
    """Resolve ``(space_key, parent_id)`` from CLI arguments."""
    space_key = (raw_space or "").strip()
    parent_id: Optional[str] = None

    if raw_parent:
        static_parent = extract_static_page_id(raw_parent)
        if static_parent and space_key and not allow_network:
            parent_id = static_parent
        else:
            parent_id = client.resolve_page_id(raw_parent)
            if not space_key:
                parent_data = client.get_page(parent_id, expand="space")
                space_key = ((parent_data.get("space") or {}).get("key") or "").strip()

    if not space_key:
        raise ValueError("Pass --space <SPACE_KEY> (or --parent <PAGE_ID_OR_URL> to infer space)")
    return space_key, parent_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new Confluence page (preview by default; pass --yes to create)."
    )
    parser.add_argument("--space", "-s", help="Confluence space key (inferred if --parent is given)")
    parser.add_argument("--parent", "-p", help="Optional parent page ID or URL")
    parser.add_argument("--title", "-t", required=True, help="Page title")
    parser.add_argument("--body", "-b", help="Page body text")
    parser.add_argument("--body-file", help="Path to UTF-8 file containing page body")
    parser.add_argument(
        "--format",
        choices=VALID_FORMATS,
        default="markdown",
        help="Input body format: markdown (default), storage (XHTML), or wiki",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually create the page; without --yes the script only prints a preview",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    valid, error_msg = validate_confluence_config(CONFLUENCE_CONFIG)
    if not valid:
        print("Error: %s" % error_msg, file=sys.stderr)
        sys.exit(1)

    try:
        raw_content = load_text_source(args.body, args.body_file, "--body", "--body-file")
        body_value, representation = prepare_body(raw_content, args.format)
    except ValueError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    client = ConfluenceClient(CONFLUENCE_CONFIG)
    try:
        space_key, parent_id = _resolve_parent_and_space(
            client, args.space, args.parent, allow_network=args.yes
        )
        payload = build_create_payload(
            space_key, args.title, body_value, representation, parent_id
        )
    except (ValueError, ConfluenceError) as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    if not args.yes:
        preview = {
            "status": "preview",
            "action": "create",
            "space": space_key,
            "parent_id": parent_id,
            "title": payload["title"],
            "format": args.format,
            "representation": representation,
            "body_length": len(body_value),
            "body_preview": body_value[:500],
        }
        if args.json:
            print(json.dumps(preview, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("PREVIEW ONLY - PAGE NOT CREATED")
            print("=" * 60)
            print("Space:          %s" % space_key)
            print("Parent ID:      %s" % (parent_id or "(space root)"))
            print("Title:          %s" % payload["title"])
            print("Input Format:   %s -> %s" % (args.format, representation))
            print("Body Length:    %d chars" % len(body_value))
            print("-" * 60)
            print("BODY PREVIEW:")
            print(body_value[:500])
            print("-" * 60)
            print("Re-run with --yes to create this Confluence page.")
            print("=" * 60)
        return

    try:
        result = create_page(client, space_key, args.title, body_value, representation, parent_id)
    except ConfluenceError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("CONFLUENCE PAGE CREATED SUCCESSFULLY")
        print("=" * 60)
        print("Page ID:    %s" % result["page_id"])
        print("Space:      %s" % result["space"])
        print("Parent ID:  %s" % (result["parent_id"] or "(space root)"))
        print("Title:      %s" % result["title"])
        print("Version:    %s" % result["version"])
        print("-" * 60)
        print("URL: %s" % result["url"])
        print("=" * 60)


if __name__ == "__main__":
    main()
