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
Jira Ticket Watcher Update Script

Update "People to be informed" (watchers) for multiple Jira tickets

Usage:
    python update_jira_watcher.py --project <PROJECT_KEY> --reporter <REPORTER> --add-user <USER_ID>

Options:
    --project, -p         Project key (required)
    --reporter, -r        Reporter username (required)
    --add-user, -a        User ID to add to watchers (required)
    --dry-run, -d         Dry run mode (show changes without applying)
"""

import json
import os
import requests
import sys
import argparse
from config_loader import load_jira_config, get_jira_auth_header, validate_jira_config

def load_config():
    """Load Jira configuration"""
    config = load_jira_config()
    valid, error_msg = validate_jira_config(config)
    if not valid:
        raise FileNotFoundError(error_msg)
    return config

def get_tickets_by_reporter(config, project, reporter, max_results=100):
    """Get tickets by reporter"""
    url = f"{config['jira_url']}/rest/api/2/search"
    headers = get_jira_auth_header(config)
    headers['Content-Type'] = 'application/json'
    params = {
        'jql': f'project = {project} AND reporter = "{reporter}"',
        'fields': ['key', 'summary'],
        'maxResults': max_results
    }
    
    response = requests.get(url, headers=headers, params=params, 
                          verify=config.get('ssl_verify', False))
    
    if response.status_code != 200:
        raise Exception(f"Jira API error: {response.status_code} - {response.text}")
    
    return response.json()

def get_watchers(config, issue_key):
    """Get current watchers for an issue"""
    url = f"{config['jira_url']}/rest/api/2/issue/{issue_key}/watchers"
    headers = get_jira_auth_header(config)
    
    response = requests.get(url, headers=headers, verify=config.get('ssl_verify', False))
    
    if response.status_code != 200:
        raise Exception(f"Jira API error: {response.status_code} - {response.text}")
    
    return response.json()

def add_watcher(config, issue_key, user_id):
    """Add a user to watchers"""
    url = f"{config['jira_url']}/rest/api/2/issue/{issue_key}/watchers"
    headers = get_jira_auth_header(config)
    headers['Content-Type'] = 'application/json'
    
    response = requests.post(url, headers=headers, json=user_id, 
                            verify=config.get('ssl_verify', False))
    
    if response.status_code == 204:
        return True
    elif response.status_code == 404:
        # User not found
        return False
    else:
        raise Exception(f"Jira API error: {response.status_code} - {response.text}")

def main():
    parser = argparse.ArgumentParser(description='Update Jira ticket watchers')
    parser.add_argument('--project', '-p', required=True, help='Project key')
    parser.add_argument('--reporter', '-r', required=True, help='Reporter username')
    parser.add_argument('--add-user', '-a', required=True, help='User ID to add to watchers')
    parser.add_argument('--dry-run', '-d', action='store_true', help='Dry run mode')
    
    args = parser.parse_args()
    
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Get tickets
    print(f"Fetching tickets for project {args.project} with reporter {args.reporter}...")
    try:
        data = get_tickets_by_reporter(config, args.project, args.reporter, max_results=100)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    total = data.get('total', 0)
    issues = data.get('issues', [])
    
    print(f"Found {total} tickets")
    
    if total == 0:
        print("No tickets to update")
        return
    
    # Process each ticket
    success_count = 0
    user_not_found_count = 0
    error_count = 0
    
    for i, issue in enumerate(issues, 1):
        key = issue.get('key')
        summary = issue.get('fields', {}).get('summary', 'N/A')
        
        print(f"\n[{i}/{total}] Processing {key}: {summary}")
        
        if args.dry_run:
            print(f"  [DRY RUN] Would add user {args.add_user} to watchers")
            success_count += 1
            continue
        
        try:
            result = add_watcher(config, key, args.add_user)
            if result:
                print(f"  ✓ Successfully added user {args.add_user} to watchers")
                success_count += 1
            else:
                print(f"  ✗ User {args.add_user} not found")
                user_not_found_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            error_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("Summary:")
    print(f"  Total tickets: {total}")
    print(f"  Successfully updated: {success_count}")
    print(f"  User not found: {user_not_found_count}")
    print(f"  Errors: {error_count}")
    print("="*60)

if __name__ == '__main__':
    main()
