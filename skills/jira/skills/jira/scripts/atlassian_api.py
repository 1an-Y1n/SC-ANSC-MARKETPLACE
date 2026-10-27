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
MCP Atlassian Bridge - REST API-based MCP service for Jira/Confluence

Provides OWL-compatible interface to Atlassian services.
Reads configuration from config.ini [Atlassian] section.
Only provides service when valid connection is established.

Design Principles:
- Reads config from config.ini (not separate config file)
- Connection validation on startup
- Service disabled if connection fails
- OWL-compatible response format (status/data/error)
- No business logic - pure API wrapper

Usage:
    # Direct call mode (OWL)
    from mcp_servers.mcp_atlassian_bridge import jira_get_issue
    result = jira_get_issue(issue_key="PROJ-123")
    
    # Check availability
    from mcp_servers.mcp_atlassian_bridge import ATLASSIAN_TOOLS
    print(ATLASSIAN_TOOLS)  # Shows available tools based on connection status
"""

import os
import sys
import json
import requests
import base64
import warnings
from typing import Dict, Any, Optional, List, Tuple
from functools import lru_cache

# Disable SSL warnings for internal servers with non-standard certificates
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utility import scm_log
except ImportError:
    def scm_log(msg, level='info'):
        print(f"[{level.upper()}] {msg}", file=sys.stderr)

try:
    from config import ConfigReader
    _config_reader = None
    def _get_config():
        global _config_reader
        if _config_reader is None:
            _config_reader = ConfigReader()
        return _config_reader
except ImportError:
    import configparser
    _config_reader = None
    def _get_config():
        global _config_reader
        if _config_reader is None:
            config_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.ini'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'config.ini'),
            ]
            _config_reader = configparser.ConfigParser()
            for path in config_paths:
                if os.path.exists(path):
                    _config_reader.read(path)
                    break
        return _config_reader


def _default_download_path():
    """按用户隔离的默认下载目录 —— 不写死 /tmp/atlassian 这类共享路径。

    共享路径会让同机多人互相覆盖下载结果，并把下载下来的 Jira / Confluence
    附件暴露给其他用户；/tmp 世界可写，还给了预创建目录 / 符号链接可乘之机。
    显式配置的 Atlassian.download_path 优先级更高（见 _load_config_from_ini）。
    """
    cache_root = os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache')
    return os.path.join(cache_root, 'ai-toolbox', 'atlassian')


class AtlassianBridge:
    """
    Bridge between OWL and Atlassian REST APIs.
    
    Can read configuration from config.ini [Atlassian] section (legacy) or
    accept profile-specific credentials (new in v2.6).
    Validates connections on initialization.
    """
    
    _instance = None
    
    def __new__(cls, jira_config=None, confluence_config=None, connection_config=None):
        # Always create new instance if profile credentials provided (v2.6+)
        if jira_config is not None or confluence_config is not None:
            instance = super().__new__(cls)
            instance._initialized = False
            return instance
        
        # Singleton behavior for legacy config.ini usage
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, jira_config=None, confluence_config=None, connection_config=None):
        if self._initialized:
            return
        self._initialized = True
        self._jira_available = False
        self._confluence_available = False
        
        # Load from profile credentials if provided (v2.6+), otherwise fallback to config.ini
        if jira_config is not None or confluence_config is not None:
            self._load_config_from_profile(jira_config, confluence_config, connection_config)
        else:
            self._load_config_from_ini()
        
        self._validate_connections()
    
    def _load_config_from_profile(self, jira_config, confluence_config, connection_config):
        """Load configuration from profile JSON (new in v2.6)"""
        config = _get_config()

        # Jira defaults from config.ini
        self.jira_url = config.get('Atlassian', 'jira_url', fallback='').strip()
        self.jira_user = config.get('Atlassian', 'jira_user', fallback='').strip()
        self.jira_token = config.get('Atlassian', 'jira_token', fallback='').strip()
        self.jira_auth_type = config.get('Atlassian', 'jira_auth_type', fallback='bearer').strip().lower()

        # Confluence defaults from config.ini
        self.confluence_url = config.get('Atlassian', 'confluence_url', fallback='').strip()
        self.confluence_user = config.get('Atlassian', 'confluence_user', fallback='').strip()
        self.confluence_token = config.get('Atlassian', 'confluence_token', fallback='').strip()
        self.confluence_auth_type = config.get('Atlassian', 'confluence_auth_type', fallback='bearer').strip().lower()

        # Connection defaults from config.ini
        ssl_verify_str = config.get('Atlassian', 'ssl_verify', fallback='true').strip().lower()
        self.ssl_verify = ssl_verify_str in ('true', '1', 'yes', 'on')
        try:
            self.timeout = int(config.get('Atlassian', 'timeout', fallback='30'))
        except ValueError:
            self.timeout = 30

        def _nonempty(value):
            if value is None:
                return None
            s = str(value).strip()
            return s if s else None

        # Jira overrides from profile
        if jira_config:
            v = _nonempty(jira_config.get('jira_url'))
            if v is not None:
                self.jira_url = v
            v = _nonempty(jira_config.get('jira_user'))
            if v is not None:
                self.jira_user = v
            v = _nonempty(jira_config.get('jira_token'))
            if v is not None:
                self.jira_token = v
            v = _nonempty(jira_config.get('jira_auth_type'))
            if v is not None:
                self.jira_auth_type = v.lower()

        # Confluence overrides from profile
        if confluence_config:
            v = _nonempty(confluence_config.get('confluence_url'))
            if v is not None:
                self.confluence_url = v
            v = _nonempty(confluence_config.get('confluence_user'))
            if v is not None:
                self.confluence_user = v
            v = _nonempty(confluence_config.get('confluence_token'))
            if v is not None:
                self.confluence_token = v
            v = _nonempty(confluence_config.get('confluence_auth_type'))
            if v is not None:
                self.confluence_auth_type = v.lower()

        # Connection overrides from profile
        if connection_config:
            if 'ssl_verify' in connection_config:
                ssl_verify_val = connection_config.get('ssl_verify', self.ssl_verify)
                if isinstance(ssl_verify_val, bool):
                    self.ssl_verify = ssl_verify_val
                else:
                    ssl_verify_str = str(ssl_verify_val).strip().lower()
                    self.ssl_verify = ssl_verify_str in ('true', '1', 'yes', 'on')
            if 'timeout' in connection_config:
                try:
                    self.timeout = int(connection_config.get('timeout', self.timeout))
                except (TypeError, ValueError):
                    pass
        
        # Download settings - hardcoded defaults (no longer in config.ini)
        self.download_path = _default_download_path()
        self.max_single_file_size = 2097152  # 2MB
        self.max_total_download_size = 10485760  # 10MB
    
    def _load_config_from_ini(self):
        """Load configuration from config.ini [Atlassian] section"""
        config = _get_config()
        
        # Jira settings
        self.jira_url = config.get('Atlassian', 'jira_url', fallback='').strip()
        self.jira_user = config.get('Atlassian', 'jira_user', fallback='').strip()
        self.jira_token = config.get('Atlassian', 'jira_token', fallback='').strip()
        self.jira_auth_type = config.get('Atlassian', 'jira_auth_type', fallback='bearer').strip().lower()
        
        # Confluence settings
        self.confluence_url = config.get('Atlassian', 'confluence_url', fallback='').strip()
        self.confluence_user = config.get('Atlassian', 'confluence_user', fallback='').strip()
        self.confluence_token = config.get('Atlassian', 'confluence_token', fallback='').strip()
        self.confluence_auth_type = config.get('Atlassian', 'confluence_auth_type', fallback='bearer').strip().lower()
        
        # Common settings
        ssl_verify_str = config.get('Atlassian', 'ssl_verify', fallback='true').strip().lower()
        self.ssl_verify = ssl_verify_str in ('true', '1', 'yes', 'on')
        try:
            self.timeout = int(config.get('Atlassian', 'timeout', fallback='30'))
        except ValueError:
            self.timeout = 30
        
        # Download settings
        cache_path = config.get('FileManagement', 'cache_path', fallback='').strip()
        default_download = os.path.join(cache_path, 'atlassian') if cache_path else _default_download_path()
        self.download_path = config.get('Atlassian', 'download_path', fallback=default_download)
        try:
            self.max_single_file_size = int(config.get('Atlassian', 'max_single_file_size', fallback='2097152'))
        except ValueError:
            self.max_single_file_size = 2097152  # 2MB
        try:
            self.max_total_download_size = int(config.get('Atlassian', 'max_total_download_size', fallback='10485760'))
        except ValueError:
            self.max_total_download_size = 10485760  # 10MB
    
    def _get_auth_header(self, service: str) -> Dict[str, str]:
        """Get authentication header for the specified service"""
        if service == 'jira':
            user, token, auth_type = self.jira_user, self.jira_token, self.jira_auth_type
        else:
            user, token, auth_type = self.confluence_user, self.confluence_token, self.confluence_auth_type
        
        if auth_type == 'bearer':
            return {"Authorization": f"Bearer {token}"}
        else:
            # Basic auth
            raw = f"{user}:{token}".encode('utf-8')
            return {"Authorization": "Basic " + base64.b64encode(raw).decode('ascii')}
    
    def _is_placeholder_url(self, url: str) -> bool:
        """Check if URL is a placeholder (not configured)"""
        if not url:
            return True
        placeholders = ['your-jira-instance', 'your-confluence-instance', 'example.com', 'your-instance']
        return any(p in url.lower() for p in placeholders)
    
    def _validate_connections(self):
        """Validate Jira and Confluence connections on startup"""
        # Validate Jira
        if self.jira_url and self.jira_token and not self._is_placeholder_url(self.jira_url):
            try:
                headers = self._get_auth_header('jira')
                headers['Content-Type'] = 'application/json'
                resp = requests.get(
                    f"{self.jira_url}/rest/api/2/myself",
                    headers=headers,
                    verify=self.ssl_verify,
                    timeout=self.timeout
                )
                if resp.status_code == 200:
                    self._jira_available = True
                    user_info = resp.json()
                    scm_log(f"Atlassian: Jira connection validated (user: {user_info.get('displayName', 'unknown')})", level='info')
                else:
                    scm_log(f"Atlassian: Jira connection failed (HTTP {resp.status_code})", level='warning')
            except Exception as e:
                scm_log(f"Atlassian: Jira connection failed: {e}", level='warning')
        else:
            scm_log("Atlassian: Jira not configured (missing url or token)", level='info')
        
        # Validate Confluence
        if self.confluence_url and self.confluence_token and not self._is_placeholder_url(self.confluence_url):
            try:
                headers = self._get_auth_header('confluence')
                headers['Content-Type'] = 'application/json'
                resp = requests.get(
                    f"{self.confluence_url}/rest/api/user/current",
                    headers=headers,
                    verify=self.ssl_verify,
                    timeout=self.timeout
                )
                if resp.status_code == 200:
                    self._confluence_available = True
                    user_info = resp.json()
                    scm_log(f"Atlassian: Confluence connection validated (user: {user_info.get('displayName', 'unknown')})", level='info')
                else:
                    scm_log(f"Atlassian: Confluence connection failed (HTTP {resp.status_code})", level='warning')
            except Exception as e:
                scm_log(f"Atlassian: Confluence connection failed: {e}", level='warning')
        else:
            scm_log("Atlassian: Confluence not configured (missing url or token)", level='info')
    
    @property
    def jira_available(self) -> bool:
        return self._jira_available
    
    @property
    def confluence_available(self) -> bool:
        return self._confluence_available
    
    def _make_request(self, service: str, method: str, endpoint: str, 
                      params: Dict = None, data: Dict = None) -> Dict[str, Any]:
        """Make HTTP request to Atlassian API"""
        base_url = self.jira_url if service == 'jira' else self.confluence_url
        url = f"{base_url}{endpoint}"
        
        headers = self._get_auth_header(service)
        headers['Content-Type'] = 'application/json'
        
        try:
            if method.upper() == 'GET':
                resp = requests.get(url, headers=headers, params=params, 
                                   verify=self.ssl_verify, timeout=self.timeout)
            elif method.upper() == 'POST':
                resp = requests.post(url, headers=headers, json=data,
                                    verify=self.ssl_verify, timeout=self.timeout)
            elif method.upper() == 'PUT':
                resp = requests.put(url, headers=headers, json=data,
                                   verify=self.ssl_verify, timeout=self.timeout)
            else:
                return {"status": "error", "error": f"Unsupported method: {method}"}
            
            if resp.status_code >= 200 and resp.status_code < 300:
                try:
                    return {"status": "success", "data": resp.json()}
                except:
                    return {"status": "success", "data": resp.text}
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {resp.status_code}: {resp.text[:500]}",
                    "error_code": resp.status_code
                }
        except requests.exceptions.Timeout:
            return {"status": "error", "error": "Request timeout"}
        except requests.exceptions.ConnectionError as e:
            return {"status": "error", "error": f"Connection error: {e}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    # ==================== JIRA FUNCTIONS ====================
    
    def jira_get_issue(self, issue_key: str, fields: str = None, expand: str = None) -> Dict[str, Any]:
        """
        Get full issue details by key.
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
            fields: Comma-separated list of fields to return (optional)
            expand: Fields to expand (e.g., 'changelog,renderedFields')
            
        Returns:
            Issue details including summary, status, description, etc.
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        params = {}
        if fields:
            params['fields'] = fields
        if expand:
            params['expand'] = expand
        
        return self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}', params=params)
    
    def jira_search_issues(self, jql: str, max_results: int = 50, 
                          fields: str = "key,summary,status,assignee,priority,created,updated") -> Dict[str, Any]:
        """
        Search issues using JQL (Jira Query Language).
        
        Args:
            jql: JQL query string (e.g., 'project = PROJ AND status = Open')
            max_results: Maximum number of results (default: 50)
            fields: Comma-separated list of fields to return
            
        Returns:
            List of matching issues
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        params = {
            'jql': jql,
            'maxResults': max_results,
            'fields': fields
        }
        
        return self._make_request('jira', 'GET', '/rest/api/2/search', params=params)
    
    def jira_get_project_issues(self, project_key: str, limit: int = 50, 
                                status: str = None) -> Dict[str, Any]:
        """
        Get all issues for a project.
        
        Args:
            project_key: Jira project key (e.g., 'PROJ')
            limit: Maximum number of results
            status: Filter by status (optional)
            
        Returns:
            List of project issues
        """
        jql = f'project = {project_key}'
        if status:
            jql += f' AND status = "{status}"'
        jql += ' ORDER BY updated DESC'
        
        return self.jira_search_issues(jql, max_results=limit)
    
    def jira_get_filter_issues(self, filter_id: str = None, jql: str = None, max_results: int = 50,
                               fields: str = "key,summary,status,assignee,priority,created,updated,duedate,customfield_10111,customfield_10603,timeoriginalestimate,labels") -> Dict[str, Any]:
        """
        Get issues from a saved Jira filter or JQL query.
        
        Args:
            filter_id: Jira filter ID (e.g., '12345') - optional if jql is provided
            jql: JQL query string (Jira advanced filter) - optional if filter_id is provided
            max_results: Maximum number of results (default: 50)
            fields: Comma-separated list of fields to return (includes Story Points and Original Estimate)
            
        Returns:
            List of issues matching the filter criteria
            
        Note:
            - duedate: Due Date
            - customfield_10111: Story Points
            - customfield_10603: Owner
            - timeoriginalestimate: Original Estimate (in seconds)
            - labels: Labels
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        if not filter_id and not jql:
            return {"status": "error", "error": "Either filter_id or jql must be provided"}
        
        params = {
            'maxResults': max_results,
            'fields': fields
        }
        
        if jql:
            params['jql'] = jql
            return self._make_request('jira', 'GET', '/rest/api/2/search', params=params)
        else:
            return self._make_request('jira', 'GET', f'/rest/api/2/filter/{filter_id}/issue', params=params)
    
    def jira_get_issue_changelog(self, issue_key: str) -> Dict[str, Any]:
        """
        Get issue change history (who changed what, when).
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of changelog entries with author, date, and changes
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        result = self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}', 
                                   params={'expand': 'changelog'})
        
        if result.get('status') == 'success':
            changelog = result['data'].get('changelog', {}).get('histories', [])
            return {
                "status": "success",
                "data": {
                    "issue_key": issue_key,
                    "total": len(changelog),
                    "histories": changelog
                }
            }
        return result
    
    def jira_get_issue_comments(self, issue_key: str) -> Dict[str, Any]:
        """
        Get all comments for an issue.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of comments with author, date, and body
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        return self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}/comment')
    
    def jira_get_issue_worklog(self, issue_key: str) -> Dict[str, Any]:
        """
        Get time tracking / worklog entries for an issue.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of worklog entries with author, time spent, and date
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        return self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}/worklog')
    
    def jira_get_issue_attachments(self, issue_key: str) -> Dict[str, Any]:
        """
        List all attachments for an issue.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of attachments with filename, size, and download URL
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        result = self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}',
                                   params={'fields': 'attachment'})
        
        if result.get('status') == 'success':
            attachments = result['data'].get('fields', {}).get('attachment', [])
            return {
                "status": "success",
                "data": {
                    "issue_key": issue_key,
                    "total": len(attachments),
                    "attachments": [
                        {
                            "id": att.get('id'),
                            "filename": att.get('filename'),
                            "size": att.get('size'),
                            "mimeType": att.get('mimeType'),
                            "created": att.get('created'),
                            "author": att.get('author', {}).get('displayName'),
                            "content": att.get('content')  # Download URL
                        }
                        for att in attachments
                    ]
                }
            }
        return result
    
    def jira_download_attachment(self, attachment_id: str, issue_key: str) -> Dict[str, Any]:
        """
        Download an attachment (respects size limits).
        
        Args:
            attachment_id: Attachment ID
            issue_key: Issue key (for organizing downloads)
            
        Returns:
            Downloaded file path or error if size exceeded
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        # Get attachment info
        result = self._make_request('jira', 'GET', f'/rest/api/2/attachment/{attachment_id}')
        if result.get('status') != 'success':
            return result
        
        att_info = result['data']
        filename = att_info.get('filename', 'unknown')
        size = att_info.get('size', 0)
        content_url = att_info.get('content')
        
        # Check size limit
        if size > self.max_single_file_size:
            return {
                "status": "error",
                "error": f"File size ({size} bytes) exceeds limit ({self.max_single_file_size} bytes)",
                "filename": filename,
                "size": size
            }
        
        # Create download directory
        download_dir = os.path.join(self.download_path, 'jira', issue_key)
        os.makedirs(download_dir, exist_ok=True)
        file_path = os.path.join(download_dir, filename)
        
        # Download file
        try:
            headers = self._get_auth_header('jira')
            resp = requests.get(content_url, headers=headers, 
                               verify=self.ssl_verify, timeout=self.timeout * 2)
            resp.raise_for_status()
            
            with open(file_path, 'wb') as f:
                f.write(resp.content)
            
            return {
                "status": "success",
                "data": {
                    "filename": filename,
                    "size": size,
                    "path": file_path
                }
            }
        except Exception as e:
            return {"status": "error", "error": f"Download failed: {e}"}
    
    def jira_get_issue_links(self, issue_key: str) -> Dict[str, Any]:
        """
        Get linked issues (blocks, is blocked by, relates to, etc.).
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of linked issues with link type
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        result = self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}',
                                   params={'fields': 'issuelinks'})
        
        if result.get('status') == 'success':
            links = result['data'].get('fields', {}).get('issuelinks', [])
            return {
                "status": "success",
                "data": {
                    "issue_key": issue_key,
                    "total": len(links),
                    "links": links
                }
            }
        return result
    
    def jira_get_remote_links(self, issue_key: str) -> Dict[str, Any]:
        """
        Get external links (Confluence pages, web links, etc.).
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of remote links with URL and title
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        return self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}/remotelink')
    
    def jira_get_project(self, project_key: str) -> Dict[str, Any]:
        """
        Get project details.
        
        Args:
            project_key: Jira project key
            
        Returns:
            Project information including name, lead, description
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        return self._make_request('jira', 'GET', f'/rest/api/2/project/{project_key}')
    
    def jira_get_project_versions(self, project_key: str) -> Dict[str, Any]:
        """
        Get all versions for a project.
        
        Args:
            project_key: Jira project key
            
        Returns:
            List of versions with release dates and status
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        return self._make_request('jira', 'GET', f'/rest/api/2/project/{project_key}/versions')
    
    def jira_get_version_issues(self, version_id: str, status: str = None) -> Dict[str, Any]:
        """
        Get all issues in a specific version.
        
        Args:
            version_id: Version ID
            status: Filter by status (optional)
            
        Returns:
            List of issues in the version
        """
        jql = f'fixVersion = {version_id}'
        if status:
            jql += f' AND status = "{status}"'
        
        return self.jira_search_issues(jql, max_results=100)
    
    def jira_get_project_components(self, project_key: str) -> Dict[str, Any]:
        """
        Get all components for a project.
        
        Args:
            project_key: Jira project key
            
        Returns:
            List of components with lead and description
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        return self._make_request('jira', 'GET', f'/rest/api/2/project/{project_key}/components')
    
    def jira_get_transitions(self, issue_key: str) -> Dict[str, Any]:
        """
        Get available status transitions for an issue.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of available transitions
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        return self._make_request('jira', 'GET', f'/rest/api/2/issue/{issue_key}/transitions')
    
    def jira_add_comment(self, issue_key: str, comment: str) -> Dict[str, Any]:
        """
        Add a comment to an issue.
        
        Args:
            issue_key: Jira issue key
            comment: Comment text
            
        Returns:
            Created comment details
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        data = {"body": comment}
        return self._make_request('jira', 'POST', f'/rest/api/2/issue/{issue_key}/comment', data=data)
    
    def jira_transition_issue(self, issue_key: str, transition_id: str, 
                             comment: str = None) -> Dict[str, Any]:
        """
        Transition an issue to a new status.
        
        Args:
            issue_key: Jira issue key
            transition_id: Transition ID (get from jira_get_transitions)
            comment: Optional comment for the transition
            
        Returns:
            Success or error status
        """
        if not self._jira_available:
            return {"status": "error", "error": "Jira not available"}
        
        data = {
            "transition": {"id": transition_id}
        }
        if comment:
            data["update"] = {
                "comment": [{"add": {"body": comment}}]
            }
        
        return self._make_request('jira', 'POST', f'/rest/api/2/issue/{issue_key}/transitions', data=data)
    
    def jira_count_issues_by_status(self, project_key: str, version: str = None) -> Dict[str, Any]:
        """
        Count issues grouped by status.
        
        Args:
            project_key: Jira project key
            version: Filter by version (optional)
            
        Returns:
            Count of issues per status
        """
        jql = f'project = {project_key}'
        if version:
            jql += f' AND fixVersion = "{version}"'
        
        result = self.jira_search_issues(jql, max_results=1000, fields='status')
        
        if result.get('status') == 'success':
            issues = result['data'].get('issues', [])
            status_counts = {}
            for issue in issues:
                status = issue.get('fields', {}).get('status', {}).get('name', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "status": "success",
                "data": {
                    "project_key": project_key,
                    "version": version,
                    "total": len(issues),
                    "by_status": status_counts
                }
            }
        return result
    
    def jira_count_issues_by_type(self, project_key: str, version: str = None) -> Dict[str, Any]:
        """
        Count issues grouped by type (Bug, Task, Story, etc.).
        
        Args:
            project_key: Jira project key
            version: Filter by version (optional)
            
        Returns:
            Count of issues per type
        """
        jql = f'project = {project_key}'
        if version:
            jql += f' AND fixVersion = "{version}"'
        
        result = self.jira_search_issues(jql, max_results=1000, fields='issuetype')
        
        if result.get('status') == 'success':
            issues = result['data'].get('issues', [])
            type_counts = {}
            for issue in issues:
                issue_type = issue.get('fields', {}).get('issuetype', {}).get('name', 'Unknown')
                type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
            
            return {
                "status": "success",
                "data": {
                    "project_key": project_key,
                    "version": version,
                    "total": len(issues),
                    "by_type": type_counts
                }
            }
        return result
    
    def jira_count_issues_by_assignee(self, project_key: str, version: str = None) -> Dict[str, Any]:
        """
        Count issues grouped by assignee.
        
        Args:
            project_key: Jira project key
            version: Filter by version (optional)
            
        Returns:
            Count of issues per assignee
        """
        jql = f'project = {project_key}'
        if version:
            jql += f' AND fixVersion = "{version}"'
        
        result = self.jira_search_issues(jql, max_results=1000, fields='assignee')
        
        if result.get('status') == 'success':
            issues = result['data'].get('issues', [])
            assignee_counts = {}
            for issue in issues:
                assignee = issue.get('fields', {}).get('assignee')
                if assignee:
                    name = assignee.get('displayName', 'Unknown')
                else:
                    name = 'Unassigned'
                assignee_counts[name] = assignee_counts.get(name, 0) + 1
            
            return {
                "status": "success",
                "data": {
                    "project_key": project_key,
                    "version": version,
                    "total": len(issues),
                    "by_assignee": assignee_counts
                }
            }
        return result
    
    # ==================== CONFLUENCE FUNCTIONS ====================
    
    def confluence_get_page(self, page_id: str = None, space_key: str = None, 
                           title: str = None) -> Dict[str, Any]:
        """
        Get page content by ID or by space_key + title.
        
        Args:
            page_id: Confluence page ID (preferred)
            space_key: Space key (use with title)
            title: Page title (use with space_key)
            
        Returns:
            Page content and metadata
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        if page_id:
            return self._make_request('confluence', 'GET', f'/rest/api/content/{page_id}',
                                     params={'expand': 'body.storage,version,space'})
        elif space_key and title:
            params = {
                'spaceKey': space_key,
                'title': title,
                'expand': 'body.storage,version,space'
            }
            return self._make_request('confluence', 'GET', '/rest/api/content', params=params)
        else:
            return {"status": "error", "error": "Must provide page_id or (space_key + title)"}
    
    def confluence_search(self, query: str, limit: int = 25, 
                         space_key: str = None) -> Dict[str, Any]:
        """
        Search Confluence content using CQL.
        
        Args:
            query: Search query (CQL or text)
            limit: Maximum results
            space_key: Filter by space (optional)
            
        Returns:
            List of matching pages
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        cql = f'text ~ "{query}"'
        if space_key:
            cql += f' AND space = "{space_key}"'
        
        params = {
            'cql': cql,
            'limit': limit
        }
        
        return self._make_request('confluence', 'GET', '/rest/api/content/search', params=params)
    
    def confluence_get_page_children(self, parent_id: str, limit: int = 25) -> Dict[str, Any]:
        """
        Get child pages of a parent page.
        
        Args:
            parent_id: Parent page ID
            limit: Maximum results
            
        Returns:
            List of child pages
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        params = {
            'expand': 'version',
            'limit': limit
        }
        
        return self._make_request('confluence', 'GET', 
                                 f'/rest/api/content/{parent_id}/child/page', params=params)
    
    def confluence_get_page_history(self, page_id: str) -> Dict[str, Any]:
        """
        Get page version history.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            List of page versions with author and date
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        return self._make_request('confluence', 'GET', f'/rest/api/content/{page_id}/history')
    
    def confluence_get_page_comments(self, page_id: str) -> Dict[str, Any]:
        """
        Get comments on a page.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            List of comments
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        params = {'expand': 'body.storage,version'}
        return self._make_request('confluence', 'GET', 
                                 f'/rest/api/content/{page_id}/child/comment', params=params)
    
    def confluence_get_page_attachments(self, page_id: str) -> Dict[str, Any]:
        """
        List attachments on a page.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            List of attachments with download URLs
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        return self._make_request('confluence', 'GET', 
                                 f'/rest/api/content/{page_id}/child/attachment')
    
    def confluence_download_attachment(self, attachment_id: str, page_id: str) -> Dict[str, Any]:
        """
        Download an attachment (respects size limits).
        
        Args:
            attachment_id: Attachment ID
            page_id: Page ID (for organizing downloads)
            
        Returns:
            Downloaded file path or error
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        # Get attachment info
        result = self._make_request('confluence', 'GET', f'/rest/api/content/{attachment_id}')
        if result.get('status') != 'success':
            return result
        
        att_info = result['data']
        title = att_info.get('title', 'unknown')
        
        # Get download link
        download_link = att_info.get('_links', {}).get('download')
        if not download_link:
            return {"status": "error", "error": "No download link found"}
        
        download_url = f"{self.confluence_url}/wiki{download_link}"
        
        # Create download directory
        download_dir = os.path.join(self.download_path, 'confluence', page_id)
        os.makedirs(download_dir, exist_ok=True)
        file_path = os.path.join(download_dir, title)
        
        # Download file
        try:
            headers = self._get_auth_header('confluence')
            resp = requests.get(download_url, headers=headers,
                               verify=self.ssl_verify, timeout=self.timeout * 2)
            resp.raise_for_status()
            
            # Check size
            if len(resp.content) > self.max_single_file_size:
                return {
                    "status": "error",
                    "error": f"File size ({len(resp.content)} bytes) exceeds limit",
                    "filename": title
                }
            
            with open(file_path, 'wb') as f:
                f.write(resp.content)
            
            return {
                "status": "success",
                "data": {
                    "filename": title,
                    "size": len(resp.content),
                    "path": file_path
                }
            }
        except Exception as e:
            return {"status": "error", "error": f"Download failed: {e}"}
    
    def confluence_get_page_labels(self, page_id: str) -> Dict[str, Any]:
        """
        Get labels on a page.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            List of labels
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        return self._make_request('confluence', 'GET', f'/rest/api/content/{page_id}/label')
    
    def confluence_get_space(self, space_key: str) -> Dict[str, Any]:
        """
        Get space information.
        
        Args:
            space_key: Confluence space key
            
        Returns:
            Space details including name, description, homepage
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        params = {'expand': 'description.plain,homepage'}
        return self._make_request('confluence', 'GET', f'/rest/api/space/{space_key}', params=params)
    
    def confluence_get_space_pages(self, space_key: str, limit: int = 25) -> Dict[str, Any]:
        """
        List pages in a space.
        
        Args:
            space_key: Confluence space key
            limit: Maximum results
            
        Returns:
            List of pages in the space
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        params = {
            'spaceKey': space_key,
            'type': 'page',
            'limit': limit,
            'expand': 'version'
        }
        
        return self._make_request('confluence', 'GET', '/rest/api/content', params=params)
    
    def confluence_search_in_space(self, space_key: str, query: str, 
                                   limit: int = 25) -> Dict[str, Any]:
        """
        Search within a specific space.
        
        Args:
            space_key: Confluence space key
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching pages in the space
        """
        return self.confluence_search(query, limit=limit, space_key=space_key)
    
    def confluence_add_comment(self, page_id: str, comment: str) -> Dict[str, Any]:
        """
        Add a comment to a page.
        
        Args:
            page_id: Confluence page ID
            comment: Comment text
            
        Returns:
            Created comment details
        """
        if not self._confluence_available:
            return {"status": "error", "error": "Confluence not available"}
        
        data = {
            "type": "comment",
            "container": {"id": page_id, "type": "page"},
            "body": {
                "storage": {
                    "value": comment,
                    "representation": "storage"
                }
            }
        }
        
        return self._make_request('confluence', 'POST', '/rest/api/content', data=data)


# ==================== SINGLETON INSTANCE ====================

_bridge_instance = None

def get_bridge(jira_config=None, confluence_config=None, connection_config=None) -> AtlassianBridge:
    """
    Get or create the bridge instance
    
    Args:
        jira_config: Optional Jira configuration dict (v2.6+)
        confluence_config: Optional Confluence configuration dict (v2.6+)
        connection_config: Optional connection settings (ssl_verify, timeout) (v2.6+)
    
    Returns:
        AtlassianBridge instance (singleton for config.ini, new instance for profile configs)
    """
    global _bridge_instance
    
    # If profile credentials provided, create new instance (v2.6+)
    if jira_config is not None or confluence_config is not None:
        return AtlassianBridge(jira_config, confluence_config, connection_config)
    
    # Otherwise use singleton for config.ini (backward compatibility)
    if _bridge_instance is None:
        _bridge_instance = AtlassianBridge()
    return _bridge_instance

def set_bridge(bridge: AtlassianBridge):
    """Set the global bridge instance (used in v2.6+ for profile-specific credentials)"""
    global _bridge_instance
    _bridge_instance = bridge


# ==================== MODULE-LEVEL WRAPPER FUNCTIONS ====================
# These are the functions that OWL will call directly

def jira_get_issue(issue_key: str, fields: str = None, expand: str = None, **kwargs) -> Dict[str, Any]:
    """Get full issue details by key."""
    return get_bridge().jira_get_issue(issue_key, fields, expand)

def jira_search_issues(jql: str, max_results: int = 50, fields: str = None, **kwargs) -> Dict[str, Any]:
    """Search issues using JQL."""
    return get_bridge().jira_search_issues(jql, max_results, fields or "key,summary,status,assignee,priority,created,updated")

def jira_get_project_issues(project_key: str, limit: int = 50, status: str = None, **kwargs) -> Dict[str, Any]:
    """Get all issues for a project."""
    return get_bridge().jira_get_project_issues(project_key, limit, status)

def jira_get_filter_issues(filter_id: str = None, jql: str = None, max_results: int = 50, fields: str = None, **kwargs) -> Dict[str, Any]:
    """Get issues from a saved Jira filter or JQL query."""
    return get_bridge().jira_get_filter_issues(filter_id, jql, max_results, fields or "key,summary,status,assignee,priority,created,updated,duedate,customfield_10111,customfield_10603,timeoriginalestimate,labels")

def jira_get_issue_changelog(issue_key: str, **kwargs) -> Dict[str, Any]:
    """Get issue change history."""
    return get_bridge().jira_get_issue_changelog(issue_key)

def jira_get_issue_comments(issue_key: str, **kwargs) -> Dict[str, Any]:
    """Get all comments for an issue."""
    return get_bridge().jira_get_issue_comments(issue_key)

def jira_get_issue_worklog(issue_key: str, **kwargs) -> Dict[str, Any]:
    """Get time tracking / worklog entries."""
    return get_bridge().jira_get_issue_worklog(issue_key)

def jira_get_issue_attachments(issue_key: str, **kwargs) -> Dict[str, Any]:
    """List all attachments for an issue."""
    return get_bridge().jira_get_issue_attachments(issue_key)

def jira_download_attachment(attachment_id: str, issue_key: str, **kwargs) -> Dict[str, Any]:
    """Download an attachment."""
    return get_bridge().jira_download_attachment(attachment_id, issue_key)

def jira_get_issue_links(issue_key: str, **kwargs) -> Dict[str, Any]:
    """Get linked issues."""
    return get_bridge().jira_get_issue_links(issue_key)

def jira_get_remote_links(issue_key: str, **kwargs) -> Dict[str, Any]:
    """Get external links (Confluence pages, etc.)."""
    return get_bridge().jira_get_remote_links(issue_key)

def jira_get_project(project_key: str, **kwargs) -> Dict[str, Any]:
    """Get project details."""
    return get_bridge().jira_get_project(project_key)

def jira_get_project_versions(project_key: str, **kwargs) -> Dict[str, Any]:
    """Get all versions for a project."""
    return get_bridge().jira_get_project_versions(project_key)

def jira_get_version_issues(version_id: str, status: str = None, **kwargs) -> Dict[str, Any]:
    """Get all issues in a version."""
    return get_bridge().jira_get_version_issues(version_id, status)

def jira_get_project_components(project_key: str, **kwargs) -> Dict[str, Any]:
    """Get all components for a project."""
    return get_bridge().jira_get_project_components(project_key)

def jira_get_transitions(issue_key: str, **kwargs) -> Dict[str, Any]:
    """Get available status transitions."""
    return get_bridge().jira_get_transitions(issue_key)

def jira_add_comment(issue_key: str, comment: str, **kwargs) -> Dict[str, Any]:
    """Add a comment to an issue."""
    return get_bridge().jira_add_comment(issue_key, comment)

def jira_transition_issue(issue_key: str, transition_id: str, comment: str = None, **kwargs) -> Dict[str, Any]:
    """Transition an issue to a new status."""
    return get_bridge().jira_transition_issue(issue_key, transition_id, comment)

def jira_count_issues_by_status(project_key: str, version: str = None, **kwargs) -> Dict[str, Any]:
    """Count issues grouped by status."""
    return get_bridge().jira_count_issues_by_status(project_key, version)

def jira_count_issues_by_type(project_key: str, version: str = None, **kwargs) -> Dict[str, Any]:
    """Count issues grouped by type."""
    return get_bridge().jira_count_issues_by_type(project_key, version)

def jira_count_issues_by_assignee(project_key: str, version: str = None, **kwargs) -> Dict[str, Any]:
    """Count issues grouped by assignee."""
    return get_bridge().jira_count_issues_by_assignee(project_key, version)

# Confluence functions
def confluence_get_page(page_id: str = None, space_key: str = None, title: str = None, **kwargs) -> Dict[str, Any]:
    """Get page content."""
    return get_bridge().confluence_get_page(page_id, space_key, title)

def confluence_search(query: str, limit: int = 25, space_key: str = None, **kwargs) -> Dict[str, Any]:
    """Search Confluence content."""
    return get_bridge().confluence_search(query, limit, space_key)

def confluence_get_page_children(parent_id: str, limit: int = 25, **kwargs) -> Dict[str, Any]:
    """Get child pages."""
    return get_bridge().confluence_get_page_children(parent_id, limit)

def confluence_get_page_history(page_id: str, **kwargs) -> Dict[str, Any]:
    """Get page version history."""
    return get_bridge().confluence_get_page_history(page_id)

def confluence_get_page_comments(page_id: str, **kwargs) -> Dict[str, Any]:
    """Get comments on a page."""
    return get_bridge().confluence_get_page_comments(page_id)

def confluence_get_page_attachments(page_id: str, **kwargs) -> Dict[str, Any]:
    """List attachments on a page."""
    return get_bridge().confluence_get_page_attachments(page_id)

def confluence_download_attachment(attachment_id: str, page_id: str, **kwargs) -> Dict[str, Any]:
    """Download an attachment."""
    return get_bridge().confluence_download_attachment(attachment_id, page_id)

def confluence_get_page_labels(page_id: str, **kwargs) -> Dict[str, Any]:
    """Get labels on a page."""
    return get_bridge().confluence_get_page_labels(page_id)

def confluence_get_space(space_key: str, **kwargs) -> Dict[str, Any]:
    """Get space information."""
    return get_bridge().confluence_get_space(space_key)

def confluence_get_space_pages(space_key: str, limit: int = 25, **kwargs) -> Dict[str, Any]:
    """List pages in a space."""
    return get_bridge().confluence_get_space_pages(space_key, limit)

def confluence_search_in_space(space_key: str, query: str, limit: int = 25, **kwargs) -> Dict[str, Any]:
    """Search within a specific space."""
    return get_bridge().confluence_search_in_space(space_key, query, limit)

def confluence_add_comment(page_id: str, comment: str, **kwargs) -> Dict[str, Any]:
    """Add a comment to a page."""
    return get_bridge().confluence_add_comment(page_id, comment)


# ==================== TOOL REGISTRATION ====================

def get_available_tools() -> Dict[str, Dict[str, Tuple[str, str]]]:
    """
    Return tools based on connection availability.
    Only registers tools if the corresponding service is connected.
    """
    bridge = get_bridge()
    tools = {}
    
    if bridge.jira_available:
        tools["jira"] = {
            # Category 1: Issue Operations (Basic)
            "get_issue": ("mcp_servers.mcp_atlassian_bridge", "jira_get_issue"),
            "search_issues": ("mcp_servers.mcp_atlassian_bridge", "jira_search_issues"),
            "get_project_issues": ("mcp_servers.mcp_atlassian_bridge", "jira_get_project_issues"),
            # Category 2: Issue Audit & Analysis
            "get_issue_changelog": ("mcp_servers.mcp_atlassian_bridge", "jira_get_issue_changelog"),
            "get_issue_comments": ("mcp_servers.mcp_atlassian_bridge", "jira_get_issue_comments"),
            "get_issue_worklog": ("mcp_servers.mcp_atlassian_bridge", "jira_get_issue_worklog"),
            "get_issue_attachments": ("mcp_servers.mcp_atlassian_bridge", "jira_get_issue_attachments"),
            "download_attachment": ("mcp_servers.mcp_atlassian_bridge", "jira_download_attachment"),
            "get_issue_links": ("mcp_servers.mcp_atlassian_bridge", "jira_get_issue_links"),
            "get_remote_links": ("mcp_servers.mcp_atlassian_bridge", "jira_get_remote_links"),
            # Category 3: Project & Version Analysis
            "get_project": ("mcp_servers.mcp_atlassian_bridge", "jira_get_project"),
            "get_project_versions": ("mcp_servers.mcp_atlassian_bridge", "jira_get_project_versions"),
            "get_version_issues": ("mcp_servers.mcp_atlassian_bridge", "jira_get_version_issues"),
            "get_project_components": ("mcp_servers.mcp_atlassian_bridge", "jira_get_project_components"),
            # Category 4: Statistics
            "count_issues_by_status": ("mcp_servers.mcp_atlassian_bridge", "jira_count_issues_by_status"),
            "count_issues_by_type": ("mcp_servers.mcp_atlassian_bridge", "jira_count_issues_by_type"),
            "count_issues_by_assignee": ("mcp_servers.mcp_atlassian_bridge", "jira_count_issues_by_assignee"),
            # Category 5: Write Operations
            "add_comment": ("mcp_servers.mcp_atlassian_bridge", "jira_add_comment"),
            "get_transitions": ("mcp_servers.mcp_atlassian_bridge", "jira_get_transitions"),
            "transition_issue": ("mcp_servers.mcp_atlassian_bridge", "jira_transition_issue"),
        }
    
    if bridge.confluence_available:
        tools["confluence"] = {
            # Category 1: Page Operations (Basic)
            "get_page": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_page"),
            "search": ("mcp_servers.mcp_atlassian_bridge", "confluence_search"),
            "get_page_children": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_page_children"),
            # Category 2: Content Analysis
            "get_page_history": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_page_history"),
            "get_page_comments": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_page_comments"),
            "get_page_attachments": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_page_attachments"),
            "download_attachment": ("mcp_servers.mcp_atlassian_bridge", "confluence_download_attachment"),
            "get_page_labels": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_page_labels"),
            # Category 3: Space Operations
            "get_space": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_space"),
            "get_space_pages": ("mcp_servers.mcp_atlassian_bridge", "confluence_get_space_pages"),
            "search_in_space": ("mcp_servers.mcp_atlassian_bridge", "confluence_search_in_space"),
            # Category 4: Write Operations
            "add_comment": ("mcp_servers.mcp_atlassian_bridge", "confluence_add_comment"),
        }
    
    return tools


# Export for mcp_auto_register.py
ATLASSIAN_TOOLS = get_available_tools()


# ==================== MAIN (for testing) ====================

if __name__ == "__main__":
    print("=" * 60)
    print("MCP Atlassian Bridge - Connection Test")
    print("=" * 60)
    
    bridge = get_bridge()
    
    print(f"\nJira Available: {bridge.jira_available}")
    print(f"Confluence Available: {bridge.confluence_available}")
    
    print(f"\nRegistered Tools:")
    for service, tools in ATLASSIAN_TOOLS.items():
        print(f"  {service}: {len(tools)} tools")
        for tool_name in list(tools.keys())[:5]:
            print(f"    - {tool_name}")
        if len(tools) > 5:
            print(f"    ... and {len(tools) - 5} more")
    
    # Quick test if Jira is available
    if bridge.jira_available:
        print("\n--- Quick Jira Test ---")
        # Test search
        result = jira_search_issues("project IS NOT EMPTY", max_results=1)
        if result.get('status') == 'success':
            total = result['data'].get('total', 0)
            print(f"Search test: Found {total} issues total")
        else:
            print(f"Search test failed: {result.get('error')}")
    
    if bridge.confluence_available:
        print("\n--- Quick Confluence Test ---")
        # Test search
        result = confluence_search("test", limit=1)
        if result.get('status') == 'success':
            print(f"Search test: Success")
        else:
            print(f"Search test failed: {result.get('error')}")
    
    print("\n" + "=" * 60)
