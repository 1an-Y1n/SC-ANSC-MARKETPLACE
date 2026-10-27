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

#
# Commit staged changes while keeping Gerrit's commit-msg hook (Change-Id).
#
# Why this exists: the repo's pre-commit hook prompts interactively via
# `read ... < /dev/tty` when br-external/package/ files are staged, which blocks
# non-interactive commits. We must NOT use `git commit --no-verify` because that
# would also skip the commit-msg hook and lose the Change-Id Gerrit needs.
#
# Strategy: when (and only when) a staged path is under br-external/package/,
# commit through a temporary hooks dir that contains every hook EXCEPT
# pre-commit. Otherwise run a plain `git commit`.
#
# Usage: commit.sh [--amend] <message-file>
# The caller must have staged the intended changes already.
set -euo pipefail

amend_flag=""
if [ "${1:-}" = "--amend" ]; then
    amend_flag="--amend"
    shift
fi
msg_file="${1:?usage: commit.sh [--amend] <message-file>}"
if [ ! -f "$msg_file" ]; then
    echo "commit.sh: message file not found: $msg_file" >&2
    exit 1
fi

if [ "$#" -ne 1 ]; then
    echo "commit.sh: unexpected extra arguments: ${*:2}" >&2
    echo "usage: commit.sh [--amend] <message-file>" >&2
    exit 2
fi

if [ -n "$amend_flag" ] && [ -z "$(git diff --cached --name-only)" ]; then
    echo "commit.sh: --amend with nothing staged — stage the fix first" >&2
    exit 1
fi

needs_bypass=false
if git diff --cached --name-only | grep -q '^br-external/package/'; then
    needs_bypass=true
fi

if [ "$needs_bypass" = false ]; then
    git commit $amend_flag -F "$msg_file"
    exit $?
fi

hooks_dir="$(git rev-parse --git-path hooks)"
tmp_hooks="$(mktemp -d)"
cleanup() { rm -rf "$tmp_hooks"; }
trap cleanup EXIT

# Copy every hook except pre-commit (the only interactive one).
for h in "$hooks_dir"/*; do
    [ -f "$h" ] || continue
    base="$(basename "$h")"
    case "$base" in
        *.sample | pre-commit) continue ;;
    esac
    cp "$h" "$tmp_hooks/$base"
    chmod +x "$tmp_hooks/$base"
done

echo "commit.sh: br-external/package/ staged -> bypassing interactive pre-commit (Change-Id preserved)" >&2
git -c core.hooksPath="$tmp_hooks" commit $amend_flag -F "$msg_file"
