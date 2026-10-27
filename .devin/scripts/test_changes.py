#!/usr/bin/env python3
"""Automated tests for the gerrit-review-code tooling, in the installed layout.

The skill is installed into `.devin/` (`.devin/skills/gerrit-review-code/`,
`.devin/mcp/gerrit_mcp/`, `.devin/scripts/`, `.devin/mcp_config.json`,
`.devin/config.json`), so every path below is resolved relative to the project
root through `.devin/`. The gitlab half of the upstream suite is not shipped here:
this entry vendors only the gerrit MCP server.
"""

import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


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
    reports_dir = REPO_ROOT / ".devin" / "scripts" / "cr_reports"
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
        REPO_ROOT / ".devin" / "mcp" / "gerrit_mcp" / "gerrit-mcp-server" / "dist"
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


def test_source_path_default_cwd():
    """SKILL.md Step 1.3 must adopt the working directory as SOURCE_PATH when a
    remote URL's project path equals <PROJECT_NAME> (exact) or ends with it
    (namespaced), or -- more weakly -- when only the last path segment matches
    (tail-only); otherwise it stays unset."""
    print("[test] source path default cwd")

    def resolve(cwd, project):
        """Mirror SKILL.md Step 1.3: return (root or None, origin, match)."""
        top = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if top.returncode != 0:
            return None, "none", "none"
        root = top.stdout.strip()
        want = project.rsplit("/", 1)[-1]
        urls = []
        for line in subprocess.run(
            ["git", "-C", root, "remote", "-v"],
            capture_output=True,
            text=True,
        ).stdout.splitlines():
            url = line.split()[1]
            urls.append(url[:-4] if url.endswith(".git") else url)

        def url_path(url):
            """Project path inside a remote URL, URI or scp form."""
            if "://" in url:
                rest = url.split("://", 1)[1]
                return rest.split("/", 1)[1] if "/" in rest else ""
            return url.rsplit(":", 1)[-1]

        best = None
        for url in urls:
            path = url_path(url)
            if path == project:
                return root, "cwd", "exact"
            if path.endswith("/" + project):
                best = "namespaced"
        if best:
            return root, "cwd", best
        if Path(root).name == want or any(
            url_path(url).rsplit("/", 1)[-1] == want for url in urls
        ):
            return root, "cwd", "tail-only"
        return None, "none", "none"

    with tempfile.TemporaryDirectory() as tmp:
        def real(path):
            """Absolute path with symlinks resolved, as git reports it."""
            return str(Path(path).resolve())

        same = Path(tmp) / "ai-toolbox"
        same.mkdir()
        subprocess.run(["git", "-C", str(same), "init", "-q"], check=True)
        assert resolve(str(same), "ai-toolbox") == (real(same), "cwd", "tail-only"), \
            "a directory named after the project is only a tail match"
        assert resolve(str(same), "other-project") == (None, "none", "none"), \
            "a different directory name must not be adopted"
        assert resolve(tmp, "ai-toolbox") == (None, "none", "none"), \
            "a non-git directory must not be adopted"

        by_remote = Path(tmp) / "whatever"
        by_remote.mkdir()
        subprocess.run(["git", "-C", str(by_remote), "init", "-q"], check=True)
        subprocess.run(
            [
                "git", "-C", str(by_remote), "remote", "add", "gerrit",
                "ssh://user@host:29418/ansc-cas/ai-toolbox",
            ],
            check=True,
        )
        assert resolve(str(by_remote), "ai-toolbox") == (real(by_remote), "cwd", "namespaced"), \
            "an ssh:// remote whose path ends with the project is a namespaced match"
        assert resolve(str(by_remote), "group/ai-toolbox") == (real(by_remote), "cwd", "tail-only"), \
            "a nested project name that only shares the last segment is a tail match"

        scp = Path(tmp) / "scp-remote"
        scp.mkdir()
        subprocess.run(["git", "-C", str(scp), "init", "-q"], check=True)
        subprocess.run(
            [
                "git", "-C", str(scp), "remote", "add", "origin",
                "git@host:group/ai-toolbox.git",
            ],
            check=True,
        )
        assert resolve(str(scp), "ai-toolbox") == (real(scp), "cwd", "namespaced"), \
            "an scp-style remote with a .git suffix is a namespaced match"

        # GR-002: two projects sharing a last segment must not be confused, and
        # the ambiguity must surface as a tail-only match.
        ambiguous = Path(tmp) / "ambiguous"
        ambiguous.mkdir()
        subprocess.run(["git", "-C", str(ambiguous), "init", "-q"], check=True)
        subprocess.run(
            [
                "git", "-C", str(ambiguous), "remote", "add", "origin",
                "git@host:teamB/utils.git",
            ],
            check=True,
        )
        assert resolve(str(ambiguous), "teamA/utils") == (real(ambiguous), "cwd", "tail-only"), \
            "a same-tail project must be flagged as tail-only"
        subprocess.run(
            [
                "git", "-C", str(ambiguous), "remote", "add", "gerrit",
                "git@host:teamA/utils.git",
            ],
            check=True,
        )
        assert resolve(str(ambiguous), "teamA/utils") == (real(ambiguous), "cwd", "exact"), \
            "a matching project path must win over a same-tail sibling"

        exact = Path(tmp) / "exact-remote"
        exact.mkdir()
        subprocess.run(["git", "-C", str(exact), "init", "-q"], check=True)
        subprocess.run(
            [
                "git", "-C", str(exact), "remote", "add", "gerrit",
                "ssh://user@host:29418/ai-toolbox",
            ],
            check=True,
        )
        assert resolve(str(exact), "ai-toolbox") == (real(exact), "cwd", "exact"), \
            "a remote path equal to the project is an exact match"

    print("[test] source path default cwd PASSED")


def test_usage_metrics_helper():
    """usage_metrics.py must report real values when available and honest
    'pending' otherwise (SKILL.md Step 6: the CLI flushes ACUs at turn
    boundaries and tokens only at session close), and must report the session's
    model name (friendly name from the transcript, slug fallback) bound to the
    same session."""
    print("[test] usage metrics helper")
    scripts_dir = REPO_ROOT / ".devin" / "scripts"
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





def test_project_config_permissions():
    """.devin/config.json (installed from the entry's config/devin/config.json)
    must auto-approve every tool of gerrit-mcp-server. Project-level config.json
    only supports permissions / read_config_from / hooks, so only the permissions
    key may be present, and the mcp__<server>__* patterns must match the server
    names declared in .devin/mcp_config.json. Unlike the upstream repo (which
    keeps the canonical files in config/devin/ and gitignores .devin/), this
    install keeps .devin/config.json and .devin/mcp_config.json tracked so a
    teammate gets them with a plain `git pull`; only the personal override
    .devin/mcp_config.local.json -- which holds the real password -- must stay
    gitignored."""
    print("[test] project config permissions")
    cfg_path = REPO_ROOT / ".devin" / "config.json"
    assert cfg_path.is_file(), f"missing committed template at {cfg_path}"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    # only the permissions key is legal in a project-level config.json
    assert set(cfg.keys()) <= {"permissions", "read_config_from", "hooks"}, (
        f"project-level config.json supports only permissions/read_config_from/hooks, got {sorted(cfg.keys())}"
    )
    assert "permissions" in cfg, "config.json must define permissions"

    allow = cfg["permissions"].get("allow", [])
    assert "mcp__gerrit-mcp-server__*" in allow, "missing mcp__gerrit-mcp-server__* allow rule"

    # every allowed MCP server must actually be declared in the MCP template
    mcp_config = json.loads((REPO_ROOT / ".devin" / "mcp_config.json").read_text(encoding="utf-8"))
    for pattern in allow:
        m = re.fullmatch(r"mcp__(.+)__\*", pattern)
        assert m, f"unexpected permission pattern {pattern!r}"
        assert m.group(1) in mcp_config["mcpServers"], (
            f"permission pattern {pattern} references unknown server {m.group(1)!r}"
        )

    # the personal override (real password) must be ignored by git; the
    # tracked template / config.json are deliberately NOT ignored.
    local_cfg = REPO_ROOT / ".devin" / "mcp_config.local.json"
    if (REPO_ROOT / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(local_cfg)],
            capture_output=True,
        )
        assert proc.returncode == 0, (
            f"{local_cfg} must be gitignored -- add it to .gitignore "
            "(install.sh does this automatically)"
        )
    else:
        print("[test] project config permissions SKIPPED gitignore check (not a git repo)")
    print("[test] project config permissions PASSED")


def test_current_patch_set_selection():
    """SKILL.md Step 1.3 must ignore non-integer change refs (`meta`) and pick
    the numerically highest patch set, not the lexicographically highest."""
    print("[test] current patch set selection")

    def select(ls_remote_output):
        """Return (sha, patch_set) for the highest numeric patch set, or None."""
        best = None
        for line in ls_remote_output.splitlines():
            sha, _, ref = line.partition("\t")
            tail = ref.rsplit("/", 1)[-1]
            if not tail.isdigit():
                continue
            if best is None or int(tail) > best[1]:
                best = (sha, int(tail))
        return best

    with tempfile.TemporaryDirectory() as tmp:
        bare = Path(tmp) / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        work = Path(tmp) / "work"
        work.mkdir()
        subprocess.run(["git", "-C", str(work), "init", "-q"], check=True)
        subprocess.run(
            [
                "git", "-C", str(work), "-c", "user.email=x@x", "-c", "user.name=x",
                "commit", "-q", "--allow-empty", "-m", "base",
            ],
            check=True,
        )
        for patch_set in ("1", "2", "9", "10", "meta"):
            subprocess.run(
                [
                    "git", "-C", str(work), "push", "-q", str(bare),
                    f"HEAD:refs/changes/15/24215/{patch_set}",
                ],
                check=True,
            )
        out = subprocess.run(
            ["git", "ls-remote", str(bare), "refs/changes/*/24215/*"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "24215/meta" in out, "the meta ref must be visible for this test to mean anything"
        sha, patch_set = select(out)
        assert patch_set == 10, f"10 must outrank 9 (numeric, not lexicographic), got {patch_set}"
        assert len(sha) == 40, f"expected a full commit SHA, got {sha!r}"

    print("[test] current patch set selection PASSED")


def test_docs_invocation_matches_skill():
    """docs/gerrit-review-code.md must quote the canonical invocation from
    SKILL.md's `argument-hint`.

    Both files are generated from the upstream snapshot plus patches, so a patch
    that updates SKILL.md without the docs leaves them contradicting each other.
    Whitespace is normalised on both sides because the docs wrap the invocation
    across lines."""
    print("[test] docs invocation matches SKILL.md")
    skill_dir = REPO_ROOT / ".devin" / "skills" / "gerrit-review-code"
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    docs = (skill_dir / "docs" / "gerrit-review-code.md").read_text(encoding="utf-8")
    match = re.search(r'^argument-hint:[ \t]*"([^"]+)"', skill, re.MULTILINE)
    assert match, "SKILL.md front-matter has no argument-hint"
    hint = " ".join(match.group(1).split())
    assert hint in " ".join(docs.split()), (
        f"docs/gerrit-review-code.md does not quote the canonical invocation {hint!r}"
    )
    print("[test] docs invocation matches SKILL.md PASSED")


def test_step7_omits_raw_json_from_conversation():
    """SKILL.md Step 7 must return a human-readable structured summary in the
    conversation without dumping the raw gerrit_submit_review_message JSON
    blocks, while Step 6.6 keeps the raw JSON blocks inside the saved
    test-report-<CHANGE_NUMBER>.md file for backfill_review_usage.py."""
    print("[test] step 7 omits raw JSON from conversation")
    skill_dir = REPO_ROOT / ".devin" / "skills" / "gerrit-review-code"
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    step7 = skill.split("### Step 7) Return status", 1)[1].split("## Expected Artifacts", 1)[0]
    assert "Always return a markdown summary **and** two fenced JSON blocks" not in step7, (
        "Step 7 must not require returning raw JSON blocks in the conversation"
    )
    assert "Conversation output (human-readable summary only — NO raw JSON blocks)" in step7, (
        "Step 7 must explicitly forbid raw JSON blocks in conversation output"
    )
    print("[test] step 7 omits raw JSON from conversation PASSED")


def main():
    tests = [
        test_cr_reports_artifacts,
        test_source_path_commit_resolution,
        test_source_path_default_cwd,
        test_current_patch_set_selection,
        test_usage_metrics_helper,
        test_gerrit_mcp_server_model_name,
        test_project_config_permissions,
        test_docs_invocation_matches_skill,
        test_step7_omits_raw_json_from_conversation,
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
