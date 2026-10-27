#!/usr/bin/env bash
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

# Deterministic upstream-migration test in a throwaway HOME.
set -euo pipefail

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/jira-worklog-migrate.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP/home"
unset APPDATA || true
mkdir -p "$HOME/.config/devin/skills"

fail() { echo "[FAIL] $*" >&2; exit 1; }
pass() { echo "[PASS] $*"; }

# 造一个没有 VERSION/SOURCE 的上游旧版目录 / create a legacy dir without provenance
legacy_skill() {
    local dir="$1" name="$2"
    mkdir -p "$dir/scripts"
    printf -- '---\nname: %s\ndescription: legacy upstream copy\n---\n' "$name" > "$dir/SKILL.md"
    printf '# legacy\n' > "$dir/scripts/legacy.py"
}

for s in jira-manage jira-create-worklog jira-tag-session; do
    legacy_skill "$HOME/.config/devin/skills/$s" "$s"
done

cat > "$HOME/.config/devin/AGENTS.md" <<'EOF'
# Global rules

## Session Jira Issue Tagging

Before doing any real work in a new Devin CLI session, you MUST invoke the
`jira-tag-session` skill via the skill tool to bind this session to a Jira
issue key for worklog generation. The only exception is the worklog-generation
session itself (first prompt invokes `/jira-create-worklog` or starts with
`# Skill Worklog`).

## Keep This Rule

This paragraph must survive the migration.
EOF

# 1) check 在迁移前应报 [MIGRATE] 并返回 3
set +e
out="$(bash "$PACK_DIR/install.sh" check 2>&1)"
rc=$?
set -e
[[ "$rc" == "3" ]] || fail "check before install: expected exit 3, got $rc"
grep -q '\[MIGRATE\]' <<<"$out" || fail "check before install: missing [MIGRATE]"
pass "check reports legacy installs with exit 3"

# 2) install 自动迁移并装新版
bash "$PACK_DIR/install.sh" >/dev/null
for s in jira-manage jira-create-worklog jira-tag-session; do
    [[ -f "$HOME/.agents/skills/$s/SKILL.md" ]] || fail "missing new install: $s"
    [[ -f "$HOME/.agents/skills/$s/VERSION" ]] || fail "missing VERSION: $s"
    [[ -L "$HOME/.config/devin/skills/$s" ]] || fail "missing symlink: $s"
    [[ "$(readlink "$HOME/.config/devin/skills/$s")" == "$HOME/.agents/skills/$s" ]] || fail "wrong symlink: $s"
done
pass "legacy dirs replaced with new install + symlinks"

# 3) 三个旧目录都进了备份
backup_count="$(find "$HOME/.agents/backups/jira-worklog" -name SKILL.md | wc -l | tr -d ' ')"
[[ "$backup_count" == "3" ]] || fail "expected 3 backed-up SKILL.md, got $backup_count"
pass "three legacy dirs backed up"

# 4) AGENTS.md 的强制 tagging 节被删，其它内容保留
grep -q 'Session Jira Issue Tagging' "$HOME/.config/devin/AGENTS.md" && fail "AGENTS.md still has the removed section"
grep -q '## Keep This Rule' "$HOME/.config/devin/AGENTS.md" || fail "AGENTS.md lost the unrelated section"
grep -q 'This paragraph must survive' "$HOME/.config/devin/AGENTS.md" || fail "AGENTS.md lost unrelated body"
pass "AGENTS.md section removed, unrelated content preserved"

# 5) AGENTS.md 改前有整文件备份
agents_backup="$(find "$HOME/.agents/backups/jira-worklog" -name 'AGENTS.md.*' | head -n 1)"
[[ -n "$agents_backup" ]] || fail "missing AGENTS.md backup"
grep -q 'Session Jira Issue Tagging' "$agents_backup" || fail "AGENTS.md backup lost the section"
pass "AGENTS.md backed up before edit"

# 6) 迁移后 check 应通过
bash "$PACK_DIR/install.sh" check >/dev/null || fail "check after install failed"
pass "check passes after migration"

# 7) 幂等：第二次装不产生新备份
before="$(find "$HOME/.agents/backups/jira-worklog" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
bash "$PACK_DIR/install.sh" >/dev/null
after="$(find "$HOME/.agents/backups/jira-worklog" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
[[ "$before" == "$after" ]] || fail "second install created a new backup dir"
pass "second install is idempotent"

# 8) 负例：带 VERSION/SOURCE 的真目录不算上游旧版
HOME2="$TMP/home2"
mkdir -p "$HOME2/.config/devin/skills/jira-manage"
printf -- '---\nname: jira-manage\n---\n' > "$HOME2/.config/devin/skills/jira-manage/SKILL.md"
printf '9.9.9\n' > "$HOME2/.config/devin/skills/jira-manage/VERSION"
printf 'repo: x\n' > "$HOME2/.config/devin/skills/jira-manage/SOURCE"
HOME="$HOME2" bash "$PACK_DIR/install.sh" >/dev/null
[[ ! -d "$HOME2/.agents/backups/jira-worklog" ]] || fail "dir with provenance was backed up as legacy"
pass "dir with provenance is not treated as legacy"

# 9) 负例：front-matter name 不匹配的真目录不动
HOME3="$TMP/home3"
mkdir -p "$HOME3/.config/devin/skills/jira-manage"
printf -- '---\nname: someone-elses-skill\n---\n' > "$HOME3/.config/devin/skills/jira-manage/SKILL.md"
HOME="$HOME3" bash "$PACK_DIR/install.sh" >/dev/null
[[ -f "$HOME3/.config/devin/skills/jira-manage/SKILL.md" ]] || fail "unrelated skill was migrated"
[[ ! -d "$HOME3/.agents/backups/jira-worklog" ]] || fail "unrelated skill was backed up"
pass "dir with a different name is not migrated"

# 10) 项目级：旧副本先备份再安装
REPO="$TMP/repo"
mkdir -p "$REPO/.devin/skills/jira-manage"
git -C "$REPO" init -q
printf -- '---\nname: jira-manage\n---\n' > "$REPO/.devin/skills/jira-manage/SKILL.md"
HOME="$TMP/home" bash "$PACK_DIR/install.sh" --project "$REPO" >/dev/null
[[ -f "$REPO/.devin/skills/jira-manage/VERSION" ]] || fail "project install missing VERSION"
project_backup="$(find "$HOME/.agents/backups/jira-worklog" -path '*project-*' -name SKILL.md | head -n 1)"
[[ -n "$project_backup" ]] || fail "project legacy dir was not backed up"
pass "project-level legacy dir backed up before install"

# 11) dry-run：什么都不改
HOME4="$TMP/home4"
mkdir -p "$HOME4/.config/devin/skills/jira-manage"
printf -- '---\nname: jira-manage\n---\n' > "$HOME4/.config/devin/skills/jira-manage/SKILL.md"
HOME="$HOME4" bash "$PACK_DIR/install.sh" --dry-run >/dev/null
[[ -f "$HOME4/.config/devin/skills/jira-manage/SKILL.md" ]] || fail "dry-run moved the legacy dir"
[[ ! -d "$HOME4/.agents/backups" ]] || fail "dry-run created a backup dir"
pass "dry-run changes nothing"

# 12) CRLF 的 AGENTS.md：节被删、其它内容保留、行尾不变
HOME5="$TMP/home5"
mkdir -p "$HOME5/.config/devin"
printf '## Session Jira Issue Tagging\r\n\r\nMUST invoke.\r\n\r\n## Keep\r\n\r\nkeep me\r\n' > "$HOME5/.config/devin/AGENTS.md"
HOME="$HOME5" bash "$PACK_DIR/install.sh" >/dev/null
grep -q 'Session Jira Issue Tagging' "$HOME5/.config/devin/AGENTS.md" && fail "CRLF: section not removed"
grep -q '## Keep' "$HOME5/.config/devin/AGENTS.md" || fail "CRLF: unrelated section lost"
python3 - "$HOME5/.config/devin/AGENTS.md" <<'PY' || fail "CRLF: line endings changed"
import sys
data = open(sys.argv[1], "rb").read()
assert b"\r\n" in data, "no CRLF left"
assert b"\n" not in data.replace(b"\r\n", b""), "bare LF introduced"
PY
pass "CRLF AGENTS.md handled without changing line endings"

# 13) 节后出现 H1：只删 tagging 节，后面的内容必须保留
HOME6="$TMP/home6"
mkdir -p "$HOME6/.config/devin"
printf '## Session Jira Issue Tagging\n\nMUST invoke.\n\n# Other Rules\n\nkeep me\n' > "$HOME6/.config/devin/AGENTS.md"
HOME="$HOME6" bash "$PACK_DIR/install.sh" >/dev/null
grep -q 'Session Jira Issue Tagging' "$HOME6/.config/devin/AGENTS.md" && fail "H1: section not removed"
grep -q '# Other Rules' "$HOME6/.config/devin/AGENTS.md" || fail "H1: unrelated H1 lost"
grep -q 'keep me' "$HOME6/.config/devin/AGENTS.md" || fail "H1: unrelated body lost"
pass "H1 after the section is preserved"

echo "[PASS] migration tests"
