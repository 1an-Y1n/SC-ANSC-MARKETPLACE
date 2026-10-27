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
# Build a throwaway git repo that mimics this project's Gerrit commit
# conventions, so the auto-commit skill can be evaluated without ever touching
# the real repository.
#
# Usage: make_scratch_repo.sh <dest_dir> <scenario>
#   scenario: feature | session-scope | package | trap-artifacts | amend | clean
set -euo pipefail

dest="${1:?usage: make_scratch_repo.sh <dest_dir> <scenario>}"
scenario="${2:?usage: make_scratch_repo.sh <dest_dir> <scenario>}"

rm -rf "$dest"
mkdir -p "$dest"
cd "$dest"

git init -q
git config user.name "Argon Cheng"
git config user.email "argon_cheng@sercomm.com"
git config commit.gpgsign false

cat > .gitreview <<'EOF'
[gerrit]
host=sercomm.gerrit
port=29418
project=comcast-dz3
defaultbranch=prod_9.4.0.9trunk_mamba
EOF

mkdir -p .git/hooks

# commit-msg hook: append a Change-Id if absent (simplified Gerrit behavior).
cat > .git/hooks/commit-msg <<'EOF'
#!/bin/sh
msg_file="$1"
grep -q '^Change-Id:' "$msg_file" && exit 0
id=$(head -c 20 /dev/urandom | od -An -tx1 | tr -d ' \n')
printf '\nChange-Id: I%s\n' "$id" >> "$msg_file"
EOF
chmod +x .git/hooks/commit-msg

# pre-commit hook: mirrors the real one, which prompts via /dev/tty when
# br-external/package/ files are staged (blocks non-interactive commits).
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/bash
CHANGED_FILES=$(git diff --cached --name-only)
COMPONENT_CHANGED=false
for file in $CHANGED_FILES; do
    if echo "$file" | grep -q "br-external/package/"; then
        COMPONENT_CHANGED=true
    fi
done
if [ "$COMPONENT_CHANGED" = true ]; then
    echo "检测到组件变更，请确认是否更新文档"
    read -p "是否继续提交？(y/n) " -n 1 -r < /dev/tty
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "提交已取消"
        exit 1
    fi
fi
exit 0
EOF
chmod +x .git/hooks/pre-commit

# Baseline content so the repo looks like the real project.
mkdir -p src/sc-ampapp doc .devin/skills
cat > README.md <<'EOF'
# comcast-dz3 (scratch fixture)
EOF
cat > src/sc-ampapp/ampapp_main.c <<'EOF'
#include <stdio.h>
int main(void) { printf("ampapp v1\n"); return 0; }
EOF
cat > doc/README.md <<'EOF'
# Documentation index
EOF
git add -A
git commit -q -F - <<'EOF'
[NEW-FEATURE] [Mamba] Initial import of scratch fixture

Description:
    Baseline fixture content for the auto-commit evals.
Root Cause:
    N/A
Solution:
    N/A
Issue ID:
    EGS00-963
Merged From:
    N/A
EOF

case "$scenario" in
  feature)
    cat > src/sc-ampapp/npd_range.c <<'EOF'
/* NpD port adjustment range helper */
int npd_max_range(void) { return 4096; }
EOF
    cat > src/sc-ampapp/npd_range.h <<'EOF'
#ifndef NPD_RANGE_H
#define NPD_RANGE_H
int npd_max_range(void);
#endif
EOF
    git add src/sc-ampapp/npd_range.c src/sc-ampapp/npd_range.h
    ;;
  session-scope)
    # The file the "session" changed (the only one that should be committed).
    mkdir -p .devin/skills/foo
    cat > .devin/skills/foo/SKILL.md <<'EOF'
---
name: foo
description: placeholder skill for fixture purposes
---
# Foo
EOF
    # Unrelated working-tree changes that are NOT part of the session.
    cat > src/sc-ampapp/ampapp_main.c <<'EOF'
#include <stdio.h>
int main(void) { printf("ampapp v2\n"); return 0; }
EOF
    cat > doc/README.md <<'EOF'
# Documentation index

- package-components-index.md
EOF
    # Everything left unstaged on purpose: the skill must git add only the
    # session file and must not sweep in the unrelated changes.
    ;;
  package)
    mkdir -p br-external/package/logctl-inject
    cat > br-external/package/logctl-inject/README.md <<'EOF'
# logctl-inject
Runtime log-level injector for Broadcom libLog.
EOF
    cat > br-external/package/logctl-inject/main.c <<'EOF'
int logctl_main(void) { return 0; }
EOF
    git add br-external/package/logctl-inject/README.md br-external/package/logctl-inject/main.c
    ;;
  trap-artifacts)
    # The session's real change.
    cat > src/sc-ampapp/npd_range.c <<'EOF'
/* NpD port adjustment range helper */
int npd_max_range(void) { return 4096; }
EOF
    cat > src/sc-ampapp/npd_range.h <<'EOF'
#ifndef NPD_RANGE_H
#define NPD_RANGE_H
int npd_max_range(void);
#endif
EOF
    # Junk that must NOT be committed: secrets, build output, bytecode.
    cat > .env <<'EOF'
GERRIT_USER=sdc_argon_cheng
GERRIT_HTTP_PASSWORD=super-secret-value
EOF
    mkdir -p build __pycache__
    head -c 2048 /dev/urandom > build/firmware.img
    head -c 512 /dev/urandom > __pycache__/helper.cpython-311.pyc
    # Nothing staged: the skill must pick the session files and skip the junk.
    ;;
  amend)
    # A fix to fold into the baseline commit, which already carries a Change-Id.
    # Left unstaged on purpose: the skill must stage exactly this file.
    cat > src/sc-ampapp/ampapp_main.c <<'EOF'
#include <stdio.h>
int main(void) { printf("ampapp v2\n"); return 0; }
EOF
    ;;
  clean)
    # Nothing modified, nothing staged: `--amend` must refuse instead of
    # rewriting the commit with no code change.
    ;;
  *)
    echo "unknown scenario: $scenario" >&2
    exit 1
    ;;
esac

echo "scratch repo ready: $dest (scenario=$scenario)"
git status --short
