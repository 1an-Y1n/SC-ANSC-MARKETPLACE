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

"""Transition resolution and payload tests.

The resolution order is the whole point of this script: an id must beat a name,
an exact name must beat a prefix, and an ambiguous prefix must fail loudly
instead of guessing — "In Progress" vs "In Review" share the prefix "In ".
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import transition_jira_issue as tj  # noqa: E402

TRANSITIONS = [
    {"id": "11", "name": "In Progress", "to": "In Progress"},
    {"id": "21", "name": "In Review", "to": "In Review"},
    {"id": "31", "name": "Resolve Issue", "to": "Resolved"},
]


class ResolveTransitionTest(unittest.TestCase):
    def test_exact_id(self):
        transition, error = tj.resolve_transition(TRANSITIONS, "31")
        self.assertEqual("Resolve Issue", transition["name"])
        self.assertEqual("", error)

    def test_exact_name_is_case_insensitive(self):
        transition, _ = tj.resolve_transition(TRANSITIONS, "in progress")
        self.assertEqual("11", transition["id"])

    def test_target_status_name_is_accepted(self):
        transition, _ = tj.resolve_transition(TRANSITIONS, "Resolved")
        self.assertEqual("31", transition["id"])

    def test_unique_prefix_is_accepted(self):
        transition, _ = tj.resolve_transition(TRANSITIONS, "Resol")
        self.assertEqual("31", transition["id"])

    def test_ambiguous_prefix_fails_and_lists_candidates(self):
        transition, error = tj.resolve_transition(TRANSITIONS, "In")
        self.assertIsNone(transition)
        self.assertIn("ambiguous", error)
        self.assertIn("In Review", error)
        self.assertIn("In Progress", error)

    def test_unknown_value_fails_and_lists_candidates(self):
        transition, error = tj.resolve_transition(TRANSITIONS, "Closed")
        self.assertIsNone(transition)
        self.assertIn("No transition matches", error)
        self.assertIn("Resolve Issue", error)

    def test_empty_transition_list_is_reported(self):
        transition, error = tj.resolve_transition([], "Done")
        self.assertIsNone(transition)
        self.assertIn("no transitions available", error)


class ApplyTransitionTest(unittest.TestCase):
    def test_payload_carries_transition_and_comment_together(self):
        client = mock.Mock()
        tj.apply_transition(client, "DUZ01-1", "31", "done")
        args, kwargs = client.request.call_args
        self.assertEqual(("POST", "/issue/DUZ01-1/transitions"), args)
        self.assertEqual(
            {"transition": {"id": "31"}, "update": {"comment": [{"add": {"body": "done"}}]}},
            kwargs["data"],
        )

    def test_payload_without_comment_has_no_update_block(self):
        client = mock.Mock()
        tj.apply_transition(client, "DUZ01-1", 31)
        _, kwargs = client.request.call_args
        self.assertEqual({"transition": {"id": "31"}}, kwargs["data"])


class FetchTransitionsTest(unittest.TestCase):
    def test_flattens_target_status(self):
        client = mock.Mock()
        client.request.return_value = {
            "transitions": [
                {"id": 11, "name": "Start Progress", "to": {"name": "In Progress"}},
            ]
        }
        self.assertEqual(
            [{"id": "11", "name": "Start Progress", "to": "In Progress"}],
            tj.fetch_transitions(client, "DUZ01-1"),
        )


if __name__ == "__main__":
    unittest.main()
