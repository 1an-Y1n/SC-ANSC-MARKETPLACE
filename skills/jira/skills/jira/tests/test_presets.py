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

"""Business-preset tests.

The FW Bug / Epic field rules are SerComm-specific knowledge that must survive
the refactor. They resolve field ids by name and fall back to the hardcoded id
with a warning when the instance renamed the field.
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from issue_creator import (  # noqa: E402
    _apply_epic_preset,
    _apply_fw_bug_preset,
    _field_id,
)


class FakeClient:
    def __init__(self, versions=None):
        self.versions = versions or []

    def request(self, method, path, data=None, params=None, retry_5xx=True):
        return self.versions


# 真实实例的字段映射；用空 map 的用例专门测回退
FIELD_MAP = {
    "reported by": {"id": "customfield_10116", "name": "Reported By"},
    "steps to reproduce": {"id": "customfield_10121", "name": "Steps To Reproduce"},
    "epic name": {"id": "customfield_10105", "name": "Epic Name"},
}


def _args(**overrides):
    base = {
        "project": "DUZ01",
        "summary": "summary",
        "steps": None,
        "version": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class FieldIdTest(unittest.TestCase):
    def test_resolves_by_name(self):
        field_map = {"reported by": {"id": "customfield_99999", "name": "Reported By"}}
        self.assertEqual("customfield_99999", _field_id(field_map, "reported_by"))

    def test_falls_back_and_warns(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            field_id = _field_id({}, "reported_by")
        self.assertEqual("customfield_10116", field_id)
        self.assertIn("回退硬编码 id customfield_10116", stderr.getvalue())


class FwBugPresetTest(unittest.TestCase):
    def test_reported_by_is_always_firmware(self):
        fields = {}
        _apply_fw_bug_preset(fields, _args(), FakeClient(), FIELD_MAP)
        self.assertEqual([{"id": "10007"}], fields["customfield_10116"])

    def test_steps_default_to_tbd(self):
        fields = {}
        _apply_fw_bug_preset(fields, _args(), FakeClient(), FIELD_MAP)
        self.assertEqual("TBD - Please provide steps to reproduce", fields["customfield_10121"])

    def test_explicit_steps_are_kept(self):
        fields = {}
        _apply_fw_bug_preset(fields, _args(steps="1. boot"), FakeClient(), FIELD_MAP)
        self.assertEqual("1. boot", fields["customfield_10121"])

    def test_explicit_version_uses_name(self):
        fields = {}
        _apply_fw_bug_preset(fields, _args(version="1.0.0"), FakeClient(), FIELD_MAP)
        self.assertEqual([{"name": "1.0.0"}], fields["versions"])

    def test_tbd_version_picks_first_unreleased(self):
        fields = {}
        versions = [
            {"id": "1", "name": "1.0.0", "released": True},
            {"id": "2", "name": "1.1.0", "released": False},
        ]
        _apply_fw_bug_preset(fields, _args(version="TBD"), FakeClient(versions), FIELD_MAP)
        self.assertEqual([{"id": "2"}], fields["versions"])

    def test_no_versions_leaves_field_absent(self):
        fields = {}
        _apply_fw_bug_preset(fields, _args(), FakeClient([]), FIELD_MAP)
        self.assertNotIn("versions", fields)

    def test_all_released_uses_last_version(self):
        fields = {}
        versions = [
            {"id": "1", "name": "1.0.0", "released": True},
            {"id": "2", "name": "1.1.0", "released": True},
        ]
        _apply_fw_bug_preset(fields, _args(), FakeClient(versions), FIELD_MAP)
        self.assertEqual([{"id": "2"}], fields["versions"])


class EpicPresetTest(unittest.TestCase):
    def test_epic_name_comes_from_summary(self):
        fields = {}
        _apply_epic_preset(fields, _args(summary="Epic title"), FakeClient(), FIELD_MAP)
        self.assertEqual("Epic title", fields["customfield_10105"])

    def test_epic_name_resolves_by_name(self):
        fields = {}
        field_map = {"epic name": {"id": "customfield_55555", "name": "Epic Name"}}
        _apply_epic_preset(fields, _args(summary="Epic title"), FakeClient(), field_map)
        self.assertEqual("Epic title", fields["customfield_55555"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
