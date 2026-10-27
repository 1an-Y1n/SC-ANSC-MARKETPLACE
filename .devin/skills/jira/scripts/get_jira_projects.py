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
Jira Projects Fetcher - Get project names and keys

Usage:
    python get_jira_projects.py [--search <KEYWORD>] [--json]
    
Example:
    python get_jira_projects.py
    python get_jira_projects.py --search DUZ
    python get_jira_projects.py --json
"""

import sys
import json
import argparse
import requests
import warnings
from typing import Dict, Any, List

# Disable SSL warnings for internal servers
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

from config_loader import load_jira_config, get_jira_auth_header, validate_jira_config

# Load configuration
JIRA_CONFIG = load_jira_config()


def get_auth_header() -> Dict[str, str]:
    """Get authentication header based on auth type"""
    return get_jira_auth_header(JIRA_CONFIG)


def get_all_projects() -> Dict[str, Any]:
    """
    Get all Jira projects accessible to the user.
    
    Returns:
        Dictionary containing list of projects with key, name, and description
    """
    base_url = JIRA_CONFIG["jira_url"]
    headers = get_auth_header()
    headers['Content-Type'] = 'application/json'
    
    try:
        url = f"{base_url}/rest/api/2/project"
        resp = requests.get(
            url,
            headers=headers,
            verify=JIRA_CONFIG["ssl_verify"],
            timeout=JIRA_CONFIG["timeout"]
        )
        
        if resp.status_code == 200:
            projects = resp.json()
            return {
                "status": "success",
                "data": {
                    "total": len(projects),
                    "projects": [
                        {
                            "key": p.get("key", ""),
                            "name": p.get("name", ""),
                            "description": p.get("description", ""),
                            "lead": p.get("lead", {}).get("displayName", "") if p.get("lead") else "",
                            "projectTypeKey": p.get("projectTypeKey", "")
                        }
                        for p in projects
                    ]
                }
            }
        else:
            return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_project_details(project_key: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific project.
    
    Args:
        project_key: Jira project key (e.g., 'DUZ01')
        
    Returns:
        Dictionary containing project details
    """
    base_url = JIRA_CONFIG["jira_url"]
    headers = get_auth_header()
    headers['Content-Type'] = 'application/json'
    
    try:
        url = f"{base_url}/rest/api/2/project/{project_key}"
        resp = requests.get(
            url,
            headers=headers,
            verify=JIRA_CONFIG["ssl_verify"],
            timeout=JIRA_CONFIG["timeout"]
        )
        
        if resp.status_code == 200:
            p = resp.json()
            return {
                "status": "success",
                "data": {
                    "key": p.get("key", ""),
                    "name": p.get("name", ""),
                    "description": p.get("description", ""),
                    "lead": p.get("lead", {}).get("displayName", "") if p.get("lead") else "",
                    "projectTypeKey": p.get("projectTypeKey", ""),
                    "issueTypes": [
                        {"id": it.get("id"), "name": it.get("name")}
                        for it in p.get("issueTypes", [])
                    ],
                    "components": [
                        {"id": c.get("id"), "name": c.get("name")}
                        for c in p.get("components", [])
                    ]
                }
            }
        else:
            return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_project_versions(project_key: str) -> Dict[str, Any]:
    """
    Get the version list of a project (for Fix Version/s and Affects Version/s).

    Args:
        project_key: Jira project key (e.g., 'DUZ01')

    Returns:
        Dictionary containing the versions with id, name, and release state
    """
    base_url = JIRA_CONFIG["jira_url"]
    headers = get_auth_header()
    headers['Content-Type'] = 'application/json'

    try:
        url = f"{base_url}/rest/api/2/project/{project_key}/versions"
        resp = requests.get(
            url,
            headers=headers,
            verify=JIRA_CONFIG["ssl_verify"],
            timeout=JIRA_CONFIG["timeout"]
        )

        if resp.status_code == 200:
            versions = resp.json()
            return {
                "status": "success",
                "data": {
                    "project": project_key,
                    "total": len(versions),
                    "versions": [
                        {
                            "id": str(v.get("id", "")),
                            "name": v.get("name", ""),
                            "released": bool(v.get("released", False)),
                            "archived": bool(v.get("archived", False)),
                            "releaseDate": v.get("releaseDate", ""),
                        }
                        for v in versions
                    ]
                }
            }
        else:
            return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def search_projects(keyword: str, projects: List[Dict]) -> List[Dict]:
    """Filter projects by keyword in key or name"""
    keyword_lower = keyword.lower()
    return [
        p for p in projects
        if keyword_lower in p.get("key", "").lower() or 
           keyword_lower in p.get("name", "").lower()
    ]


def format_output(data: Dict[str, Any], search_keyword: str = None) -> str:
    """Format the output for display"""
    if data.get("status") == "error":
        return f"Error: {data.get('error', 'Unknown error')}"
    
    projects = data.get("data", {}).get("projects", [])
    
    if search_keyword:
        projects = search_projects(search_keyword, projects)
    
    output = []
    output.append("=" * 70)
    output.append(f"JIRA PROJECTS ({len(projects)} found)")
    output.append("=" * 70)
    output.append("")
    output.append(f"{'KEY':<15} {'NAME':<40} {'LEAD':<15}")
    output.append("-" * 70)
    
    for p in projects:
        key = p.get("key", "")[:15]
        name = p.get("name", "")[:40]
        lead = p.get("lead", "")[:15]
        output.append(f"{key:<15} {name:<40} {lead:<15}")
    
    output.append("-" * 70)
    output.append(f"Total: {len(projects)} projects")
    
    return "\n".join(output)


def format_project_detail(data: Dict[str, Any]) -> str:
    """Format project detail output"""
    if data.get("status") == "error":
        return f"Error: {data.get('error', 'Unknown error')}"
    
    p = data.get("data", {})
    
    output = []
    output.append("=" * 60)
    output.append(f"PROJECT: {p.get('key', 'N/A')}")
    output.append("=" * 60)
    output.append(f"Name:        {p.get('name', 'N/A')}")
    output.append(f"Lead:        {p.get('lead', 'N/A')}")
    output.append(f"Type:        {p.get('projectTypeKey', 'N/A')}")
    output.append(f"Description: {p.get('description', 'N/A') or '(No description)'}")
    output.append("")
    output.append("-" * 60)
    output.append("ISSUE TYPES:")
    output.append("-" * 60)
    for it in p.get("issueTypes", []):
        output.append(f"  - {it.get('name', '')} (ID: {it.get('id', '')})")
    
    if p.get("components"):
        output.append("")
        output.append("-" * 60)
        output.append("COMPONENTS:")
        output.append("-" * 60)
        for c in p.get("components", []):
            output.append(f"  - {c.get('name', '')} (ID: {c.get('id', '')})")
    
    return "\n".join(output)


def format_versions(data: Dict[str, Any]) -> str:
    """Format the project version list for display"""
    if data.get("status") == "error":
        return f"Error: {data.get('error', 'Unknown error')}"

    payload = data.get("data", {})
    versions = payload.get("versions", [])

    output = []
    output.append("=" * 78)
    output.append(f"PROJECT VERSIONS: {payload.get('project', 'N/A')} ({len(versions)} found)")
    output.append("=" * 78)
    output.append("")
    output.append(f"{'ID':<10} {'NAME':<34} {'RELEASED':<10} {'ARCHIVED':<10} {'DATE':<12}")
    output.append("-" * 78)
    for v in versions:
        output.append(
            f"{v.get('id', ''):<10} {v.get('name', '')[:34]:<34} "
            f"{str(v.get('released', False)):<10} {str(v.get('archived', False)):<10} "
            f"{v.get('releaseDate', '') or '-':<12}"
        )
    output.append("-" * 78)
    output.append(f"Total: {len(versions)} versions")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Get Jira project names and keys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all projects
  python get_jira_projects.py

  # Search projects by keyword
  python get_jira_projects.py --search DUZ

  # Get details of a specific project
  python get_jira_projects.py --project DUZ01

  # List versions of a project (for Fix Version/s)
  python get_jira_projects.py --project DUZ01 --versions

  # Output in JSON format
  python get_jira_projects.py --json
        """
    )
    
    parser.add_argument("--search", "-s", help="Search keyword for project key or name")
    parser.add_argument("--project", "-p", help="Get details of a specific project by key")
    parser.add_argument("--versions", action="store_true",
                        help="List the versions of --project (for Fix/Affects Version)")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    if args.versions:
        if not args.project:
            parser.error("--versions requires --project <KEY>")
        print(f"Fetching versions for project: {args.project}...")
        print()
        result = get_project_versions(args.project.upper())

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(format_versions(result))
        return

    if args.project:
        # Get specific project details
        print(f"Fetching project details for: {args.project}...")
        print()
        result = get_project_details(args.project.upper())
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(format_project_detail(result))
    else:
        # List all projects
        print("Fetching Jira projects...")
        print()
        result = get_all_projects()
        
        if args.json:
            if args.search and result.get("status") == "success":
                result["data"]["projects"] = search_projects(
                    args.search, result["data"]["projects"]
                )
                result["data"]["total"] = len(result["data"]["projects"])
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(format_output(result, args.search))


if __name__ == "__main__":
    main()
