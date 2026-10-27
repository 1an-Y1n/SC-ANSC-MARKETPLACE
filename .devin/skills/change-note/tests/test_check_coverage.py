#!/usr/bin/env python3
"""check_coverage.py 的回归测试。

覆盖审查意见里的四类风险：基线选择、`--base` 校验、`## 覆盖检查` 回写的
幂等性，以及「只认 `## 文件覆盖表` 里的精确路径」——最后一条用于防止
`README.md` 被 `skills/foo/README.md` 这样的更长路径误判为已覆盖。
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import check_coverage as cc  # noqa: E402


class CheckCoverageTest(unittest.TestCase):
    """在临时 git 仓库里跑 check_coverage 的关键路径。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")

    def tearDown(self):
        self._tmp.cleanup()

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def _commit(self, files: dict[str, str], message: str = "commit") -> None:
        for name, content in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", message)

    def test_dirty_worktree_baseline(self):
        self._commit({"a.txt": "a"})
        (self.repo / "a.txt").write_text("b", encoding="utf-8")

        baseline, files = cc.detect_changes(self.repo)

        self.assertEqual(baseline, "工作区 vs HEAD")
        self.assertEqual(files, ["a.txt"])

    def test_merge_base_baseline(self):
        self._commit({"a.txt": "a"})
        # 本地分支当上游，避免测试依赖网络 / 远端配置
        self._git("branch", "upstream")
        self._git("branch", "--set-upstream-to=upstream")
        self._commit({"b.txt": "b"})

        baseline, files = cc.detect_changes(self.repo)

        self.assertTrue(baseline.startswith("merge-base("))
        self.assertEqual(files, ["b.txt"])

    def test_head_parent_baseline(self):
        self._commit({"a.txt": "a"})
        self._commit({"b.txt": "b"})

        baseline, files = cc.detect_changes(self.repo)

        self.assertEqual(baseline, "HEAD~1")
        self.assertEqual(files, ["b.txt"])

    def test_empty_repo_has_no_changes(self):
        baseline, files = cc.detect_changes(self.repo)

        self.assertEqual((baseline, files), ("无改动", []))

    def test_invalid_base_raises(self):
        self._commit({"a.txt": "a"})

        with self.assertRaises(cc.InvalidBaseError):
            cc.detect_changes(self.repo, "no-such-ref")

    def test_invalid_base_cli_exits_2(self):
        self._commit({"a.txt": "a"})

        self.assertEqual(
            cc.main(["--list", "--repo", str(self.repo), "--base", "no-such-ref"]),
            2,
        )

    def test_strip_section_removes_generated_block(self):
        text = (
            "# note\n\nbody\n\n"
            "## 覆盖检查\n\n"
            "| 文件 | 状态 |\n| --- | --- |\n| `a.txt` | 已覆盖 |\n\n"
            "## 修订记录\n\nlog\n"
        )

        stripped = cc.strip_section(text)

        self.assertNotIn("已覆盖", stripped)
        self.assertIn("body", stripped)
        self.assertIn("## 修订记录", stripped)

    def test_upsert_section_is_idempotent(self):
        text = "# note\n\nbody\n\n## 覆盖检查\n"
        block = cc.build_block(["a.txt"], [], "HEAD")

        once = cc.upsert_section(text, block)
        twice = cc.upsert_section(once, block)

        self.assertEqual(once.count("## 覆盖检查"), 1)
        self.assertEqual(twice.count("## 覆盖检查"), 1)
        self.assertIn("覆盖 1/1", twice)

    def test_table_paths_only_reads_coverage_table(self):
        text = (
            "# note\n\nprose `skills/foo/README.md`\n\n"
            "## 文件覆盖表\n\n"
            "| 文件 | 单元 | 类型 |\n| --- | --- | --- |\n"
            "| `skills/foo/README.md` | U1 | 核心 |\n\n"
            "## 覆盖检查\n\n| `README.md` | 已覆盖 |\n"
        )

        self.assertEqual(cc._table_paths(text), {"skills/foo/README.md"})

    def test_note_check_reports_missing_and_is_idempotent(self):
        self._commit({"README.md": "root\n", "skills/foo/README.md": "nested\n"})
        (self.repo / "README.md").write_text("root2\n", encoding="utf-8")
        (self.repo / "skills/foo/README.md").write_text("nested2\n", encoding="utf-8")

        with tempfile.TemporaryDirectory() as note_dir:
            note = Path(note_dir) / "note.md"
            note.write_text(
                "# note\n\nOnly the nested file.\n\n"
                "## 文件覆盖表\n\n"
                "| 文件 | 单元 | 类型 |\n| --- | --- | --- |\n"
                "| `skills/foo/README.md` | U1 | 核心 |\n\n"
                "## 覆盖检查\n",
                encoding="utf-8",
            )

            args = ["--note", str(note), "--repo", str(self.repo), "--base", "HEAD"]
            self.assertEqual(cc.main(args), 0)
            text = note.read_text(encoding="utf-8")
            self.assertIn("| `README.md` | **未覆盖** |", text)
            self.assertIn("| `skills/foo/README.md` | 已覆盖 |", text)

            self.assertEqual(cc.main(args), 0)
            self.assertEqual(note.read_text(encoding="utf-8").count("## 覆盖检查"), 1)


if __name__ == "__main__":
    unittest.main()
