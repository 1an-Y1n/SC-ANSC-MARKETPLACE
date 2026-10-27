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

"""Upload CLI confirmation gate and sandbox enforcement tests.

main() in upload_jira_attachment.py is the only code path that pushes local
bytes to the Jira server, so both the --yes confirmation gate and the sandbox
check must be tested through main() itself rather than only via helper unit
tests.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import upload_jira_attachment as ua  # noqa: E402


class UploadCliTest(unittest.TestCase):
    CONFIG = {
        "jira_url": "https://jira.example.invalid",
        "jira_token": "token",
        "jira_auth_type": "bearer",
        "ssl_verify": False,
        "timeout": 5,
    }

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_inside(self, name="design.md", content="hello"):
        path = os.path.join(self.root, name)
        Path(path).write_text(content, encoding="utf-8")
        return path

    def _run_main(self, argv):
        buffer = io.StringIO()
        exit_code = 0
        with mock.patch.object(ua, "JIRA_CONFIG", dict(self.CONFIG)), \
                mock.patch.object(sys, "argv", ["upload_jira_attachment.py"] + list(argv)), \
                redirect_stdout(buffer):
            try:
                ua.main()
            except SystemExit as exc:
                exit_code = exc.code if exc.code is not None else 0
        return exit_code, buffer.getvalue()

    def test_without_yes_previews_and_never_calls_post(self):
        source = self._write_inside("notes.txt", "payload")
        with mock.patch.object(ua.requests, "post") as post:
            code, output = self._run_main(
                ["DUZ01-1560", "--attach-root", self.root, "--file", source]
            )

        self.assertEqual(0, code)
        self.assertEqual(0, post.call_count)
        self.assertIn("PREVIEW ONLY - NOTHING UPLOADED", output)
        self.assertIn("Re-run with --yes to upload.", output)

    def test_with_yes_uploads_to_jira(self):
        source = self._write_inside("notes.txt", "payload")
        response = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value=[{"id": "99", "filename": "notes.txt", "size": 7}]),
        )
        with mock.patch.object(ua.requests, "post", return_value=response) as post:
            code, output = self._run_main(
                ["DUZ01-1560", "--attach-root", self.root, "--file", source, "--yes"]
            )

        self.assertEqual(0, code)
        self.assertEqual(1, post.call_count)
        self.assertIn("/rest/api/2/issue/DUZ01-1560/attachments", post.call_args.args[0])
        self.assertEqual("no-check", post.call_args.kwargs["headers"].get("X-Atlassian-Token"))
        self.assertIn("ATTACHMENT UPLOADED SUCCESSFULLY", output)

    def test_source_outside_sandbox_exits_one_without_uploading(self):
        outside = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        outside.write(b"secret")
        outside.close()
        try:
            with mock.patch.object(ua.requests, "post") as post:
                code, output = self._run_main(
                    ["DUZ01-1560", "--attach-root", self.root, "--file", outside.name, "--yes"]
                )
        finally:
            os.unlink(outside.name)

        self.assertEqual(1, code)
        self.assertEqual(0, post.call_count)
        self.assertIn("outside the attachment sandbox", output)

    def test_attach_root_dot_allows_repo_file(self):
        with tempfile.TemporaryDirectory() as repo:
            doc_dir = os.path.join(repo, "doc")
            os.makedirs(doc_dir)
            doc = os.path.join(doc_dir, "design.md")
            Path(doc).write_text("# spec\n", encoding="utf-8")

            response = mock.Mock(
                status_code=200,
                json=mock.Mock(return_value=[{"id": "100", "filename": "design.md", "size": 7}]),
            )
            old_cwd = os.getcwd()
            try:
                os.chdir(repo)
                with mock.patch.object(ua.requests, "post", return_value=response) as post:
                    code, output = self._run_main(
                        ["DUZ01-1560", "--attach-root", ".", "--file", os.path.join("doc", "design.md"), "--yes"]
                    )
            finally:
                os.chdir(old_cwd)

        self.assertEqual(0, code)
        self.assertEqual(1, post.call_count)
        self.assertIn("ATTACHMENT UPLOADED SUCCESSFULLY", output)


if __name__ == "__main__":
    unittest.main()
