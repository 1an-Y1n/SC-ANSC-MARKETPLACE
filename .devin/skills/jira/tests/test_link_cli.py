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

"""Issue-link CLI tests.

Direction is the easy thing to get backwards: --outward is the issue that does
the action ("A blocks B"), --inward is the one it is done to. These tests pin
the payload shape so the two cannot silently swap.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import link_jira_issues as lj  # noqa: E402


class ListLinkTypesTest(unittest.TestCase):
    def test_flattens_inward_and_outward_labels(self):
        client = mock.Mock()
        client.request.return_value = {
            "issueLinkTypes": [
                {"id": 10000, "name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
            ]
        }
        self.assertEqual(
            [{"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}],
            lj.list_link_types(client),
        )


class CreateLinkTest(unittest.TestCase):
    def test_payload_keeps_outward_and_inward_apart(self):
        client = mock.Mock()
        result = lj.create_link(client, "Blocks", "DUZ01-1600", "DUZ01-1560")

        args, kwargs = client.request.call_args
        self.assertEqual(("POST", "/issueLink"), args)
        self.assertEqual(
            {
                "type": {"name": "Blocks"},
                "outwardIssue": {"key": "DUZ01-1600"},
                "inwardIssue": {"key": "DUZ01-1560"},
            },
            kwargs["data"],
        )
        self.assertEqual("DUZ01-1600", result["outward"])
        self.assertEqual("DUZ01-1560", result["inward"])


if __name__ == "__main__":
    unittest.main()
