#!/usr/bin/env python3
"""Automated tests for the gerrit-review-code / gitlab-review-code tooling."""

import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _is_pending_or_number(value, allow_float=False):
    """Valid usage value: the string 'pending' or a non-negative number."""
    if value == "pending":
        return True
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value >= 0
    if allow_float and isinstance(value, float):
        return value >= 0
    return False


def test_cr_reports_artifacts():
    """Every saved cr_reports record must follow the SKILL.md Step 6.6 for its
    review system: gerrit_payload.json (gerrit_server) / gitlab_payload.json
    (gitlab_server) carry the review metrics (modified_lines, modified_files,
    tokens_consumed, acus_consumed, model_name) alongside the submitted review
    content, the *_response.json wraps the raw response (success + output), and
    the markdown report records the Server row + Diff Stat. The standalone
    general-review-code record (general_payload.json) has no submission step, so
    it carries no *_response.json and no <system>_server field -- its
    test-report.md only needs the Diff Stat row. The usage metrics may
    legitimately be the string 'pending' (session not yet flushed; Step 6.7
    backfill replaces them with real values) -- a non-pending numeric value must
    be a number, and model_name must be a non-empty string.
    """
    print("[test] cr_reports artifacts")
    reports_dir = REPO_ROOT / "scripts" / "cr_reports"
    records = [d for d in reports_dir.iterdir() if d.is_dir()] if reports_dir.is_dir() else []
    if not records:
        print(f"[test] cr_reports artifacts SKIPPED (no records under {reports_dir})")
        return

    for rec_dir in records:
        payload_path = None
        response_path = None
        server_key = None
        server_row = None
        is_general = False
        if (rec_dir / "gerrit_payload.json").is_file():
            payload_path = rec_dir / "gerrit_payload.json"
            response_path = rec_dir / "gerrit_response.json"
            server_key = "gerrit_server"
            server_row = "Gerrit Server"
        elif (rec_dir / "gitlab_payload.json").is_file():
            payload_path = rec_dir / "gitlab_payload.json"
            response_path = rec_dir / "gitlab_response.json"
            server_key = "gitlab_server"
            server_row = "GitLab Server"
        elif (rec_dir / "general_payload.json").is_file():
            payload_path = rec_dir / "general_payload.json"
            is_general = True
        else:
            assert False, f"{rec_dir} carries neither gerrit_payload.json nor gitlab_payload.json nor general_payload.json"
        if response_path is not None:
            assert response_path.is_file(), f"missing {response_path}"

        payload = json.loads(payload_path.read_text(encoding="utf-8"))

        if not is_general:
            response = json.loads(response_path.read_text(encoding="utf-8"))
            # *_response.json wraps the raw tool response (Step 7)
            assert "success" in response and "output" in response, f"{response_path} missing success/output"

        # *_payload.json: the submitted review content plus the review metrics
        # (SKILL.md Step 6/6.6): <system>_server, modified_lines,
        # modified_files, tokens_consumed, acus_consumed
        if not is_general:
            assert isinstance(payload.get(server_key), str) and payload[server_key].startswith("http"), \
                f"{payload_path} missing/bad {server_key}"
        assert isinstance(payload.get("modified_lines"), int) and payload["modified_lines"] >= 0, \
            f"{payload_path} modified_lines must be a non-negative int"
        assert isinstance(payload.get("modified_files"), int) and payload["modified_files"] >= 0, \
            f"{payload_path} modified_files must be a non-negative int"
        assert _is_pending_or_number(payload.get("tokens_consumed")), \
            f"{payload_path} tokens_consumed must be a non-negative int or 'pending'"
        assert _is_pending_or_number(payload.get("acus_consumed"), allow_float=True), \
            f"{payload_path} acus_consumed must be a non-negative number or 'pending'"
        model_name = payload.get("model_name")
        assert isinstance(model_name, str) and model_name, \
            f"{payload_path} model_name must be a non-empty string (or 'pending')"

        # markdown report records the Server row (submission skills) and the
        # Diff Stat row (all skills; general-review-code only requires Diff Stat)
        report = rec_dir.glob("test-report*.md")
        report = next(report, None)
        assert report is not None, f"missing test-report in {rec_dir}"
        text = report.read_text(encoding="utf-8")
        if not is_general:
            assert server_row in text, f"{report} missing {server_row} row"
        assert "Diff Stat" in text, f"{report} missing Diff Stat row"

    print("[test] cr_reports artifacts PASSED")


def test_gerrit_mcp_server_model_name():
    """The vendored gerrit-mcp-server must carry model_name from the submitted
    payload into the Gerrit overall comment's `## Review Metrics` section,
    bound together with tokens_consumed / acus_consumed (SKILL.md Step 6).

    Regression for the bug where the server dropped model_name from the
    submitted comment even though gerrit_payload.json recorded it (the
    gerrit 23689 submission): the MCP tool schema + handler (index.js) and the
    review-message renderer (gerrit-client.js) all have to pass model_name
    through, and version.txt must stay paired with the compiled RUNTIME_VERSION.
    """
    print("[test] gerrit-mcp-server model_name pass-through")
    server_dir = (
        REPO_ROOT / "mcp" / "gerrit_mcp" / "gerrit-mcp-server" / "dist"
    )
    assert server_dir.is_dir(), f"missing gerrit-mcp-server dist at {server_dir}"

    gerrit_client = (server_dir / "gerrit-client.js").read_text(encoding="utf-8")
    # 1. submitReviewMessage destructures model_name from the payload
    assert re.search(
        r"const \{[^}]*model_name[^}]*\}\s*=\s*reviewSubmitMessage",
        gerrit_client,
    ), "gerrit-client.js must destructure model_name from reviewSubmitMessage"
    # 2. the Review Metrics section renders it right after acus_consumed,
    #    before session_id (same ordering as SKILL.md Step 6)
    assert re.search(
        r"- acus_consumed: '\s*\+\s*\(acus_consumed \?\? ''\);\s*"
        r"\n\s*message \+= '\\n- model_name: '\s*\+\s*\(model_name \?\? ''\);",
        gerrit_client,
    ), "gerrit-client.js Review Metrics section must render '- model_name:'"

    index_js = (server_dir / "index.js").read_text(encoding="utf-8")
    # 3. the MCP tool handler passes model_name through to the client
    assert re.search(
        r"model_name:\s*args\.model_name", index_js
    ), "index.js handler must pass model_name: args.model_name"
    # 4. the tool inputSchema declares model_name
    assert re.search(
        r"model_name:\s*\{\s*type:\s*'string'", index_js
    ), "index.js inputSchema must declare the model_name property"

    # 5. types.d.ts declares model_name on ReviewSubmitMessage
    types_dts = (server_dir / "types.d.ts").read_text(encoding="utf-8")
    assert re.search(
        r"model_name\??:\s*string;", types_dts
    ), "types.d.ts ReviewSubmitMessage must declare model_name"

    # 6. version pairing: version.txt must match the compiled RUNTIME_VERSION
    #    (version.txt carries a UTF-8 BOM and CRLF line ending by convention)
    version_txt = (
        server_dir.parent / "version.txt"
    ).read_text(encoding="utf-8").strip("\ufeff\r\n \t")
    m = re.search(r"RUNTIME_VERSION\s*=\s*'([^']+)'", (server_dir / "version.js").read_text(encoding="utf-8"))
    assert m, "version.js must export RUNTIME_VERSION"
    assert m.group(1) == version_txt, (
        f"version.txt ({version_txt}) != RUNTIME_VERSION ({m.group(1)}); "
        "the server refuses to start on mismatch"
    )
    print("[test] gerrit-mcp-server model_name pass-through PASSED")


def test_gitlab_mcp_server_review_metrics():
    """The vendored gitlab-mcp-server must carry the review metrics from the
    submitted payload into the GitLab overall comment's `## Review Metrics`
    section, bound together with tokens_consumed / acus_consumed / model_name
    (SKILL.md Step 6), plus the per-issue `rule_id` lines and the top-level
    `rule_ids` array -- mirroring what gerrit-mcp-server does for Gerrit.

    Regression guard: the gitlab SKILL.md now submits the same metrics the
    gerrit skill pushes to Gerrit, so the MCP tool schema + handler (index.js)
    and the review-message renderer (gitlab-client.js) all have to pass them
    through, and the .windsurf overall-comment rule must declare the 7-key
    `## Review Metrics` format.
    """
    print("[test] gitlab-mcp-server review metrics pass-through")
    server_dir = (
        REPO_ROOT / "mcp" / "gitlab_mcp" / "gitlab-mcp-server" / "dist"
    )
    assert server_dir.is_dir(), f"missing gitlab-mcp-server dist at {server_dir}"

    gitlab_client = (server_dir / "gitlab-client.js").read_text(encoding="utf-8")
    # 1. submitReviewMessage destructures the metric fields from the payload
    for field in (
        "gitlab_server", "modified_lines", "modified_files", "tokens_consumed",
        "acus_consumed", "model_name", "session_id", "rule_ids",
    ):
        assert re.search(
            r"const \{[^}]*" + re.escape(field) + r"[^}]*\}\s*=\s*reviewSubmitMessage",
            gitlab_client,
        ), f"gitlab-client.js must destructure {field} from reviewSubmitMessage"
    # 2. the Review Metrics section renders rule_ids first, then the numeric
    #    metrics, then model_name right after acus_consumed, then session_id
    #    (same ordering as SKILL.md Step 6)
    assert re.search(
        r"- rule_ids: '\s*\+\s*JSON\.stringify\(rule_ids \?\? \[\]\);",
        gitlab_client,
    ), "gitlab-client.js Review Metrics section must render '- rule_ids:'"
    assert re.search(
        r"- acus_consumed: '\s*\+\s*\(acus_consumed \?\? ''\);\s*"
        r"\n\s*message \+= '\\n- model_name: '\s*\+\s*\(model_name \?\? ''\);",
        gitlab_client,
    ), "gitlab-client.js Review Metrics section must render '- model_name:'"
    assert re.search(
        r"- session_id: '\s*\+\s*\(session_id \?\? ''\);",
        gitlab_client,
    ), "gitlab-client.js Review Metrics section must render '- session_id:'"
    # 3. every issue in the Issue List carries a rule_id line after standard
    assert re.search(
        r"- standard: '\s*\+\s*issue\.standard;\s*"
        r"\n\s*message \+= '\\n\\t- rule_id: '\s*\+\s*\(issue\.rule_id \?\? ''\);",
        gitlab_client,
    ), "gitlab-client.js must render '- rule_id:' after '- standard:' per issue"

    index_js = (server_dir / "index.js").read_text(encoding="utf-8")
    # 4. the MCP tool handler passes the metric fields through to the client
    for field in (
        "gitlab_server", "modified_lines", "modified_files", "tokens_consumed",
        "acus_consumed", "model_name", "session_id", "rule_ids",
    ):
        assert re.search(
            re.escape(field) + r":\s*args\." + re.escape(field), index_js
        ), f"index.js handler must pass {field}: args.{field}"
    # 5. the tool inputSchema declares the metric fields
    assert re.search(
        r"model_name:\s*\{\s*type:\s*'string'", index_js
    ), "index.js inputSchema must declare the model_name property"
    assert re.search(
        r"rule_ids:\s*\{\s*type:\s*'array'", index_js
    ), "index.js inputSchema must declare the rule_ids property"
    assert re.search(
        r"modified_lines:\s*\{\s*type:\s*'number'", index_js
    ), "index.js inputSchema must declare the modified_lines property"
    assert re.search(
        r"tokens_consumed:\s*\{\s*type:\s*\['number',\s*'string'\]", index_js
    ), "index.js inputSchema must declare the tokens_consumed property"
    assert re.search(
        r"rule_id:\s*\{\s*type:\s*'string'", index_js
    ), "index.js inputSchema issues item must declare rule_id"

    # 6. types.d.ts declares the metric fields on ReviewSubmitMessage
    types_dts = (server_dir / "types.d.ts").read_text(encoding="utf-8")
    for field in (
        "gitlab_server", "modified_lines", "modified_files", "tokens_consumed",
        "acus_consumed", "model_name", "session_id", "rule_ids",
    ):
        assert re.search(
            re.escape(field) + r"\??:\s*(?:number|string|boolean|string\[\]|\|).*;",
            types_dts,
        ), f"types.d.ts ReviewSubmitMessage must declare {field}"
    assert re.search(
        r"rule_id\??:\s*string;", types_dts
    ), "types.d.ts InlineCommentRawData must declare rule_id"

    # 7. the .windsurf overall-comment rule declares the 7-key Review Metrics format
    rule_path = (
        REPO_ROOT / "mcp" / "gitlab_mcp" / ".windsurf" / "rules"
        / "sc-overall-comment-format-rule.md"
    )
    rule_text = rule_path.read_text(encoding="utf-8")
    for key in (
        "rule_ids", "modified_lines", "modified_files", "tokens_consumed",
        "acus_consumed", "model_name", "session_id",
    ):
        assert re.search(
            r"^## Review Metrics$", rule_text, re.M
        ) and f"- {key}:" in rule_text, (
            f"sc-overall-comment-format-rule.md Review Metrics section must list {key}"
        )
    print("[test] gitlab-mcp-server review metrics pass-through PASSED")


def test_source_path_commit_resolution():
    print("[test] source path commit resolution")
    source = "/home/mantic/Mantic/AI/volts_code/sercomm_virtual_olt"
    change_id = "I44e1b92689673bf2295f3d094b9b1214b314e14a"
    expected_hash = "c9cd7e3366425bba598109ac20f6904b9ace2d6d"

    # Environment-aware: this path only exists on the machine that owns that
    # checkout. Skip (not fail) elsewhere so the suite stays green.
    if not Path(source).is_dir():
        print(f"[test] source path commit resolution SKIPPED (checkout {source} not present)")
        return

    proc = subprocess.run(
        [
            "git", "-C", source,
            "log", "--all", f"--grep=Change-Id: {change_id}",
            "--format=%H", "-1",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    found = proc.stdout.strip()
    assert found == expected_hash, f"expected {expected_hash}, got {found}"
    print("[test] source path commit resolution PASSED")


def test_usage_metrics_helper():
    """usage_metrics.py must report real values when available and honest
    'pending' otherwise (SKILL.md Step 6: the CLI flushes ACUs at turn
    boundaries and tokens only at session close), and must report the session's
    model name (friendly name from the transcript, slug fallback) bound to the
    same session."""
    print("[test] usage metrics helper")
    scripts_dir = REPO_ROOT / "scripts"
    usage_spec = importlib.util.spec_from_file_location(
        "usage_metrics", scripts_dir / "usage_metrics.py"
    )
    usage = importlib.util.module_from_spec(usage_spec)
    usage_spec.loader.exec_module(usage)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        db_path = tmp / "sessions.db"
        transcripts = tmp / "transcripts"
        transcripts.mkdir()

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                working_directory TEXT,
                created_at INTEGER,
                last_activity_at INTEGER,
                title TEXT,
                metadata TEXT,
                model TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions (id, working_directory, created_at, last_activity_at, title, metadata, model) "
            "VALUES ('open-sess', ?, 1000, 1000, 'Review 1', ?, '')",
            (str(REPO_ROOT), json.dumps({"total_acu_cost": 0.0})),
        )
        conn.execute(
            "INSERT INTO sessions (id, working_directory, created_at, last_activity_at, title, metadata, model) "
            "VALUES ('closed-sess', ?, 900, 950, 'Review 2', ?, 'deepseek-v4-flash-high')",
            (str(REPO_ROOT), json.dumps({"total_acu_cost": 0.5})),
        )
        conn.execute(
            "INSERT INTO sessions (id, working_directory, created_at, last_activity_at, title, metadata, model) "
            "VALUES ('costed-open', ?, 800, 800, 'Review 3', ?, 'sonnet-4.5')",
            (str(REPO_ROOT), json.dumps({"total_acu_cost": 0.25})),
        )
        conn.execute(
            "INSERT INTO sessions (id, working_directory, created_at, last_activity_at, title, metadata, model) "
            "VALUES ('slug-only', ?, 700, 700, 'Review 4', ?, 'swe-1.6')",
            (str(REPO_ROOT), json.dumps({"total_acu_cost": 0.1})),
        )
        conn.commit()
        conn.close()

        # closed session transcript has final_metrics and the friendly model name
        (transcripts / "closed-sess.json").write_text(
            json.dumps({
                "agent": {"model_name": "DeepSeek V4 Flash High"},
                "final_metrics": {"total_prompt_tokens": 1000, "total_completion_tokens": 200},
            }),
            encoding="utf-8",
        )
        # open session with a friendly model name but no final_metrics yet
        (transcripts / "costed-open.json").write_text(
            json.dumps({"agent": {"model_name": "Sonnet 4.5"}, "steps": []}),
            encoding="utf-8",
        )
        # open sessions with a transcript that has neither final_metrics nor a model name
        for sid in ("open-sess", "slug-only"):
            (transcripts / f"{sid}.json").write_text(json.dumps({"steps": []}), encoding="utf-8")

        # Resolution: prefer the most recent session for the repo working dir.
        sid = usage.resolve_session_id(str(db_path), str(transcripts), cwd=str(REPO_ROOT))
        assert sid == "open-sess", f"resolve_session_id picked {sid}"
        # Explicit --session wins.
        sid = usage.resolve_session_id(str(db_path), str(transcripts), cwd=str(REPO_ROOT), prefer="closed-sess")
        assert sid == "closed-sess", f"prefer failed: {sid}"

        # Open session, unflushed 0.0 acus -> tokens pending, acus pending (not a real 0.0).
        # Its model is unflushed too (empty DB model, no transcript name) -> pending.
        m = usage.compute_metrics(str(db_path), str(transcripts), "open-sess")
        assert m["tokens_consumed"] == "pending" and m["tokens_state"] == "pending", m
        assert m["acus_consumed"] == "pending" and m["acus_state"] == "pending", m
        assert m["model_name"] == "pending" and m["model_state"] == "pending", m

        # Open session with a real acu cost -> tokens pending, acus real, friendly model name.
        m = usage.compute_metrics(str(db_path), str(transcripts), "costed-open")
        assert m["tokens_consumed"] == "pending", m
        assert m["acus_consumed"] == 0.25 and m["acus_state"] == "real", m
        assert m["model_name"] == "Sonnet 4.5" and m["model_state"] == "real", m

        # Closed session -> both real; tokens = prompt + completion; friendly model name.
        m = usage.compute_metrics(str(db_path), str(transcripts), "closed-sess")
        assert m["tokens_consumed"] == 1200 and m["tokens_state"] == "real", m
        assert m["acus_consumed"] == 0.5 and m["acus_state"] == "real", m
        assert m["model_name"] == "DeepSeek V4 Flash High" and m["model_state"] == "real", m

        # No transcript model name -> fall back to the sessions.model slug.
        m = usage.compute_metrics(str(db_path), str(transcripts), "slug-only")
        assert m["model_name"] == "swe-1.6" and m["model_state"] == "real", m

        # Unknown session id -> nothing to read, both pending (honest).
        m = usage.compute_metrics(str(db_path), str(transcripts), "ghost-sess")
        assert m["tokens_consumed"] == "pending" and m["tokens_state"] == "pending", m
        assert m["acus_consumed"] == "pending" and m["acus_state"] == "pending", m
        assert m["model_name"] == "pending" and m["model_state"] == "pending", m
        # No session resolved at all -> n/a states.
        m = usage.compute_metrics(str(db_path), str(transcripts), None)
        assert m["tokens_consumed"] == "pending" and m["tokens_state"] == "n/a", m
        assert m["acus_consumed"] == "pending" and m["acus_state"] == "n/a", m
        assert m["model_name"] == "pending" and m["model_state"] == "n/a", m

    print("[test] usage metrics helper PASSED")


def test_gitlab_skill_definition():
    """The gitlab-review-code skill must exist and reference exactly the MCP
    tools the vendored gitlab-mcp-server registers (Step 0.1 of the skill)."""
    print("[test] gitlab-review-code skill definition")
    skill_path = REPO_ROOT / "skills" / "gitlab-review-code" / "SKILL.md"
    assert skill_path.is_file(), f"missing skill at {skill_path}"
    text = skill_path.read_text(encoding="utf-8")

    assert re.search(r"^name:\s*gitlab-review-code\s*$", text, re.M), \
        "frontmatter name must be gitlab-review-code"
    for tool in (
        "gitlab_check_merge_request_review_need",
        "gitlab_get_file_diff_segment",
        "gitlab_check_changed_files_symbol_match",
        "gitlab_submit_review_message",
    ):
        assert tool in text, f"SKILL.md must reference {tool}"

    # the skill must read the rule files from the vendored gitlab .windsurf
    rules_dir = REPO_ROOT / "mcp" / "gitlab_mcp" / ".windsurf" / "rules"
    assert rules_dir.is_dir(), f"missing gitlab rules dir {rules_dir}"
    for rule in (
        "sc-code-check-cwe-top25-rule.md",
        "sc-code-check-owasp-top10-rule.md",
        "sc-code-check-sercomm-rule.md",
        "sc-code-check-reserved-rule.md",
        "sc-inline-comment-format-rule.md",
        "sc-overall-comment-format-rule.md",
    ):
        assert (rules_dir / rule).is_file(), f"missing rule file {rule}"
    print("[test] gitlab-review-code skill definition PASSED")


def test_gitlab_mcp_server_registration():
    """The vendored gitlab-mcp-server must register the four review tools
    actually used by the skill, version.txt must pair with the compiled
    RUNTIME_VERSION, and .devin/mcp_config.json must declare the server."""
    print("[test] gitlab-mcp-server registration")
    server_dist = REPO_ROOT / "mcp" / "gitlab_mcp" / "gitlab-mcp-server" / "dist"
    assert server_dist.is_dir(), f"missing gitlab-mcp-server dist at {server_dist}"

    index_js = (server_dist / "index.js").read_text(encoding="utf-8")
    for tool in (
        "gitlab_check_merge_request_review_need",
        "gitlab_get_file_diff_segment",
        "gitlab_check_changed_files_symbol_match",
        "gitlab_submit_review_message",
    ):
        assert re.search(
            rf"name:\s*'{tool}'", index_js
        ), f"gitlab-mcp-server must register {tool}"

    # version pairing: version.txt must match the compiled RUNTIME_VERSION
    version_txt = (
        server_dist.parent / "version.txt"
    ).read_text(encoding="utf-8").strip("\ufeff\r\n \t")
    m = re.search(r"RUNTIME_VERSION\s*=\s*'([^']+)'", (server_dist / "version.js").read_text(encoding="utf-8"))
    assert m, "gitlab version.js must export RUNTIME_VERSION"
    assert m.group(1) == version_txt, (
        f"gitlab version.txt ({version_txt}) != RUNTIME_VERSION ({m.group(1)}); "
        "the server refuses to start on mismatch"
    )

    # the project MCP config declares the server (committed template, no secrets)
    mcp_config = json.loads((REPO_ROOT / "config" / "devin" / "mcp_config.json").read_text(encoding="utf-8"))
    gitlab_cfg = mcp_config["mcpServers"].get("gitlab-mcp-server")
    assert gitlab_cfg is not None, "mcp_config.json must declare gitlab-mcp-server"
    assert gitlab_cfg["args"][0] == "mcp/gitlab_mcp/gitlab-mcp-server/dist/index.js"
    assert gitlab_cfg["env"].get("GITLAB_API_URL", "").startswith("http")
    assert gitlab_cfg["env"].get("GITLAB_TOKEN"), "gitlab-mcp-server must declare GITLAB_TOKEN"
    print("[test] gitlab-mcp-server registration PASSED")


def test_backfill_gitlab_payload():
    """backfill_review_usage.py must detect gitlab_payload.json records and
    backfill them the same way as gerrit records (Step 6.7 of the skill)."""
    print("[test] backfill gitlab payload")
    scripts_dir = REPO_ROOT / "scripts"
    backfill_spec = importlib.util.spec_from_file_location(
        "backfill_review_usage", scripts_dir / "backfill_review_usage.py"
    )
    backfill = importlib.util.module_from_spec(backfill_spec)
    backfill_spec.loader.exec_module(backfill)

    with tempfile.TemporaryDirectory() as tmp:
        record_dir = Path(tmp) / "ai-tools_ai-code-review-skill_123"
        record_dir.mkdir()
        payload = {
            "project_id": "ai-tools/ai-code-review-skill",
            "merge_request_iid": 123,
            "gitlab_server": "http://172.21.1.202:8090",
            "modified_lines": 42,
            "modified_files": 3,
            "tokens_consumed": "pending",
            "acus_consumed": "pending",
            "model_name": "pending",
        }
        (record_dir / "gitlab_payload.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

        # payload detection prefers the gitlab payload when present
        name, path = backfill.find_payload_file(record_dir)
        assert name == "gitlab_payload.json" and path.name == "gitlab_payload.json"
        kind, identifier = backfill.payload_identifier(payload, name)
        assert kind == "gitlab" and identifier == 123

        # backfilling records the owning session (a ghost one here -> all
        # metrics stay pending, only session_id is written back)
        result = backfill.backfill_review(record_dir, force_session="ghost-sess")
        assert result["kind"] == "gitlab" and result["identifier"] == 123, result
        assert result.get("session_id") == "ghost-sess", result
        saved = json.loads(
            (record_dir / "gitlab_payload.json").read_text(encoding="utf-8")
        )
        assert saved["session_id"] == "ghost-sess"
        assert saved["tokens_consumed"] == "pending" and saved["acus_consumed"] == "pending"

        # gerrit payloads still detected as gerrit
        record_dir2 = Path(tmp) / "proj_23608"
        record_dir2.mkdir()
        (record_dir2 / "gerrit_payload.json").write_text(
            json.dumps({"change_number": 23608, "gerrit_server": "http://x"}), encoding="utf-8"
        )
        name2, _ = backfill.find_payload_file(record_dir2)
        kind2, identifier2 = backfill.payload_identifier(
            json.loads((record_dir2 / "gerrit_payload.json").read_text(encoding="utf-8")), name2
        )
        assert kind2 == "gerrit" and identifier2 == 23608
    print("[test] backfill gitlab payload PASSED")


def test_project_config_permissions():
    """config/devin/config.json (the committed Devin CLI project-config template,
    copied to .devin/config.json during install) must auto-approve every tool of
    gerrit-mcp-server and gitlab-mcp-server. Project-level config.json only
    supports permissions / read_config_from / hooks, so only the permissions key
    may be present, and the mcp__<server>__* patterns must match the server names
    declared in config/devin/mcp_config.json. The .devin/ copy is a local install
    artifact and must stay gitignored (canonical file lives in config/devin/)."""
    print("[test] project config permissions")
    cfg_path = REPO_ROOT / "config" / "devin" / "config.json"
    assert cfg_path.is_file(), f"missing committed template at {cfg_path}"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    # only the permissions key is legal in a project-level config.json
    assert set(cfg.keys()) <= {"permissions", "read_config_from", "hooks"}, (
        f"project-level config.json supports only permissions/read_config_from/hooks, got {sorted(cfg.keys())}"
    )
    assert "permissions" in cfg, "config.json must define permissions"

    allow = cfg["permissions"].get("allow", [])
    assert "mcp__gerrit-mcp-server__*" in allow, "missing mcp__gerrit-mcp-server__* allow rule"
    assert "mcp__gitlab-mcp-server__*" in allow, "missing mcp__gitlab-mcp-server__* allow rule"

    # every allowed MCP server must actually be declared in the MCP template
    mcp_config = json.loads((REPO_ROOT / "config" / "devin" / "mcp_config.json").read_text(encoding="utf-8"))
    for pattern in allow:
        m = re.fullmatch(r"mcp__(.+)__\*", pattern)
        assert m, f"unexpected permission pattern {pattern!r}"
        assert m.group(1) in mcp_config["mcpServers"], (
            f"permission pattern {pattern} references unknown server {m.group(1)!r}"
        )

    # the local install copy must be gitignored (canonical file stays committed)
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".devin/config.json" in gitignore, ".devin/config.json must be gitignored"
    print("[test] project config permissions PASSED")


def main():
    tests = [
        test_cr_reports_artifacts,
        test_source_path_commit_resolution,
        test_usage_metrics_helper,
        test_gerrit_mcp_server_model_name,
        test_gitlab_mcp_server_review_metrics,
        test_gitlab_skill_definition,
        test_gitlab_mcp_server_registration,
        test_backfill_gitlab_payload,
        test_project_config_permissions,
    ]
    failed = []
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"[test] {t.__name__} FAILED: {e}")
            failed.append(t.__name__)
    if failed:
        print(f"\n{len(failed)} test(s) failed: {failed}")
        sys.exit(1)
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
