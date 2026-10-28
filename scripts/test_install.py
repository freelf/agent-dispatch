#!/usr/bin/env python3
"""Exercise installation in isolated config directories; never change real HOME."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
BEGIN = "<!-- agent-dispatch:begin -->"
END = "<!-- agent-dispatch:end -->"


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agent-install-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "source with spaces"
        self.repo.mkdir()
        for name in ("bin", "rules", "skills"):
            shutil.copytree(ROOT / name, self.repo / name)
        (self.repo / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/install.py", self.repo / "scripts/install.py")
        shutil.copy2(ROOT / "install.sh", self.repo / "install.sh")
        self.claude = self.base / "claude"
        self.codex = self.base / "codex"
        self.skills = self.base / "codex-skills"
        self.env = dict(os.environ, AGENT_BIN_DIR=str(self.base / "bin"))
        self.env.pop("AGENT_SKILL_DIR", None)

    def run_install(self, *args, expected=0):
        result = subprocess.run([
            "sh", str(self.repo / "install.sh"), "--client", "all",
            "--claude-dir", str(self.claude), "--codex-dir", str(self.codex),
            "--codex-skills-dir", str(self.skills), *args,
        ], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def seed(self, content):
        self.claude.mkdir(exist_ok=True)
        target = self.claude / "CLAUDE.md"
        target.write_text(content)
        return target

    def test_both_clients_share_rules_and_dispatch(self):
        self.run_install()
        a = (self.claude / "CLAUDE.md").read_text()
        b = (self.codex / "AGENTS.md").read_text()
        self.assertEqual(a, b)
        for name in ("common.md", "brain.md"):
            self.assertEqual(a.count((self.repo / "rules" / name).read_text().strip()), 1)
        self.assertNotIn("## 1. Think Before Coding", a)
        for path in (self.claude / "skills/dispatch", self.skills / "dispatch"):
            self.assertEqual(path.resolve(), self.repo / "skills/dispatch")
        self.run_install("--check")

    def test_preserves_outside_block_and_is_idempotent(self):
        prefix, suffix = "# personal\n原有指令\n\n", "\n# another tool\n保留\n"
        target = self.seed(prefix + BEGIN + "\nold\n" + END + "\n" + suffix)
        old = target.read_bytes()
        target.chmod(0o640)
        self.run_install()
        content = target.read_text()
        self.assertTrue(content.startswith(prefix) and content.endswith(suffix))
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        backups = list(self.claude.glob("CLAUDE.md.bak-agent-dispatch-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), old)
        self.run_install()
        self.assertEqual(target.read_text(), content)
        self.assertEqual(list(self.claude.glob("CLAUDE.md.bak-agent-dispatch-*")), backups)

    def test_check_detects_missing_and_stale_without_writing(self):
        self.run_install("--check", expected=1)
        self.assertFalse(self.claude.exists())
        self.run_install()
        target = self.claude / "CLAUDE.md"
        old = target.read_bytes()
        source = self.repo / "rules/common.md"
        source.write_text(source.read_text() + "\nNEW-COMMON\n")
        self.run_install("--check", expected=1)
        self.assertEqual(target.read_bytes(), old)
        self.run_install()
        self.run_install("--check")
        self.assertEqual(target.read_text().count("NEW-COMMON"), 1)

    def test_combined_utf8_budget_rejects_before_writes(self):
        (self.repo / "rules/common.md").write_text("中" * 5000)
        (self.repo / "rules/brain.md").write_text("文" * 5000)
        result = self.run_install(expected=2)
        self.assertIn("超过上限", result.stderr)
        self.assertFalse(self.claude.exists())

    def test_preserved_content_counts_toward_budget(self):
        target = self.seed("x" * 24576)
        self.run_install(expected=2)
        self.assertEqual(target.read_text(), "x" * 24576)
        self.assertFalse(self.codex.exists())

    def test_malformed_markers_never_overwrite(self):
        for content in (BEGIN + "\nbroken", END, BEGIN + "\nx\n" + END + "\n" + BEGIN):
            with self.subTest(content=content):
                target = self.seed(content)
                self.run_install(expected=2)
                self.assertEqual(target.read_text(), content)

    def test_override_blocks_both_clients_before_writes(self):
        self.codex.mkdir()
        override = self.codex / "AGENTS.override.md"
        override.write_text("active override")
        self.run_install(expected=2)
        self.assertFalse(self.claude.exists())
        self.assertEqual(override.read_text(), "active override")

    def test_existing_skill_directory_is_not_replaced(self):
        destination = self.skills / "dispatch"
        destination.mkdir(parents=True)
        (destination / "mine").write_text("keep")
        self.run_install(expected=2)
        self.assertFalse(self.claude.exists())
        self.assertEqual((destination / "mine").read_text(), "keep")

    def test_rule_symlink_is_not_replaced(self):
        source = self.base / "own-rules.md"
        source.write_text("keep")
        self.claude.mkdir()
        (self.claude / "CLAUDE.md").symlink_to(source)
        self.run_install(expected=2)
        self.assertTrue((self.claude / "CLAUDE.md").is_symlink())
        self.assertEqual(source.read_text(), "keep")

    def test_single_client_and_legacy_skill_dir_override(self):
        self.env["AGENT_SKILL_DIR"] = str(self.base / "legacy-skills")
        self.run_install("--client", "claude")
        self.assertFalse(self.codex.exists())
        self.assertTrue((self.base / "legacy-skills/dispatch").is_symlink())
        self.run_install("--client", "claude", "--check")


if __name__ == "__main__":
    unittest.main()
