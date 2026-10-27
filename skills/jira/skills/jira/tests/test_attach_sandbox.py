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

"""Attachment sandbox tests.

Pins the two rules that stop a Jira-provided filename, or a careless --file,
from reaching files outside the staging directory: names are reduced to their
basename, and uploads refuse credential-like files and protected directories.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import attach_sandbox  # noqa: E402


class SafeDownloadPathTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # realpath keeps the expectations stable on systems where /tmp itself
        # is a symlink (macOS): ensure_inside resolves links by design.
        self.root = os.path.realpath(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_strips_relative_traversal(self):
        path = attach_sandbox.safe_download_path(self.root, "../../.bashrc")
        self.assertEqual(os.path.join(self.root, ".bashrc"), path)

    def test_strips_absolute_path(self):
        path = attach_sandbox.safe_download_path(self.root, "/etc/passwd")
        self.assertEqual(os.path.join(self.root, "passwd"), path)

    def test_strips_windows_separators(self):
        path = attach_sandbox.safe_download_path(self.root, "..\\..\\evil.txt")
        self.assertEqual(os.path.join(self.root, "evil.txt"), path)

    def test_never_overwrites_an_existing_file(self):
        first = attach_sandbox.safe_download_path(self.root, "log.txt")
        Path(first).write_text("one", encoding="utf-8")

        second = attach_sandbox.safe_download_path(self.root, "log.txt")
        self.assertEqual(os.path.join(self.root, "log_1.txt"), second)
        Path(second).write_text("two", encoding="utf-8")

        third = attach_sandbox.safe_download_path(self.root, "log.txt")
        self.assertEqual(os.path.join(self.root, "log_2.txt"), third)

    def test_rejects_names_without_a_basename(self):
        for name in ("", ".", "..", "../"):
            with self.assertRaises(attach_sandbox.SandboxError):
                attach_sandbox.safe_download_path(self.root, name)

    def test_rejects_symlink_download_target(self):
        # A dangling symlink makes os.path.exists() False, so without an
        # explicit islink check the collision loop would write through it.
        outside = tempfile.mkdtemp()
        try:
            os.symlink(os.path.join(outside, "target.txt"), os.path.join(self.root, "evil.txt"))
            with self.assertRaises(attach_sandbox.SandboxError) as ctx:
                attach_sandbox.safe_download_path(self.root, "evil.txt")
            self.assertIn("symlink", str(ctx.exception))
        finally:
            shutil.rmtree(outside)

    def test_rejects_symlink_in_collision_suffix(self):
        # The _1/_2 suffix loop is a sibling path to the same file and needs the
        # same refusal, otherwise a pre-planted symlink there escapes the root.
        Path(attach_sandbox.safe_download_path(self.root, "evil.txt")).write_text("one")

        outside = tempfile.mkdtemp()
        try:
            os.symlink(os.path.join(outside, "pwned.txt"), os.path.join(self.root, "evil_1.txt"))
            with self.assertRaises(attach_sandbox.SandboxError) as ctx:
                attach_sandbox.safe_download_path(self.root, "evil.txt")
            self.assertIn("symlink", str(ctx.exception))
            self.assertFalse(os.path.exists(os.path.join(outside, "pwned.txt")))
        finally:
            shutil.rmtree(outside)


class CheckUploadPathTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, relative, content="x"):
        path = os.path.join(self.root, relative)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def test_accepts_file_inside_root(self):
        path = self._write("design.md")
        self.assertEqual(path, attach_sandbox.check_upload_path(self.root, path))

    def test_rejects_file_outside_root(self):
        outside = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        outside.close()
        try:
            with self.assertRaises(attach_sandbox.SandboxError) as ctx:
                attach_sandbox.check_upload_path(self.root, outside.name)
            self.assertIn("outside the attachment sandbox", str(ctx.exception))
        finally:
            os.unlink(outside.name)

    def test_rejects_env_file(self):
        path = self._write(".env.production")
        with self.assertRaises(attach_sandbox.SandboxError) as ctx:
            attach_sandbox.check_upload_path(self.root, path)
        self.assertIn("credential-like", str(ctx.exception))

    def test_rejects_private_key(self):
        path = self._write("server.pem")
        with self.assertRaises(attach_sandbox.SandboxError):
            attach_sandbox.check_upload_path(self.root, path)

    def test_rejects_mcp_config(self):
        path = self._write("mcp_config.local.json")
        with self.assertRaises(attach_sandbox.SandboxError):
            attach_sandbox.check_upload_path(self.root, path)

    def test_rejects_file_under_protected_directory(self):
        path = self._write(os.path.join(".ssh", "id_ed25519"))
        with self.assertRaises(attach_sandbox.SandboxError) as ctx:
            attach_sandbox.check_upload_path(self.root, path)
        self.assertIn("protected directory", str(ctx.exception))

    def test_rejects_symlink_pointing_outside_root(self):
        # The link's own name ("id") passes the credential-name check, so the
        # only thing standing between this and an uploaded private key is the
        # symlink rejection.
        outside = tempfile.mkdtemp()
        try:
            secret = os.path.join(outside, "id_rsa")
            Path(secret).write_text("PRIVATE", encoding="utf-8")
            link = os.path.join(self.root, "id")
            os.symlink(secret, link)

            with self.assertRaises(attach_sandbox.SandboxError) as ctx:
                attach_sandbox.check_upload_path(self.root, link)
            self.assertIn("symlink", str(ctx.exception))
        finally:
            shutil.rmtree(outside)

    def test_rejects_symlinked_directory_component(self):
        # islink() only sees the final component; a symlinked *directory*
        # inside the root is caught by the realpath containment check instead.
        outside = tempfile.mkdtemp()
        try:
            Path(os.path.join(outside, "notes.md")).write_text("x", encoding="utf-8")
            os.symlink(outside, os.path.join(self.root, "linkdir"))

            with self.assertRaises(attach_sandbox.SandboxError) as ctx:
                attach_sandbox.check_upload_path(
                    self.root, os.path.join(self.root, "linkdir", "notes.md")
                )
            self.assertIn("outside the attachment sandbox", str(ctx.exception))
        finally:
            shutil.rmtree(outside)

    def test_rejects_missing_file(self):
        with self.assertRaises(attach_sandbox.SandboxError) as ctx:
            attach_sandbox.check_upload_path(self.root, os.path.join(self.root, "nope.txt"))
        self.assertIn("not found", str(ctx.exception))


class DownloadSandboxTest(unittest.TestCase):
    """The rules only hold if download_attachments actually applies them."""

    CONFIG = {
        "jira_url": "https://jira.example.invalid",
        "jira_token": "t",
        "jira_auth_type": "bearer",
        "ssl_verify": False,
        "timeout": 5,
    }

    def setUp(self):
        import get_jira_issue as gj

        self.gj = gj
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_traversal_filename_stays_inside_root(self):
        result = {"attachments": [{
            "filename": "../../evil.txt",
            "content_url": "https://jira.example.invalid/secure/attachment/1/evil.txt",
        }]}
        response = mock.Mock(status_code=200, content=b"payload")

        with mock.patch.object(self.gj.requests, "get", return_value=response):
            saved = self.gj.download_attachments(result, self.CONFIG, self.root)

        expected = os.path.join(self.root, "evil.txt")
        self.assertEqual([expected], saved)
        self.assertTrue(os.path.isfile(expected))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.root), "evil.txt")))

    def test_foreign_origin_is_rejected(self):
        result = {"attachments": [{
            "filename": "evil.txt",
            "content_url": "https://attacker.example.invalid/evil.txt",
        }]}
        with mock.patch.object(self.gj.requests, "get") as get:
            saved = self.gj.download_attachments(result, self.CONFIG, self.root)

        self.assertEqual([], saved)
        self.assertEqual(0, get.call_count)
        self.assertIn("outside the Jira origin", " ".join(result["download_errors"]))

    def test_redirect_is_refused(self):
        # Checking the origin of the URL Jira returned is useless if the fetch
        # can then be redirected to another host.
        result = {"attachments": [{
            "filename": "evil.txt",
            "content_url": "https://jira.example.invalid/secure/attachment/1/evil.txt",
        }]}
        response = mock.Mock(status_code=302, content=b"")
        with mock.patch.object(self.gj.requests, "get", return_value=response) as get:
            saved = self.gj.download_attachments(result, self.CONFIG, self.root)

        self.assertEqual([], saved)
        self.assertIn("redirected", " ".join(result["download_errors"]))
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(get.call_args.kwargs["stream"])
        self.assertFalse(os.path.exists(os.path.join(self.root, "evil.txt")))

    def test_content_length_over_cap_is_rejected_without_writing(self):
        result = {"attachments": [{
            "filename": "huge.bin",
            "content_url": "https://jira.example.invalid/secure/attachment/1/huge.bin",
        }]}
        response = mock.Mock(
            status_code=200,
            headers={"Content-Length": str(self.gj.DEFAULT_MAX_ATTACHMENT_BYTES + 1)},
        )
        response.iter_content.return_value = [b"should not be read"]

        with mock.patch.object(self.gj.requests, "get", return_value=response):
            saved = self.gj.download_attachments(result, self.CONFIG, self.root)

        self.assertEqual([], saved)
        self.assertEqual(0, response.iter_content.call_count)
        self.assertIn("Content-Length", " ".join(result["download_errors"]))
        self.assertFalse(os.path.exists(os.path.join(self.root, "huge.bin")))

    def test_streamed_body_over_cap_aborts_and_removes_partial_file(self):
        # Even when Content-Length is absent or lies, streaming must stop once
        # the accumulated bytes cross JIRA_MAX_ATTACHMENT_BYTES and unlink any
        # partial file rather than silently truncating.
        result = {"attachments": [{
            "filename": "stream.bin",
            "content_url": "https://jira.example.invalid/secure/attachment/1/stream.bin",
        }]}
        response = mock.Mock(status_code=200, headers={})
        response.iter_content.return_value = [b"12345", b"67890", b"overflow"]

        with mock.patch.dict(os.environ, {"JIRA_MAX_ATTACHMENT_BYTES": "10"}), \
                mock.patch.object(self.gj.requests, "get", return_value=response):
            saved = self.gj.download_attachments(result, self.CONFIG, self.root)

        self.assertEqual([], saved)
        self.assertIn("exceeds limit of 10 bytes", " ".join(result["download_errors"]))
        self.assertFalse(os.path.exists(os.path.join(self.root, "stream.bin")))


class RootResolutionTest(unittest.TestCase):
    def test_project_root_used_inside_a_git_repo(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, ".git"))
            nested = os.path.join(repo, "src", "deep")
            os.makedirs(nested)
            self.assertEqual(
                os.path.join(repo, ".devin", "TmpWorkDir", "attach_root"),
                attach_sandbox.default_root(nested),
            )

    def test_git_file_marks_a_worktree_root(self):
        # In a linked worktree or a submodule .git is a file, not a directory.
        with tempfile.TemporaryDirectory() as repo:
            Path(os.path.join(repo, ".git")).write_text(
                "gitdir: /elsewhere/.git/worktrees/x\n", encoding="utf-8"
            )
            nested = os.path.join(repo, "src")
            os.makedirs(nested)
            self.assertEqual(
                os.path.join(repo, ".devin", "TmpWorkDir", "attach_root"),
                attach_sandbox.default_root(nested),
            )

    def test_falls_back_to_cache_outside_a_repo(self):
        with tempfile.TemporaryDirectory() as plain:
            self.assertEqual(
                os.path.expanduser("~/.cache/jira-skill/attach_root"),
                attach_sandbox.default_root(plain),
            )

    def test_create_writes_self_ignoring_gitignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "attach_root")
            attach_sandbox.resolve_root(root, create=True)
            self.assertTrue(os.path.isdir(root))
            with open(os.path.join(root, ".gitignore"), encoding="utf-8") as handle:
                self.assertEqual("*\n", handle.read())

    def test_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(tmp, attach_sandbox.resolve_root(tmp))


if __name__ == "__main__":
    unittest.main()
