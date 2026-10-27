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

# Deterministic install/check/uninstall test in a throwaway HOME.
set -euo pipefail

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/jira-worklog-install.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP/home"
mkdir -p "$HOME/.config/devin/skills"

fail() { echo "[FAIL] $*" >&2; exit 1; }
pass() { echo "[PASS] $*"; }

# 1) user-level install
bash "$PACK_DIR/install.sh" >/dev/null
for skill in jira-manage jira-create-worklog jira-tag-session; do
    [[ -f "$HOME/.agents/skills/$skill/SKILL.md" ]] || fail "missing user install: $skill"
    [[ -L "$HOME/.config/devin/skills/$skill" ]] || fail "missing symlink: $skill"
done
pass "user-level install creates three skills and symlinks"

# 2) check
bash "$PACK_DIR/install.sh" check >/dev/null || fail "user-level check failed"
pass "user-level check passes"

# 3) uninstall
bash "$PACK_DIR/install.sh" uninstall --yes >/dev/null
for skill in jira-manage jira-create-worklog jira-tag-session; do
    [[ ! -e "$HOME/.agents/skills/$skill" ]] || fail "user uninstall left: $skill"
    [[ ! -L "$HOME/.config/devin/skills/$skill" ]] || fail "user uninstall left symlink: $skill"
done
pass "user-level uninstall removes skills and symlinks"

# 4) project-level install (emits [WARN] recommending user-level install)
REPO="$TMP/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q
proj_out="$(bash "$PACK_DIR/install.sh" --project "$REPO" 2>&1)"
grep -q "强烈建议装在用户级" <<<"$proj_out" || fail "project-level install missing user-level recommendation warning"
for skill in jira-manage jira-create-worklog jira-tag-session; do
    [[ -f "$REPO/.devin/skills/$skill/SKILL.md" ]] || fail "missing project install: $skill"
done
pass "project-level install creates three skills and warns about user-level recommendation"

# 5) project-level check
bash "$PACK_DIR/install.sh" check --project "$REPO" >/dev/null || fail "project-level check failed"
pass "project-level check passes"

# 6) project-level uninstall
bash "$PACK_DIR/install.sh" uninstall --project "$REPO" --yes >/dev/null
for skill in jira-manage jira-create-worklog jira-tag-session; do
    [[ ! -e "$REPO/.devin/skills/$skill" ]] || fail "project uninstall left: $skill"
done
pass "project-level uninstall removes skills"

# 7) project-level install into ai-toolbox itself is refused
TOOLBOX_ROOT="$(cd "$PACK_DIR/../.." && pwd -P)"
set +e
self_out="$(bash "$PACK_DIR/install.sh" --project "$TOOLBOX_ROOT" 2>&1)"
self_rc=$?
set -e
[[ "$self_rc" == "1" ]] || fail "expected exit 1 when installing --project into ai-toolbox, got $self_rc"
grep -q "不能用 --project 装进 ai-toolbox 本仓" <<<"$self_out" || fail "missing ai-toolbox self-install error message"
for skill in jira-manage jira-create-worklog jira-tag-session; do
    [[ ! -e "$TOOLBOX_ROOT/.devin/skills/$skill" ]] || fail "ai-toolbox .devin/skills polluted: $skill"
done
pass "project-level install into ai-toolbox itself is refused"

echo "[PASS] install tests"
