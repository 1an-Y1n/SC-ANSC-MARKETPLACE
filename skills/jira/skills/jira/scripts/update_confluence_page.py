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

"""Update an existing Confluence page (preview by default; pass --yes to update).

Supports both full-page replacement (default) and appending to the end of the
existing page (--append). Automatically increments the Confluence page version.

Usage:
    python update_confluence_page.py <PAGE_ID_OR_URL> --body "<TEXT>" [--yes]
    python update_confluence_page.py <PAGE_ID_OR_URL> --body-file update.md --append [--yes]

Examples:
    python update_confluence_page.py 12345678 --body-file page.md
    python update_confluence_page.py 12345678 --body-file notes.md --append --message "Add Q4 notes" --yes
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
    load_text_source,
    prepare_body,
)

CONFLUENCE_CONFIG = load_confluence_config()


def merge_update_body(
    existing_storage: str,
    new_value: str,
    representation: str,
    append: bool,
    client: Optional[ConfluenceClient] = None,
) -> Tuple[str, str]:
    """Compute final ``(body_value, representation)`` for full replace or ``--append``.

    When ``--append`` is used, the existing page is stored as ``storage`` XHTML,
    so ``wiki`` input is converted to ``storage`` first via Confluence's
    contentbody conversion endpoint before concatenation.
    """
    if not append:
        return new_value, representation

    addition = new_value
    if representation == "wiki":
        if client is None:
            raise ValueError("client is required to convert --format wiki when --append is set")
        addition = client.convert_wiki_to_storage(new_value)

    base = (existing_storage or "").rstrip()
    if not base:
        return addition, "storage"
    return base + "\n" + addition, "storage"


def build_update_payload(
    page_id: str,
    space_key: str,
    title: str,
    body_value: str,
    representation: str,
    next_version: int,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the Confluence REST API PUT payload for updating a page."""
    version_obj: Dict[str, Any] = {"number": int(next_version)}
    if message:
        version_obj["message"] = message

    payload: Dict[str, Any] = {
        "id": str(page_id),
        "type": "page",
        "title": title.strip(),
        "body": {
            representation: {
                "value": body_value,
                "representation": representation,
            }
        },
        "version": version_obj,
    }
    if space_key:
        payload["space"] = {"key": space_key}
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update an existing Confluence page (preview by default; pass --yes to update)."
    )
    parser.add_argument("page", help="Confluence page ID or URL")
    parser.add_argument("--title", "-t", help="New page title (defaults to keeping current title)")
    parser.add_argument("--body", "-b", help="New or appended page body text")
    parser.add_argument("--body-file", help="Path to UTF-8 file containing page body")
    parser.add_argument(
        "--format",
        choices=VALID_FORMATS,
        default="markdown",
        help="Input body format: markdown (default), storage (XHTML), or wiki",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append new body to the end of the existing page instead of replacing it",
    )
    parser.add_argument("--message", "-m", help="Optional Confluence version comment")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually update the page; without --yes the script only prints a preview",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    valid, error_msg = validate_confluence_config(CONFLUENCE_CONFIG)
    if not valid:
        print("Error: %s" % error_msg, file=sys.stderr)
        sys.exit(1)

    try:
        raw_content = load_text_source(args.body, args.body_file, "--body", "--body-file")
        converted_value, representation = prepare_body(raw_content, args.format)
    except ValueError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    client = ConfluenceClient(CONFLUENCE_CONFIG)
    try:
        page_id = client.resolve_page_id(args.page)
        current = client.get_page(page_id, expand="body.storage,version,space")
        current_title = current.get("title") or ""
        current_space = ((current.get("space") or {}).get("key")) or ""
        current_version = int(((current.get("version") or {}).get("number")) or 1)
        existing_storage = (((current.get("body") or {}).get("storage") or {}).get("value")) or ""

        target_title = (args.title or current_title).strip()
        if not target_title:
            raise ValueError("Page title resolved to empty string")

        final_body, final_repr = merge_update_body(
            existing_storage,
            converted_value,
            representation,
            append=args.append,
            client=client,
        )
        next_version = current_version + 1
        payload = build_update_payload(
            page_id=page_id,
            space_key=current_space,
            title=target_title,
            body_value=final_body,
            representation=final_repr,
            next_version=next_version,
            message=args.message,
        )
    except (ValueError, ConfluenceError) as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    mode_label = "append" if args.append else "replace"
    if not args.yes:
        preview = {
            "status": "preview",
            "action": "update",
            "mode": mode_label,
            "page_id": page_id,
            "space": current_space,
            "current_title": current_title,
            "new_title": target_title,
            "current_version": current_version,
            "next_version": next_version,
            "message": args.message or "",
            "format": args.format,
            "representation": final_repr,
            "body_length": len(final_body),
            "body_preview": converted_value[:500],
            "url": client.page_url(page_id),
        }
        if args.json:
            print(json.dumps(preview, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("PREVIEW ONLY - PAGE NOT UPDATED")
            print("=" * 60)
            print("Page ID:        %s" % page_id)
            print("Space:          %s" % current_space)
            print("Mode:           %s" % mode_label)
            print("Title:          %s" % target_title)
            print("Version:        %d -> %d" % (current_version, next_version))
            if args.message:
                print("Version Note:   %s" % args.message)
            print("Input Format:   %s -> %s" % (args.format, final_repr))
            print("Final Length:   %d chars" % len(final_body))
            print("-" * 60)
            print("NEW CONTENT PREVIEW:")
            print(converted_value[:500])
            print("-" * 60)
            print("Re-run with --yes to update this Confluence page.")
            print("=" * 60)
        return

    try:
        updated = client.request("PUT", "/content/%s" % page_id, data=payload, retry_5xx=False)
    except ConfluenceError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    updated_version = ((updated.get("version") or {}).get("number")) or next_version
    result = {
        "status": "success",
        "page_id": page_id,
        "space": current_space,
        "title": updated.get("title", target_title),
        "mode": mode_label,
        "previous_version": current_version,
        "version": updated_version,
        "url": client.page_url(page_id),
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("CONFLUENCE PAGE UPDATED SUCCESSFULLY")
        print("=" * 60)
        print("Page ID:    %s" % result["page_id"])
        print("Space:      %s" % result["space"])
        print("Title:      %s" % result["title"])
        print("Mode:       %s" % result["mode"])
        print("Version:    %d -> %s" % (current_version, result["version"]))
        print("-" * 60)
        print("URL: %s" % result["url"])
        print("=" * 60)


if __name__ == "__main__":
    main()
