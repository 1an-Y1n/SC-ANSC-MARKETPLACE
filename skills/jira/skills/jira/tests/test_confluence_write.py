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

"""Unit tests for Confluence write scripts and confluence_client.

Covers:
1. Markdown -> Confluence Storage XHTML conversion (headings, lists, code blocks,
   tables, inline styles, HTML escaping).
2. URL / page ID resolution and retry policy (never retrying 5xx or post-send
   read timeouts on writes).
3. --yes confirmation gates and payloads across all 4 Confluence write CLIs:
   create_confluence_page.py, update_confluence_page.py (replace & --append),
   add_confluence_comment.py, and upload_confluence_attachment.py (sandbox check).
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import requests

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import add_confluence_comment as acc  # noqa: E402
import confluence_client as cc  # noqa: E402
import create_confluence_page as ccp  # noqa: E402
import update_confluence_page as ucp  # noqa: E402
import upload_confluence_attachment as uca  # noqa: E402


FAKE_CONFIG = {
    "confluence_url": "https://confluence.example.invalid",
    "confluence_token": "secret-pat",
    "confluence_auth_type": "bearer",
    "ssl_verify": False,
    "timeout": 5,
    "max_retries": 2,
    "retry_base_seconds": 0,
}


class MarkdownToStorageTest(unittest.TestCase):
    def test_headings_lists_and_inline_formatting(self):
        md = (
            "# Title <1>\n\n"
            "Paragraph with **bold**, *italic*, `x < y`, and [Doc](https://example.com?a=1&b=2).\n\n"
            "- item one\n"
            "- item two\n\n"
            "1. first\n"
            "2. second\n"
        )
        storage = cc.markdown_to_storage(md)
        self.assertIn("<h1>Title &lt;1&gt;</h1>", storage)
        self.assertIn("<strong>bold</strong>", storage)
        self.assertIn("<em>italic</em>", storage)
        self.assertIn("<code>x &lt; y</code>", storage)
        self.assertIn('<a href="https://example.com?a=1&amp;b=2">Doc</a>', storage)
        self.assertIn("<ul><li>item one</li><li>item two</li></ul>", storage)
        self.assertIn("<ol><li>first</li><li>second</li></ol>", storage)

    def test_fenced_code_block_escapes_cdata_terminator(self):
        md = "```python\nprint('a]]>b')\n```"
        storage = cc.markdown_to_storage(md)
        self.assertIn('<ac:structured-macro ac:name="code">', storage)
        self.assertIn('<ac:parameter ac:name="language">python</ac:parameter>', storage)
        self.assertIn("]]]]><![CDATA[>", storage)

    def test_pipe_table_renders_thead_and_tbody(self):
        md = "| Name | Value |\n| --- | --- |\n| alpha | 1 |\n| beta | 2 |"
        storage = cc.markdown_to_storage(md)
        self.assertIn("<table><thead><tr><th>Name</th><th>Value</th></tr></thead>", storage)
        self.assertIn("<tbody><tr><td>alpha</td><td>1</td></tr><tr><td>beta</td><td>2</td></tr></tbody></table>", storage)


class ConfluenceClientResolutionAndRetryTest(unittest.TestCase):
    def test_extract_static_page_id(self):
        self.assertEqual("12345", cc.extract_static_page_id("12345"))
        self.assertEqual(
            "67890",
            cc.extract_static_page_id(
                "https://confluence.example.invalid/pages/viewpage.action?pageId=67890"
            ),
        )
        self.assertEqual(
            "54321",
            cc.extract_static_page_id(
                "https://confluence.example.invalid/spaces/ANSC/pages/54321/My+Page"
            ),
        )
        self.assertIsNone(
            cc.extract_static_page_id("https://confluence.example.invalid/display/ANSC/My+Page")
        )

    def test_resolve_display_url_queries_api(self):
        client = cc.ConfluenceClient(dict(FAKE_CONFIG))
        resp = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"results": [{"id": "777888"}]}),
        )
        with mock.patch.object(cc.requests, "get", return_value=resp) as get_mock:
            page_id = client.resolve_page_id(
                "https://confluence.example.invalid/display/ANSC/Release+Plan"
            )
        self.assertEqual("777888", page_id)
        self.assertEqual(1, get_mock.call_count)
        self.assertIn("spaceKey=ANSC", get_mock.call_args.args[0])
        self.assertIn("title=Release+Plan", get_mock.call_args.args[0])

    def test_write_does_not_retry_on_500_or_read_timeout(self):
        client = cc.ConfluenceClient(dict(FAKE_CONFIG))
        resp_500 = mock.Mock(status_code=500, reason="Internal Server Error", text="boom")
        with mock.patch.object(cc.requests, "post", return_value=resp_500) as post_mock:
            with self.assertRaises(cc.ConfluenceError):
                client.request("POST", "/content", data={"title": "x"}, retry_5xx=False)
        self.assertEqual(1, post_mock.call_count)

        with mock.patch.object(
            cc.requests, "post", side_effect=requests.ReadTimeout("timed out after send")
        ) as post_timeout:
            with self.assertRaises(cc.ConfluenceError) as ctx:
                client.request("POST", "/content", data={"title": "x"}, retry_5xx=False)
        self.assertEqual(1, post_timeout.call_count)
        self.assertIn("结果未知", str(ctx.exception))


class CreatePageCliTest(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        code = 0
        with mock.patch.object(ccp, "CONFLUENCE_CONFIG", dict(FAKE_CONFIG)), \
                mock.patch.object(sys, "argv", ["create_confluence_page.py"] + list(argv)), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                ccp.main()
            except SystemExit as exc:
                code = exc.code if exc.code is not None else 0
        return code, out.getvalue(), err.getvalue()

    def test_preview_without_yes_never_calls_post(self):
        with mock.patch.object(cc.requests, "post") as post_mock:
            code, out, _ = self._run(
                ["--space", "ANSC", "--parent", "100", "--title", "Spec", "--body", "# Hello"]
            )
        self.assertEqual(0, code)
        self.assertEqual(0, post_mock.call_count)
        self.assertIn("PREVIEW ONLY - PAGE NOT CREATED", out)
        self.assertIn("<h1>Hello</h1>", out)

    def test_create_with_yes_posts_storage_payload(self):
        created_resp = mock.Mock(
            status_code=200,
            json=mock.Mock(
                return_value={
                    "id": "2001",
                    "title": "Spec",
                    "space": {"key": "ANSC"},
                    "version": {"number": 1},
                }
            ),
        )
        with mock.patch.object(cc.requests, "post", return_value=created_resp) as post_mock:
            code, out, _ = self._run(
                [
                    "--space",
                    "ANSC",
                    "--parent",
                    "100",
                    "--title",
                    "Spec",
                    "--body",
                    "## Section",
                    "--yes",
                    "--json",
                ]
            )
        self.assertEqual(0, code)
        self.assertEqual(1, post_mock.call_count)
        sent = post_mock.call_args.kwargs["json"]
        self.assertEqual("ANSC", sent["space"]["key"])
        self.assertEqual([{"id": "100"}], sent["ancestors"])
        self.assertEqual("<h2>Section</h2>", sent["body"]["storage"]["value"])
        data = json.loads(out)
        self.assertEqual("2001", data["page_id"])


class UpdatePageCliTest(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        code = 0
        with mock.patch.object(ucp, "CONFLUENCE_CONFIG", dict(FAKE_CONFIG)), \
                mock.patch.object(sys, "argv", ["update_confluence_page.py"] + list(argv)), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                ucp.main()
            except SystemExit as exc:
                code = exc.code if exc.code is not None else 0
        return code, out.getvalue(), err.getvalue()

    def _existing_page_resp(self):
        return mock.Mock(
            status_code=200,
            json=mock.Mock(
                return_value={
                    "id": "3001",
                    "title": "Existing Title",
                    "space": {"key": "ANSC"},
                    "version": {"number": 4},
                    "body": {"storage": {"value": "<p>Old content</p>"}},
                }
            ),
        )

    def test_preview_without_yes_reads_version_but_never_puts(self):
        with mock.patch.object(cc.requests, "get", return_value=self._existing_page_resp()) as get_m, \
                mock.patch.object(cc.requests, "put") as put_m:
            code, out, _ = self._run(["3001", "--body", "New line"])
        self.assertEqual(0, code)
        self.assertEqual(1, get_m.call_count)
        self.assertEqual(0, put_m.call_count)
        self.assertIn("PREVIEW ONLY - PAGE NOT UPDATED", out)
        self.assertIn("4 -> 5", out)

    def test_append_with_yes_concatenates_storage_and_increments_version(self):
        put_resp = mock.Mock(
            status_code=200,
            json=mock.Mock(
                return_value={
                    "id": "3001",
                    "title": "Existing Title",
                    "version": {"number": 5},
                }
            ),
        )
        with mock.patch.object(cc.requests, "get", return_value=self._existing_page_resp()), \
                mock.patch.object(cc.requests, "put", return_value=put_resp) as put_m:
            code, out, _ = self._run(
                [
                    "3001",
                    "--body",
                    "## Appended",
                    "--append",
                    "--message",
                    "Add section",
                    "--yes",
                    "--json",
                ]
            )
        self.assertEqual(0, code)
        self.assertEqual(1, put_m.call_count)
        sent = put_m.call_args.kwargs["json"]
        self.assertEqual(5, sent["version"]["number"])
        self.assertEqual("Add section", sent["version"]["message"])
        self.assertEqual("Existing Title", sent["title"])
        self.assertEqual(
            "<p>Old content</p>\n<h2>Appended</h2>",
            sent["body"]["storage"]["value"],
        )
        result = json.loads(out)
        self.assertEqual("append", result["mode"])
        self.assertEqual(5, result["version"])


class AddCommentAndUploadAttachmentCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_comment_requires_yes_before_posting(self):
        out = io.StringIO()
        with mock.patch.object(acc, "CONFLUENCE_CONFIG", dict(FAKE_CONFIG)), \
                mock.patch.object(
                    sys, "argv", ["add_confluence_comment.py", "3001", "--comment", "Looks good"]
                ), \
                mock.patch.object(cc.requests, "post") as post_m, \
                redirect_stdout(out):
            acc.main()
        self.assertEqual(0, post_m.call_count)
        self.assertIn("PREVIEW ONLY - COMMENT NOT POSTED", out.getvalue())

        post_resp = mock.Mock(status_code=200, json=mock.Mock(return_value={"id": "9001"}))
        out_yes = io.StringIO()
        with mock.patch.object(acc, "CONFLUENCE_CONFIG", dict(FAKE_CONFIG)), \
                mock.patch.object(
                    sys,
                    "argv",
                    ["add_confluence_comment.py", "3001", "--comment", "Looks good", "--yes"],
                ), \
                mock.patch.object(cc.requests, "post", return_value=post_resp) as post_m, \
                redirect_stdout(out_yes):
            acc.main()
        self.assertEqual(1, post_m.call_count)
        sent = post_m.call_args.kwargs["json"]
        self.assertEqual("comment", sent["type"])
        self.assertEqual({"id": "3001", "type": "page"}, sent["container"])
        self.assertIn("CONFLUENCE COMMENT ADDED SUCCESSFULLY", out_yes.getvalue())

    def test_attachment_upload_enforces_sandbox_and_yes_gate(self):
        inside_file = os.path.join(self.root, "diagram.txt")
        Path(inside_file).write_text("diagram-bytes", encoding="utf-8")

        # 1. Without --yes -> preview only, no POST
        buf = io.StringIO()
        with mock.patch.object(uca, "CONFLUENCE_CONFIG", dict(FAKE_CONFIG)), \
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "upload_confluence_attachment.py",
                        "3001",
                        "--attach-root",
                        self.root,
                        "--file",
                        inside_file,
                    ],
                ), \
                mock.patch.object(uca.requests, "post") as post_m, \
                redirect_stdout(buf):
            uca.main()
        self.assertEqual(0, post_m.call_count)
        self.assertIn("PREVIEW ONLY - NOTHING UPLOADED", buf.getvalue())

        # 2. With --yes -> uploads with X-Atlassian-Token: no-check
        upload_resp = mock.Mock(
            status_code=200,
            json=mock.Mock(
                return_value={
                    "results": [
                        {
                            "id": "att-1",
                            "title": "diagram.txt",
                            "extensions": {"fileSize": 13},
                        }
                    ]
                }
            ),
        )
        buf_yes = io.StringIO()
        with mock.patch.object(uca, "CONFLUENCE_CONFIG", dict(FAKE_CONFIG)), \
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "upload_confluence_attachment.py",
                        "3001",
                        "--attach-root",
                        self.root,
                        "--file",
                        inside_file,
                        "--yes",
                    ],
                ), \
                mock.patch.object(uca.requests, "post", return_value=upload_resp) as post_m, \
                redirect_stdout(buf_yes):
            uca.main()
        self.assertEqual(1, post_m.call_count)
        self.assertIn("/rest/api/content/3001/child/attachment", post_m.call_args.args[0])
        self.assertEqual("no-check", post_m.call_args.kwargs["headers"].get("X-Atlassian-Token"))
        self.assertIn("CONFLUENCE ATTACHMENT UPLOADED SUCCESSFULLY", buf_yes.getvalue())


if __name__ == "__main__":
    unittest.main()
