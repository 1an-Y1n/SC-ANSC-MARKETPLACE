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
Jira Ticket Query Script

Usage:
    python query_jira_tickets.py --project <PROJECT_KEY> [OPTIONS]

Options:
    --project, -p         Project key (required)
    --assignee, -a        Assignee username
    --reporter, -r        Reporter username
    --status, -s          Issue status
    --type, -t            Issue type
    --priority, -P        Priority level
    --details, -d         Show detailed information
    --group-by, -g        Group by field (status, type, priority, assignee, reporter)
    --max-results, -m     Maximum results (default: 100)
    --json                Output in JSON format

Examples:
    # Get total ticket count for a project
    python query_jira_tickets.py --project DZ300

    # Get tickets assigned to a user
    python query_jira_tickets.py --project DZ300 --assignee "Xiaoan Chen"

    # Get tickets reported by a user
    python query_jira_tickets.py --project DZ300 --reporter "A004401"

    # Get open tickets
    python query_jira_tickets.py --project DZ300 --status Open

    # Get detailed information
    python query_jira_tickets.py --project DZ300 --assignee "Xiaoan Chen" --details

    # Group by status
    python query_jira_tickets.py --project DZ300 --group-by status
"""

import json
import os
import requests
import sys
import argparse
from datetime import datetime
from collections import defaultdict

# Load config using new config_loader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_jira_config, get_jira_auth_header, validate_jira_config

def load_config():
    """Load Jira configuration using config_loader"""
    config = load_jira_config()
    valid, error_msg = validate_jira_config(config)
    if not valid:
        raise FileNotFoundError(error_msg)
    return config

def build_jql(args):
    """Build JQL query from arguments

    --jql bypasses the structured filters entirely. Mixing the two would make
    it ambiguous which one wins, so they are rejected together in main().
    """
    if args.jql:
        return args.jql.strip()

    conditions = []

    if args.project:
        conditions.append(f'project = {args.project}')

    if args.assignee:
        conditions.append(f'assignee = "{args.assignee}"')

    if args.reporter:
        conditions.append(f'reporter = "{args.reporter}"')

    if args.status:
        conditions.append(f'status = "{args.status}"')

    if args.type:
        conditions.append(f'issuetype = "{args.type}"')

    if args.priority:
        conditions.append(f'priority = "{args.priority}"')

    return ' AND '.join(conditions) if conditions else ''

def validate_query_args(args):
    """Return an error message when --jql is mixed with the structured filters."""
    structured = any([args.project, args.assignee, args.reporter,
                      args.status, args.type, args.priority])
    if args.jql and structured:
        return ("--jql cannot be combined with --project/--assignee/--reporter/"
                "--status/--type/--priority. Use one style or the other.")
    return ''


def search_issues(config, jql, fields=None, max_results=100):
    """Search Jira issues"""
    url = f"{config['jira_url']}/rest/api/2/search"
    headers = get_jira_auth_header(config)
    headers['Content-Type'] = 'application/json'
    params = {
        'jql': jql,
        'fields': fields or ['key', 'summary', 'status', 'priority'],
        'maxResults': max_results
    }
    
    response = requests.get(url, headers=headers, params=params, 
                          verify=config.get('ssl_verify', False))
    
    if response.status_code != 200:
        raise Exception(f"Jira API error: {response.status_code} - {response.text}")
    
    return response.json()

def format_date(date_str):
    """Format date string"""
    if not date_str:
        return 'N/A'
    try:
        return date_str[:10]
    except:
        return date_str

def print_summary(data, args):
    """Print summary of results"""
    total = data.get('total', 0)
    print(f"Total tickets: {total}")
    
    if args.json:
        print(json.dumps(data, indent=2))
        return

def print_details(issues, config):
    """Print detailed information for issues"""
    for i, issue in enumerate(issues, 1):
        key = issue.get('key')
        fields = issue.get('fields', {})
        
        summary = fields.get('summary', 'N/A')
        status = fields.get('status', {}).get('name', 'N/A')
        priority = fields.get('priority', {}).get('name', 'N/A')
        issuetype = fields.get('issuetype', {}).get('name', 'N/A')
        created = format_date(fields.get('created'))
        updated = format_date(fields.get('updated'))
        
        components = [c.get('name', '') for c in fields.get('components', [])]
        components_str = ', '.join(components) if components else 'N/A'
        
        print(f"{i}. {key}")
        print(f"   Summary: {summary}")
        print(f"   Type: {issuetype}")
        print(f"   Status: {status}")
        print(f"   Priority: {priority}")
        print(f"   Components: {components_str}")
        print(f"   Created: {created}")
        print(f"   Updated: {updated}")
        print(f"   URL: {config['jira_url']}/browse/{key}")
        print()

def print_grouped(issues, group_by):
    """Print issues grouped by specified field"""
    grouped = defaultdict(list)

    for issue in issues:
        fields = issue.get('fields', {})

        if group_by == 'status':
            key = fields.get('status', {}).get('name', 'Unknown')
        elif group_by == 'type':
            key = fields.get('issuetype', {}).get('name', 'Unknown')
        elif group_by == 'priority':
            key = fields.get('priority', {}).get('name', 'Unknown')
        elif group_by == 'assignee':
            key = fields.get('assignee', {}).get('displayName', 'Unassigned')
        elif group_by == 'reporter':
            key = fields.get('reporter', {}).get('displayName', 'Unknown')
        else:
            key = 'Unknown'

        grouped[key].append(issue)

    print(f"\nGrouped by {group_by}:")
    for key, items in sorted(grouped.items()):
        print(f"  {key}: {len(items)}")

def main():
    parser = argparse.ArgumentParser(description='Query Jira tickets')
    parser.add_argument('--project', '-p', help='Project key')
    parser.add_argument('--jql', help='Raw JQL query (mutually exclusive with the structured filters)')
    parser.add_argument('--assignee', '-a', help='Assignee username')
    parser.add_argument('--reporter', '-r', help='Reporter username')
    parser.add_argument('--status', '-s', help='Issue status')
    parser.add_argument('--type', '-t', help='Issue type')
    parser.add_argument('--priority', '-P', help='Priority level')
    parser.add_argument('--details', '-d', action='store_true', help='Show detailed information')
    parser.add_argument('--group-by', '-g', choices=['status', 'type', 'priority', 'assignee', 'reporter'],
                       help='Group results by field')
    parser.add_argument('--max-results', '-m', type=int, default=100,
                       help='Maximum results (default: 100)')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    args = parser.parse_args()
    
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Build JQL query
    arg_error = validate_query_args(args)
    if arg_error:
        print(f"Error: {arg_error}")
        sys.exit(1)

    jql = build_jql(args)
    if not jql:
        print("Error: At least --project or --jql must be specified")
        sys.exit(1)
    
    # Determine fields to fetch
    fields = ['key', 'summary', 'status', 'priority']
    if args.details:
        fields.extend(['issuetype', 'created', 'updated', 'components'])
    
    # Search issues
    try:
        data = search_issues(config, jql, fields, args.max_results)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Print results
    print_summary(data, args)
    
    if args.json:
        return
    
    issues = data.get('issues', [])
    
    if args.group_by:
        print_grouped(issues, args.group_by)
    
    if args.details and issues:
        print()
        print("Ticket details:")
        print_details(issues, config)
    elif issues and not args.group_by:
        print("\nFirst 10 tickets:")
        for i, issue in enumerate(issues[:10], 1):
            key = issue.get('key')
            fields = issue.get('fields', {})
            summary = fields.get('summary', 'N/A')
            status = fields.get('status', {}).get('name', 'N/A')
            print(f"{i}. {key} - {summary} ({status})")
        
        if len(issues) > 10:
            print(f"\n... and {len(issues) - 10} more tickets")

if __name__ == '__main__':
    main()
