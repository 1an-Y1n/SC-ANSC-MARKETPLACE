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

"""Query-mode tests for --jql and --versions.

Two query styles in one script only work if mixing them is refused: silently
preferring one would make the other look ignored. The version listing is pinned
here too because it feeds Fix Version/s values that are easy to mistype.
"""

import argparse
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import get_jira_projects as gp  # noqa: E402
import query_jira_tickets as qj  # noqa: E402


def _query_args(**kwargs):
    defaults = {
        "project": None, "assignee": None, "reporter": None,
        "status": None, "type": None, "priority": None, "jql": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class QueryArgValidationTest(unittest.TestCase):
    def test_jql_with_structured_filter_is_refused(self):
        error = qj.validate_query_args(_query_args(jql="project = X", project="X"))
        self.assertIn("--jql cannot be combined", error)

    def test_jql_alone_is_accepted(self):
        self.assertEqual("", qj.validate_query_args(_query_args(jql="project = X")))

    def test_structured_filters_alone_are_accepted(self):
        self.assertEqual("", qj.validate_query_args(_query_args(project="X", status="Open")))

    def test_nothing_is_accepted_here_and_rejected_by_main(self):
        self.assertEqual("", qj.validate_query_args(_query_args()))


class BuildJqlTest(unittest.TestCase):
    def test_raw_jql_is_returned_verbatim(self):
        jql = qj.build_jql(_query_args(jql='project = DUZ01 AND status != Closed ORDER BY created DESC'))
        self.assertEqual('project = DUZ01 AND status != Closed ORDER BY created DESC', jql)

    def test_structured_filters_are_anded(self):
        jql = qj.build_jql(_query_args(project="DUZ01", status="Open"))
        self.assertEqual('project = DUZ01 AND status = "Open"', jql)


class ProjectVersionsTest(unittest.TestCase):
    def test_versions_are_normalized(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = [
            {"id": 10100, "name": "V1.0", "released": True, "archived": False, "releaseDate": "2026-01-31"},
            {"id": 10101, "name": "V1.1", "released": False, "archived": True},
        ]
        with mock.patch.object(gp.requests, "get", return_value=response):
            result = gp.get_project_versions("DUZ01")

        self.assertEqual("success", result["status"])
        self.assertEqual("DUZ01", result["data"]["project"])
        self.assertEqual(2, result["data"]["total"])
        self.assertEqual("10100", result["data"]["versions"][0]["id"])
        self.assertTrue(result["data"]["versions"][0]["released"])
        self.assertTrue(result["data"]["versions"][1]["archived"])

    def test_http_error_is_reported(self):
        response = mock.Mock(status_code=404, text="not found")
        with mock.patch.object(gp.requests, "get", return_value=response):
            result = gp.get_project_versions("NOPE")
        self.assertEqual("error", result["status"])
        self.assertIn("404", result["error"])

    def test_format_lists_every_version(self):
        text = gp.format_versions({
            "status": "success",
            "data": {
                "project": "DUZ01",
                "total": 1,
                "versions": [
                    {"id": "10100", "name": "V1.0", "released": True,
                     "archived": False, "releaseDate": "2026-01-31"},
                ],
            },
        })
        self.assertIn("V1.0", text)
        self.assertIn("10100", text)
        self.assertIn("DUZ01", text)


if __name__ == "__main__":
    unittest.main()
