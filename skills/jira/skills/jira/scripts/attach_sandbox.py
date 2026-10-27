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

"""Attachment sandbox shared by the download and upload paths.

Both directions are confined to a single root so the agent cannot touch
arbitrary files: a Jira attachment literally named ``../../.bashrc`` must not
escape the staging directory, and a careless ``--file ~/.ssh/id_rsa`` must be
refused before the bytes reach Jira.

Root selection (highest priority first):
1. ``--attach-root`` on the command line
2. ``<git toplevel>/.devin/TmpWorkDir/attach_root`` (already git-ignored in
   this repo, so downloads never get committed by accident)
3. ``~/.cache/jira-skill/attach_root`` when not inside a git repository
"""

import os

PROJECT_SUBDIR = os.path.join(".devin", "TmpWorkDir", "attach_root")
FALLBACK_ROOT = "~/.cache/jira-skill/attach_root"

# Directories that must never be reached through the sandbox, checked against
# the path *relative to the root* so the root's own ``.devin`` part is fine.
BLOCKED_DIR_NAMES = {".ssh", ".aws", ".gnupg", ".git", ".claude", ".windsurf"}

# Credential-like filenames that must never be uploaded to Jira.
BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore")
BLOCKED_FILENAMES = {"id_rsa", "id_ed25519", "credentials", "config.local.json"}


class SandboxError(ValueError):
    """Raised when a path falls outside the attachment sandbox."""


def git_toplevel(start=None):
    """Return the enclosing git repository root for ``start``, or None.

    ``.git`` is a directory in a normal clone but a *file* in a linked worktree
    or a submodule, so existence is what identifies a repo root — checking for
    a directory would silently walk past the worktree and fall back to the
    user-level cache root.
    """
    current = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def default_root(start=None):
    """Project-scoped root when inside a repo, user-level fallback otherwise."""
    top = git_toplevel(start)
    if top:
        return os.path.join(top, PROJECT_SUBDIR)
    return os.path.expanduser(FALLBACK_ROOT)


def resolve_root(override=None, start=None, create=False):
    """Resolve the sandbox root, optionally creating it with owner-only mode."""
    root = os.path.abspath(os.path.expanduser(override)) if override else default_root(start)
    if create and not os.path.isdir(root):
        os.makedirs(root, mode=0o700, exist_ok=True)
        # Self-ignoring marker: keeps attachments out of git even in repos
        # whose .gitignore does not know about .devin/TmpWorkDir.
        marker = os.path.join(root, ".gitignore")
        if not os.path.exists(marker):
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write("*\n")
    return root


def is_sensitive_name(name):
    """True when ``name`` looks like a credential file we must not upload."""
    lower = name.lower()
    if lower.startswith(".env"):
        return True
    if lower.endswith(BLOCKED_SUFFIXES):
        return True
    if lower in BLOCKED_FILENAMES:
        return True
    return lower.startswith("mcp_config")


def ensure_inside(root, path):
    """Return ``path`` resolved, raising SandboxError if it leaves ``root``.

    ``realpath`` rather than ``abspath`` is deliberate: ``abspath`` only
    normalises the string, so a symlink planted inside the root and pointing
    outside would pass the containment check while every later ``open`` /
    ``isfile`` follows it.
    """
    root_abs = os.path.realpath(root)
    target = os.path.realpath(path)
    if os.path.commonpath([root_abs, target]) != root_abs:
        raise SandboxError(
            "path is outside the attachment sandbox: %s\n"
            "sandbox root: %s\n"
            "Pass --attach-root <dir> to work somewhere else." % (target, root_abs)
        )
    return target


def _blocked_dir(root, target):
    """Return the first blocked directory component relative to ``root``."""
    rel = os.path.relpath(target, os.path.realpath(root))
    if rel == ".":
        return None
    for part in rel.split(os.sep):
        if part.lower() in BLOCKED_DIR_NAMES:
            return part
    return None


def _reject_symlink(path):
    """Raise SandboxError when ``path`` is a symlink (dangling or not).

    ``os.path.exists`` follows links, so a dangling link reports "free" and the
    following ``open(..., "wb")`` writes through it to wherever it points.
    """
    if os.path.islink(path):
        raise SandboxError("refusing to write through a symlink: %s" % (path,))


def safe_download_path(root, filename):
    """Pick a collision-free path below ``root`` for a Jira attachment name.

    Only the basename is kept, so ``../`` or an absolute path smuggled into an
    attachment name cannot escape. Existing files are never overwritten: a
    ``_1``/``_2`` suffix is added instead, which also makes blocking
    credential-like names unnecessary on the download side.
    """
    base = os.path.basename(str(filename).replace("\\", "/"))
    if base in ("", ".", ".."):
        raise SandboxError("attachment name has no usable file name: %r" % (filename,))

    candidate = os.path.join(root, base)
    # Checked before resolving: a dangling symlink makes os.path.exists() False,
    # so the collision loop would happily write through the link to wherever it
    # points instead of refusing.
    _reject_symlink(candidate)

    target = ensure_inside(root, candidate)
    if _blocked_dir(root, target):
        raise SandboxError("attachment name targets a protected directory: %s" % (filename,))

    if not os.path.exists(target):
        return target

    stem, ext = os.path.splitext(base)
    for index in range(1, 1000):
        candidate = os.path.join(root, "%s_%d%s" % (stem, index, ext))
        # Same guard as the primary name: the suffix loop is a sibling path to
        # the same file, so it needs the same symlink refusal.
        _reject_symlink(candidate)
        if not os.path.exists(candidate):
            return candidate
    raise SandboxError("too many files with the same name in %s: %s" % (root, base))


def check_upload_path(root, file_path):
    """Validate an upload source, returning its absolute path.

    Uploads are stricter than downloads: the file must already sit inside the
    sandbox, and credential-like names are refused outright — that is the one
    direction where a mistake leaks secrets to the Jira server. Symlinks are
    rejected because the basename check only sees the link's own name: an
    ``id -> ~/.ssh/id_rsa`` link inside the root would otherwise pass every
    check and upload the private key.
    """
    raw = os.path.expanduser(file_path)
    if os.path.islink(raw):
        raise SandboxError("refusing to upload through a symlink: %s" % (raw,))

    target = ensure_inside(root, raw)
    if not os.path.isfile(target):
        raise SandboxError("file not found inside the sandbox: %s" % (target,))

    blocked = _blocked_dir(root, target)
    if blocked:
        raise SandboxError("refusing to upload from protected directory %r: %s" % (blocked, target))

    name = os.path.basename(target)
    if is_sensitive_name(name):
        raise SandboxError(
            "refusing to upload a credential-like file: %s\n"
            "Move it out of the sandbox and rename it if the upload is intentional." % (name,)
        )
    return target
