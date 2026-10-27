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
Link tasks to Epic using Jira REST API
This script links multiple tasks to an Epic using the correct custom field
"""

import requests
import json
import sys
from typing import List, Dict, Any

from config_loader import load_jira_config, get_jira_auth_header, validate_jira_config

# Load configuration
JIRA_CONFIG = load_jira_config()


def get_auth_header():
    """Get authentication header based on auth type"""
    return get_jira_auth_header(JIRA_CONFIG)

def link_task_to_epic(epic_key: str, task_key: str) -> bool:
    """Link a single task to an epic"""
    base_url = JIRA_CONFIG["jira_url"]
    headers = get_auth_header()
    headers['Content-Type'] = 'application/json'
    
    try:
        url = f"{base_url}/rest/api/2/issue/{task_key}"
        
        # Get current issue to check if it's already linked
        get_resp = requests.get(url, headers=headers, verify=JIRA_CONFIG["ssl_verify"])
        if get_resp.status_code != 200:
            print(f"❌ Failed to get task {task_key}: {get_resp.status_code}")
            return False
        
        task_data = get_resp.json()
        
        # Check if already linked to epic
        if task_data.get("fields", {}).get("customfield_10109"):
            current_epic = task_data["fields"]["customfield_10109"]
            if current_epic == epic_key:
                print(f"✅ Task {task_key} already linked to Epic {epic_key}")
                return True
        
        # Link task to epic using customfield_10109
        update_data = {
            "fields": {
                "customfield_10109": epic_key  # Epic Link field
            }
        }
        
        update_resp = requests.put(url, headers=headers, json=update_data, verify=JIRA_CONFIG["ssl_verify"])
        
        if update_resp.status_code in (200, 204):
            print(f"✅ Task {task_key} linked to Epic {epic_key}")
            return True
        else:
            print(f"❌ Failed to link task {task_key} to Epic {epic_key}: {update_resp.status_code}")
            print(f"Error: {update_resp.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception linking task {task_key} to Epic {epic_key}: {e}")
        return False

def link_tasks_to_epic(epic_key: str, task_keys: List[str]) -> bool:
    """Link multiple tasks to an epic"""
    success_count = 0
    total_count = len(task_keys)
    
    print(f"🔗 Linking {total_count} tasks to Epic {epic_key}...")
    
    for task_key in task_keys:
        print(f"📋 Linking task {task_key} to Epic {epic_key}")
        
        if link_task_to_epic(epic_key, task_key):
            success_count += 1
    
    print(f"📊 Summary: {success_count}/{total_count} tasks linked to Epic")
    
    if success_count == total_count:
        print("🎉 All tasks successfully linked to Epic!")
        return True
    else:
        print("⚠️ Some tasks failed to link. Please check the errors above.")
        return False

def verify_epic_links(epic_key: str, task_keys: List[str]) -> bool:
    """Verify that tasks are linked to the epic"""
    base_url = JIRA_CONFIG["jira_url"]
    headers = get_auth_header()
    
    try:
        url = f"{base_url}/rest/api/2/issue/{epic_key}"
        resp = requests.get(url, headers=headers, verify=JIRA_CONFIG["ssl_verify"])
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Epic {epic_key} found: {data['fields']['summary']}")
            return True
        else:
            print(f"❌ Failed to get Epic {epic_key}: {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Exception verifying Epic {epic_key}: {e}")
        return False

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Link tasks to Epic")
    parser.add_argument("--epic", required=True, help="Epic key (e.g., EBP00-161)")
    parser.add_argument("--tasks", required=True, help="Comma-separated list of task keys (e.g., EBP00-162,EBP00-163)")
    parser.add_argument("--verify", action="store_true", help="Verify Epic exists before linking")
    
    args = parser.parse_args()
    
    # Parse task keys
    task_keys = [task.strip() for task in args.tasks.split(",")]
    
    print(f"🎯 Epic Link Operation")
    print(f"Epic: {args.epic}")
    print(f"Tasks: {len(task_keys)} tasks")
    print(f"Task Keys: {', '.join(task_keys)}")
    print()
    
    # Verify Epic exists if requested
    if args.verify:
        print("🔍 Verifying Epic...")
        if not verify_epic_links(args.epic, task_keys):
            print("❌ Epic verification failed. Aborting.")
            sys.exit(1)
        print()
    
    # Link all tasks to epic
    if link_tasks_to_epic(args.epic, task_keys):
        print("✅ Epic linking completed successfully!")
    else:
        print("❌ Epic linking failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
