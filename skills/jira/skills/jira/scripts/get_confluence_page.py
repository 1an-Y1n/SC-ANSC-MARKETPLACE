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
Confluence Page Reader Script

This script fetches Confluence page content by page ID or URL.
It can extract page title, body content, and metadata.

Usage:
    python get_confluence_page.py <page_id_or_url> [options]

Examples:
    python get_confluence_page.py 12345678
    python get_confluence_page.py "https://confluenceprod.sercomm.com/display/SPACE/Page+Title"
    python get_confluence_page.py 12345678 --json
    python get_confluence_page.py 12345678 --format text
"""

import argparse
import json
import re
import sys
import urllib.parse
from html import unescape
from typing import Any, Dict, Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config_loader import load_confluence_config, get_confluence_auth_header, validate_confluence_config

# Load configuration
CONFIG = load_confluence_config()


def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers based on config"""
    return get_confluence_auth_header(CONFIG)


def extract_page_id_from_url(url: str) -> Optional[str]:
    """Extract page ID from Confluence URL"""
    # Pattern 1: /pages/viewpage.action?pageId=12345678
    match = re.search(r'pageId=(\d+)', url)
    if match:
        return match.group(1)
    
    # Pattern 2: /display/SPACE/Page+Title - need to resolve via API
    match = re.search(r'/display/([^/]+)/(.+?)(?:\?|$)', url)
    if match:
        space_key = match.group(1)
        title = urllib.parse.unquote(match.group(2).replace('+', ' '))
        return resolve_page_by_title(space_key, title)
    
    # Pattern 3: /spaces/SPACE/pages/12345678/Page+Title
    match = re.search(r'/pages/(\d+)', url)
    if match:
        return match.group(1)
    
    # If it's just a number, assume it's a page ID
    if url.isdigit():
        return url
    
    return None


def resolve_page_by_title(space_key: str, title: str) -> Optional[str]:
    """Resolve page ID by space key and title"""
    base_url = CONFIG.get("confluence_url", "").rstrip('/')
    url = f"{base_url}/rest/api/content"
    
    params = {
        "spaceKey": space_key,
        "title": title,
        "expand": "version"
    }
    
    try:
        response = requests.get(
            url,
            headers=get_auth_headers(),
            params=params,
            verify=CONFIG.get("ssl_verify", False),
            timeout=CONFIG.get("timeout", 30)
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("results"):
            return data["results"][0]["id"]
    except Exception as e:
        print(f"Error resolving page: {e}", file=sys.stderr)
    
    return None


def html_to_text(html_content: str) -> str:
    """Convert HTML content to plain text"""
    # Remove script and style elements
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert common HTML elements
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?div[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '\n• ', text, flags=re.IGNORECASE)
    text = re.sub(r'<h[1-6][^>]*>', '\n\n## ', text, flags=re.IGNORECASE)
    text = re.sub(r'</h[1-6]>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<tr[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<td[^>]*>', ' | ', text, flags=re.IGNORECASE)
    text = re.sub(r'<th[^>]*>', ' | ', text, flags=re.IGNORECASE)
    
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Unescape HTML entities
    text = unescape(text)
    
    # Clean up whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()


def get_confluence_page(page_id: str, expand: str = "body.storage,version,space") -> Dict[str, Any]:
    """Fetch Confluence page by ID"""
    base_url = CONFIG.get("confluence_url", "").rstrip('/')
    url = f"{base_url}/rest/api/content/{page_id}"
    
    params = {"expand": expand}
    
    response = requests.get(
        url,
        headers=get_auth_headers(),
        params=params,
        verify=CONFIG.get("ssl_verify", False),
        timeout=CONFIG.get("timeout", 30)
    )
    response.raise_for_status()
    return response.json()


def get_page_children(page_id: str) -> list:
    """Get child pages of a Confluence page"""
    base_url = CONFIG.get("confluence_url", "").rstrip('/')
    url = f"{base_url}/rest/api/content/{page_id}/child/page"
    
    response = requests.get(
        url,
        headers=get_auth_headers(),
        verify=CONFIG.get("ssl_verify", False),
        timeout=CONFIG.get("timeout", 30)
    )
    response.raise_for_status()
    return response.json().get("results", [])


def get_page_attachments(page_id: str) -> list:
    """Get attachments of a Confluence page"""
    base_url = CONFIG.get("confluence_url", "").rstrip('/')
    url = f"{base_url}/rest/api/content/{page_id}/child/attachment"
    
    response = requests.get(
        url,
        headers=get_auth_headers(),
        verify=CONFIG.get("ssl_verify", False),
        timeout=CONFIG.get("timeout", 30)
    )
    response.raise_for_status()
    return response.json().get("results", [])


def generate_summary(body_content: str, title: str) -> str:
    """Generate a summary of the page content"""
    lines = body_content.strip().split('\n')
    
    # Extract headings
    headings = []
    for line in lines:
        line = line.strip()
        if line.startswith('## '):
            headings.append(line[3:].strip())
        elif line.startswith('# '):
            headings.append(line[2:].strip())
    
    # Count content metrics
    total_lines = len([l for l in lines if l.strip()])
    bullet_points = len([l for l in lines if l.strip().startswith('•')])
    
    # Build summary
    summary_parts = []
    summary_parts.append(f"Page Title: {title}")
    summary_parts.append(f"Total Sections: {len(headings)}")
    summary_parts.append(f"Content Lines: {total_lines}")
    summary_parts.append(f"Bullet Points: {bullet_points}")
    
    if headings:
        summary_parts.append(f"Main Sections:")
        for i, h in enumerate(headings[:10], 1):  # Limit to first 10 headings
            summary_parts.append(f"  {i}. {h}")
        if len(headings) > 10:
            summary_parts.append(f"  ... and {len(headings) - 10} more sections")
    
    return '\n'.join(summary_parts)


def format_page_output(page_data: Dict[str, Any], output_format: str = "text") -> str:
    """Format page data for output"""
    title = page_data.get("title", "Unknown")
    space = page_data.get("space", {}).get("key", "Unknown")
    version = page_data.get("version", {}).get("number", "Unknown")
    
    body_storage = page_data.get("body", {}).get("storage", {}).get("value", "")
    
    if output_format == "html":
        body_content = body_storage
    else:
        body_content = html_to_text(body_storage)
    
    base_url = CONFIG.get("confluence_url", "").rstrip('/')
    page_id = page_data.get("id", "")
    page_url = f"{base_url}/pages/viewpage.action?pageId={page_id}"
    
    # Generate summary
    summary = generate_summary(body_content, title)
    
    output = []
    output.append("=" * 80)
    output.append("CONFLUENCE PAGE")
    output.append("=" * 80)
    output.append(f"Title:    {title}")
    output.append(f"Space:    {space}")
    output.append(f"Page ID:  {page_id}")
    output.append(f"Version:  {version}")
    output.append(f"URL:      {page_url}")
    output.append("-" * 80)
    output.append("FULL CONTENT:")
    output.append("-" * 80)
    output.append(body_content)
    output.append("")
    output.append("=" * 80)
    output.append("SUMMARY:")
    output.append("=" * 80)
    output.append(summary)
    output.append("=" * 80)
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Confluence page content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 12345678                    # Get page by ID
  %(prog)s "https://confluence.../display/SPACE/Title"  # Get page by URL
  %(prog)s 12345678 --json             # Output as JSON
  %(prog)s 12345678 --format html      # Output HTML content
  %(prog)s 12345678 --children         # List child pages
  %(prog)s 12345678 --attachments      # List attachments
        """
    )
    
    parser.add_argument(
        "page",
        help="Confluence page ID or URL"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response"
    )
    parser.add_argument(
        "--format",
        choices=["text", "html"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--children",
        action="store_true",
        help="List child pages"
    )
    parser.add_argument(
        "--attachments",
        action="store_true",
        help="List attachments"
    )
    
    args = parser.parse_args()
    
    # Extract page ID
    page_id = extract_page_id_from_url(args.page)
    if not page_id:
        print(f"Error: Could not extract page ID from '{args.page}'", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.children:
            children = get_page_children(page_id)
            if args.json:
                print(json.dumps(children, indent=2))
            else:
                print(f"Child pages of {page_id}:")
                print("-" * 40)
                for child in children:
                    print(f"  [{child['id']}] {child['title']}")
                if not children:
                    print("  (No child pages)")
        
        elif args.attachments:
            attachments = get_page_attachments(page_id)
            if args.json:
                print(json.dumps(attachments, indent=2))
            else:
                print(f"Attachments of page {page_id}:")
                print("-" * 40)
                for att in attachments:
                    size = att.get("extensions", {}).get("fileSize", "Unknown")
                    print(f"  [{att['id']}] {att['title']} ({size} bytes)")
                if not attachments:
                    print("  (No attachments)")
        
        else:
            page_data = get_confluence_page(page_id)
            if args.json:
                print(json.dumps(page_data, indent=2))
            else:
                print(format_page_output(page_data, args.format))
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Page '{page_id}' not found", file=sys.stderr)
        elif e.response.status_code == 401:
            print("Error: Authentication failed. Check your token.", file=sys.stderr)
        elif e.response.status_code == 403:
            print("Error: Access denied. Check your permissions.", file=sys.stderr)
        else:
            print(f"Error: HTTP {e.response.status_code}: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
