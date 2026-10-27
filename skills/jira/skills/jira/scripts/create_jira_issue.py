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
Jira Issue Creator - Create Jira tickets for FW Feature/FW Bug/FW Task

Two modes:

  legacy (default)   create immediately, no description template.
  --structured       validate the description template, discover fields, and
                     preview first; add --execute to actually create.

Usage:
    python create_jira_issue.py --project <PROJECT_KEY> --type <ISSUE_TYPE> \
        --summary "<SUMMARY>" --description "<DESCRIPTION>"

    python create_jira_issue.py --structured --project DZ300 --type Story \
        --summary "<SUMMARY>" --description-file story.md --output-format markdown
    # ... review the preview, then re-run the same command with --execute

Discovery modes (no issue is created):
    --discover-meta / --discover-fields / --discover-epics
    --discover-sprints / --discover-users

Interview (no issue is created):
    --interview         output 4 required + 2 optional questions, each with a
                        hint, an example and a counter-example

Options:
    --project       Project key (e.g., DUZ01, AD)
    --type          Issue type (e.g., "FW Feature", "FW Bug", "Story")
    --summary       Issue summary/title
    --description   Issue description (Jira markup)
    --description-file  Read the description from a UTF-8 file (wins over --description)
    --priority      Priority: Critical, High, Medium, Low (default: Medium)
    --assignee      displayName / email / username (resolved, ambiguity is an error)
    --labels        Comma-separated labels
    --components    Comma-separated component names
    --estimate      Original estimate (e.g., "2d", "8h")
    --reported-by   Reported By (required for FW Bug, default: TBD)
    --steps         Steps to Reproduce (required for FW Bug, default: TBD)
    --version       Affects Version (required for FW Bug, default: auto-detect)
    --epic          Epic key to link this issue to (must be an Epic issue)
    --sprint        Sprint id (use --discover-sprints)
    --story-points  Story Points value
    --parent        Parent issue key
    --due-date      Due date, YYYY-MM-DD
    --field         Arbitrary field override KEY=VALUE (repeatable)
    --no-verify     Skip the post-create read-back verification
    --json          Output the create result as JSON
"""

import argparse
import json
import os
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

# Disable SSL warnings for internal servers
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

from config_loader import load_jira_config, validate_jira_config
from description_lint import lint_description
from issue_creator import build_payload, create_issue
import interview
from jira_client import JiraClient, JiraError
from jira_fields import (
    check_required_fields,
    discover_epics,
    discover_fields,
    discover_sprints,
    discover_users,
    fetch_create_meta,
    get_project_versions,
)

# Load configuration
JIRA_CONFIG = load_jira_config()


def _skill_version() -> str:
    """读取安装目录里的 VERSION（install.sh 写入）；仓库内没有该文件时返回空串。"""
    try:
        return (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def list_issue_types(client: JiraClient, project_key: str) -> None:
    """Print the issue types available in a project."""
    try:
        data = client.request("GET", "/project/%s" % project_key)
    except JiraError as exc:
        print("Error: %s" % exc)
        return

    print("\nAvailable issue types for project '%s':" % project_key)
    print("-" * 50)
    for issue_type in data.get("issueTypes", []):
        print("  - %s (ID: %s)" % (issue_type.get("name"), issue_type.get("id")))
        if issue_type.get("description"):
            print("    %s..." % issue_type["description"][:60])
    print()


def format_output(data: Dict[str, Any]) -> str:
    """Format the output for display."""
    if data.get("status") == "error":
        return "Error: %s" % data.get("error", "Unknown error")

    result = data.get("data", {})
    output = []
    output.append("=" * 60)
    output.append("JIRA TICKET CREATED SUCCESSFULLY")
    output.append("=" * 60)
    output.append("Issue Key:  %s" % result.get("key", "N/A"))
    output.append("Issue ID:   %s" % result.get("id", "N/A"))
    output.append("Project:    %s" % result.get("project", "N/A"))
    output.append("Type:       %s" % result.get("type", "N/A"))
    output.append("Summary:    %s" % result.get("summary", "N/A"))
    output.append("-" * 60)
    output.append("URL: %s" % result.get("url", "N/A"))
    output.append("=" * 60)

    return "\n".join(output)


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def read_description(args) -> str:
    """读取描述：--description-file 优先，否则用 --description。"""
    path = getattr(args, "description_file", None)
    if path:
        description_path = Path(path)
        if not description_path.is_file():
            raise JiraError("--description-file 不存在: %s" % description_path)
        return description_path.read_text(encoding="utf-8")
    return args.description or ""


def _emit(payload, args) -> None:
    """统一输出：写文件（UTF-8 无 BOM）或打印。"""
    out_file = getattr(args, "output_file", None)
    if isinstance(payload, str):
        text = payload
    else:
        indent = 2 if getattr(args, "pretty", False) or out_file else None
        text = json.dumps(payload, ensure_ascii=False, indent=indent)

    if not out_file:
        print(text)
        return

    if os.sep in out_file or "/" in out_file or Path(out_file).is_absolute():
        path = Path(out_file)
    else:
        out_dir = Path(getattr(args, "output_dir", tempfile.gettempdir()))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / out_file
    path.write_text(text, encoding="utf-8")
    print("Written to %s" % path, file=sys.stderr)


def _markdown_preview(
    fields, extras, missing, meta_error, lint_errors, lint_warnings, simple, url
) -> str:
    """渲染给人看的 dry-run 预览（markdown）。"""
    lines = ["# 待创建 Story 预览", ""]
    version = _skill_version()
    if version:
        lines.append("- 创建工具: `jira` skill v%s" % version)
    lines.append("- 项目: `%s`" % fields.get("project", {}).get("key"))
    lines.append("- 类型: `%s`" % (extras.get("issue_type") or fields.get("issuetype", {}).get("name")))
    lines.append("- 标题: %s" % fields.get("summary"))
    if simple:
        lines.append("- 档位: **简单档**（`--simple`，描述小节校验已放宽）")
    if fields.get("priority"):
        lines.append("- 优先级: %s" % fields["priority"].get("name"))
    if extras.get("assignee"):
        lines.append(
            "- 经办人: %s (`%s`)"
            % (extras["assignee"].get("displayName"), extras["assignee"].get("name"))
        )
    if fields.get("labels"):
        lines.append("- 标签: %s" % ", ".join(fields["labels"]))
    if fields.get("components"):
        lines.append("- 组件: %s" % ", ".join(c.get("name", "") for c in fields["components"]))
    if extras.get("parent"):
        lines.append("- 父 issue: `%s`" % extras["parent"].get("key"))
    if extras.get("due_date"):
        lines.append("- 截止日期: %s" % extras["due_date"])
    if extras.get("story_points") is not None:
        lines.append("- Story Points: %s" % extras["story_points"])
    if extras.get("sprint"):
        lines.append("- Sprint: id=%s" % extras["sprint"].get("id"))

    lines.append("")
    if extras.get("epic_link"):
        epic = extras["epic_link"]
        lines.append("## ⚠️ Epic 关联（必须由用户确认）")
        lines.append("")
        lines.append("- **%s** — %s" % (epic.get("key"), epic.get("summary")))
        lines.append("- 若用户未明确选择此 Epic，请先停下来让用户确认，不要直接创建。")
    else:
        lines.append("## Epic 关联")
        lines.append("")
        lines.append("- **未关联任何 Epic**（用户未指定）。若需求应归属某个 Epic，请先与用户确认。")

    if extras.get("notes"):
        lines.append("")
        lines.append("## 字段解析")
        lines.extend("- %s" % note for note in extras["notes"])

    if missing:
        lines.append("")
        lines.append("## 必填字段缺失（创建会失败）")
        lines.extend("- %s" % item for item in missing)
    if meta_error:
        lines.append("")
        lines.append("## 必填字段校验未完成")
        lines.append("- %s" % meta_error)

    if lint_errors or lint_warnings:
        lines.append("")
        lines.append("## ⚠️ 描述质量检查")
        lines.append("")
        if lint_errors:
            lines.append("**必须修复（会阻止创建）：**")
            lines.extend("- ❌ %s" % error for error in lint_errors)
        if lint_warnings:
            lines.append("**建议修复：**")
            lines.extend("- ⚠️ %s" % warning for warning in lint_warnings)
        lines.append("")
        lines.append("上述问题若源于需求本身不明确，**先向用户澄清**，不要自行假设后填入。")

    lines.append("")
    lines.append("## 需求描述（description）")
    lines.append("")
    lines.append(fields.get("description") or "_(空)_")
    lines.append("")
    lines.append("目标端点: `POST %s`" % url)
    return "\n".join(lines)


def _print_create_result(args, result, description_warnings) -> None:
    if result["unapplied"]:
        print(
            "[warn] 以下字段补 PUT 后仍未写入，请人工在 Jira 上确认: %s" % result["unapplied"],
            file=sys.stderr,
        )

    payload = {
        "status": "success",
        "data": {
            "key": result["key"],
            "id": result["id"],
            "url": result["url"],
            "summary": args.summary,
            "type": args.issue_type,
            "project": args.project,
            "epic_key": args.epic,
            "post_create_fixups": result["fixups"],
            "unapplied_fields": result["unapplied"],
            "description_warnings": description_warnings,
        },
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_output(payload))


def _fail(args, message: str) -> None:
    error = {"status": "error", "error": message}
    if getattr(args, "json", False):
        print(json.dumps(error, indent=2, ensure_ascii=False))
    else:
        print(format_output(error))
    sys.exit(1)


def _require_project(args, mode: str) -> str:
    if not args.project:
        _fail(args, "%s 需要 --project（或配置 jira 项目）。" % mode)
    return args.project


def _discover_meta(args, client) -> None:
    project = _require_project(args, "--discover-meta")
    try:
        meta = fetch_create_meta(client, project, args.issue_type)
    except JiraError as exc:
        _fail(args, str(exc))

    if args.output_format != "markdown":
        _emit(meta, args)
        return

    lines = ["# %s 可用 issue type" % project, ""]
    for issue_type in meta["issue_types"]:
        lines.append("- %s (id=%s)" % (issue_type["name"], issue_type["id"]))
    lines.append("")
    for type_name, fields in meta["fields_by_issue_type"].items():
        lines.append("## %s 必填字段" % type_name)
        required = [
            "- `%s` %s" % (field_id, field.get("name"))
            for field_id, field in fields.items()
            if isinstance(field, dict) and field.get("required") and not field.get("hasDefaultValue")
        ]
        lines.extend(required or ["- (无必填字段)"])
        lines.append("")
    _emit("\n".join(lines), args)


def main():
    parser = argparse.ArgumentParser(
        description="Create Jira tickets (legacy immediate mode, or --structured with preview)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Legacy: create immediately
  python create_jira_issue.py --project DUZ01 --type "FW Feature" \\
    --summary "[AD][X85] Support AT service" --description "h2. Background..."

  # Structured: preview first, then re-run with --execute
  python create_jira_issue.py --structured --project DZ300 --type Story \\
    --summary "[Mamba] Make EQ span configurable" \\
    --description-file story.md --epic DZ300-123 --story-points 3 \\
    --output-format markdown
  python create_jira_issue.py --structured --execute --project DZ300 --type Story \\
    --summary "[Mamba] Make EQ span configurable" \\
    --description-file story.md --epic DZ300-123 --story-points 3

  # Discovery
  python create_jira_issue.py --discover-meta --project DZ300 --type Story
  python create_jira_issue.py --discover-epics --project DZ300
        """,
    )

    parser.add_argument("--project", "-p", help="Project key (e.g., DUZ01)")
    parser.add_argument("--type", "-t", dest="issue_type", help="Issue type (e.g., 'FW Bug', 'Story')")
    parser.add_argument("--summary", "-s", help="Issue summary/title")
    parser.add_argument("--description", "-d", help="Issue description (Jira markup)")
    parser.add_argument(
        "--description-file", help="Read the description from a UTF-8 file (wins over --description)"
    )
    parser.add_argument(
        "--priority",
        default="Medium",
        choices=["Critical", "High", "Medium", "Low"],
        help="Priority level (default: Medium)",
    )
    parser.add_argument("--assignee", "-a", help="displayName / email / username")
    parser.add_argument("--labels", "-l", help="Comma-separated labels")
    parser.add_argument("--components", "-c", help="Comma-separated component names")
    parser.add_argument("--estimate", "-e", help="Original estimate (e.g., '2d', '8h')")
    parser.add_argument("--reported-by", help="Reported By (required for FW Bug, default: TBD)")
    parser.add_argument("--steps", help="Steps to Reproduce (required for FW Bug, default: TBD)")
    parser.add_argument(
        "--version", "-v", help="Affects Version (required for FW Bug, default: auto-detect)"
    )
    parser.add_argument("--epic", help="Epic key to link this issue to (e.g., SWP00-13)")
    parser.add_argument("--sprint", help="Sprint id (use --discover-sprints)")
    parser.add_argument("--story-points", type=int, help="Story Points value")
    parser.add_argument("--parent", help="Parent issue key")
    parser.add_argument("--due-date", help="Due date, YYYY-MM-DD")
    parser.add_argument(
        "--field", action="append", default=[], help="Arbitrary field override KEY=VALUE (repeatable)"
    )
    parser.add_argument(
        "--structured",
        action="store_true",
        help="Enable the description template, lint, and field discovery; previews by default",
    )
    parser.add_argument(
        "--execute", action="store_true", help="Actually create (only meaningful with --structured)"
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Relax the description checks (skip required sections; still reject empty descriptions)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="创建后不回读校验字段（默认会校验，并对被 Jira 静默丢弃的字段补一次 PUT）",
    )
    parser.add_argument(
        "--list-types", action="store_true", help="List available issue types for the project"
    )
    parser.add_argument(
        "--list-versions", action="store_true", help="List available versions for the project"
    )
    parser.add_argument("--discover-meta", action="store_true", help="Show issue types and required fields")
    parser.add_argument("--discover-fields", action="store_true", help="Find field ids by keyword")
    parser.add_argument("--discover-epics", action="store_true", help="List Epics usable with --epic")
    parser.add_argument("--discover-sprints", action="store_true", help="List sprints usable with --sprint")
    parser.add_argument("--discover-users", action="store_true", help="List assignable users")
    parser.add_argument(
        "--interview",
        action="store_true",
        help="Output the question list for a Story (4 required + 2 optional); creates nothing",
    )
    parser.add_argument("--term", help="Keyword for --discover-fields (e.g. epic / sprint / point)")
    parser.add_argument("--user-query", help="Keyword for --discover-users")
    parser.add_argument(
        "--output-format",
        default="json",
        choices=["json", "markdown"],
        help="Output format for previews and discovery (default: json)",
    )
    parser.add_argument("--output-file", help="Write output to a file (UTF-8, no BOM)")
    parser.add_argument("--output-dir", default=tempfile.gettempdir())
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    parser.add_argument("--json", action="store_true", help="Output the create result as JSON")

    args = parser.parse_args()

    if args.interview and args.simple:
        _fail(args, "--simple 与 --interview 互斥：--simple 是跳过完整流程，访谈是补齐信息。")

    issue_type = (args.issue_type or "Story").strip()

    # 没有 --project 时，访谈不需要凭据，直接输出静态问题集。
    if args.interview and not args.project:
        payload = interview.build_questions(issue_type)
        if args.output_format == "markdown":
            _emit(interview.render_markdown(payload), args)
        else:
            _emit(payload, args)
        return

    ok, config_error = validate_jira_config(JIRA_CONFIG)
    if not ok:
        print("Error: %s" % config_error)
        sys.exit(1)

    client = JiraClient(JIRA_CONFIG)

    if args.interview:
        payload = interview.build_questions(issue_type)
        try:
            meta = fetch_create_meta(client, args.project, issue_type)
            questions, field_error = interview.project_field_questions(meta, issue_type)
            payload["project_fields"] = questions
            if field_error:
                payload["project_fields_error"] = field_error
        except JiraError as exc:
            payload["project_fields_error"] = str(exc)
        if args.output_format == "markdown":
            _emit(interview.render_markdown(payload), args)
        else:
            _emit(payload, args)
        return

    try:
        if args.discover_fields:
            _emit(discover_fields(client, args.term), args)
            return
        if args.discover_meta:
            _discover_meta(args, client)
            return
        if args.discover_sprints:
            _emit(discover_sprints(client, _require_project(args, "--discover-sprints")), args)
            return
        if args.discover_epics:
            _emit(discover_epics(client, _require_project(args, "--discover-epics")), args)
            return
        if args.discover_users:
            _emit(
                discover_users(client, _require_project(args, "--discover-users"), args.user_query or ""),
                args,
            )
            return
        if args.list_types:
            list_issue_types(client, _require_project(args, "--list-types"))
            return
        if args.list_versions:
            versions = get_project_versions(client, _require_project(args, "--list-versions"))
            print("\nAvailable versions for project '%s':" % args.project)
            print("-" * 50)
            if versions:
                for version in versions:
                    released = "(released)" if version.get("released") else "(unreleased)"
                    print("  - %s %s" % (version.get("name"), released))
            else:
                print("  No versions found")
            print()
            return
    except JiraError as exc:
        _fail(args, str(exc))

    # Validate required arguments
    if not all([args.project, args.issue_type, args.summary, args.description or args.description_file]):
        parser.print_help()
        print("\nError: --project, --type, --summary, and --description/--description-file are required")
        sys.exit(1)

    args.labels = _parse_csv(args.labels)
    args.components = _parse_csv(args.components)
    try:
        args.description = read_description(args)
    except JiraError as exc:
        _fail(args, str(exc))

    # Legacy path: create immediately, no template.
    if not args.structured:
        if args.execute:
            print("[warn] --execute 只在 --structured 下有效；旧路径本来就会立即创建。", file=sys.stderr)
        print("Creating Jira issue in project '%s'..." % args.project)
        print()
        try:
            fields, _ = build_payload(client, args, args.issue_type)
            result = create_issue(
                client, fields, epic_key=args.epic, verify=not args.no_verify
            )
        except JiraError as exc:
            _fail(args, str(exc))
        _print_create_result(args, result, [])
        return

    # Structured path: lint, discover required fields, preview unless --execute.
    lint_errors, lint_warnings = lint_description(args.description, simple=args.simple)
    try:
        fields, extras = build_payload(client, args, args.issue_type)
        missing, meta_error = check_required_fields(
            client, args.project, args.issue_type, fields
        )
    except JiraError as exc:
        _fail(args, str(exc))

    url = "%s/rest/api/%s/issue" % (client.base_url, client.api_version)

    if not args.execute:
        preview = {
            "mode": "dry-run",
            "status": "preview",
            "created": False,
            "simple": bool(args.simple),
            "target": {"method": "POST", "url": url},
            "resolved": extras,
            "payload": {"fields": fields},
            "missing_required_fields": missing,
            "required_field_check_error": meta_error,
            "description_errors": lint_errors,
            "description_warnings": lint_warnings,
            "next_step": "确认无误后加 --execute 真正创建。",
        }
        if args.output_format == "markdown":
            _emit(
                _markdown_preview(
                    fields, extras, missing, meta_error, lint_errors, lint_warnings, args.simple, url
                ),
                args,
            )
        else:
            _emit(preview, args)
        return

    if missing:
        _fail(
            args,
            "必填字段缺失，已阻止创建：\n  "
            + "\n  ".join(missing)
            + "\n用 --field KEY=VALUE 补齐后重试。",
        )
    if lint_errors:
        _fail(
            args,
            "描述不符合撰写标准，已阻止创建：\n  "
            + "\n  ".join(lint_errors)
            + "\n\n处理方式：先向用户澄清或补齐必备小节；若本就是简单任务，加 --simple。",
        )
    for warning in lint_warnings:
        print("[warn] 描述质量: %s" % warning, file=sys.stderr)

    print("Creating Jira issue in project '%s'..." % args.project)
    print()
    try:
        result = create_issue(client, fields, epic_key=args.epic, verify=not args.no_verify)
    except JiraError as exc:
        _fail(args, str(exc))
    _print_create_result(args, result, lint_warnings)


if __name__ == "__main__":
    main()
