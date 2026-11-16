import shutil
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "orchestrator"))
from development.codex_stage_safety import (claim_pending, inspect_example_repo,
                                            validate_spec_and_target, validate_work_binding,
                                            verify_frozen_review, verify_scoped_diff)


BASE = Path(__file__).resolve().parents[2] / "tmp" / "codex-stage-tests"


class StageSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = BASE / f"run-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True)
        self.addCleanup(self.cleanup)
        self.thread = "safe-test-1"
        self.repo = self.tmp / "development-sandboxes" / self.thread / "example-repo"
        self.repo.mkdir(parents=True)
        (self.repo / ".git").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.repo / "src" / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
        self.patcher = patch("development.codex_stage_safety._git", side_effect=self.fake_git)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def cleanup(self):
        target = self.tmp.resolve()
        if target.parent != BASE.resolve() or not target.name.startswith("run-"):
            raise ValueError("unsafe test cleanup")
        shutil.rmtree(target)

    def fake_git(self, _repo, *args):
        command = args[0]
        tracked = ["src/module.py", "src/other.py"]
        changed = [name for name in tracked if (self.repo / name).read_text(encoding="utf-8") !=
                   ("VALUE = 1\n" if name == "src/module.py" else "OTHER = 1\n")]
        new = (self.repo / "src" / "new.py").exists()
        if command == "rev-parse":
            return (str(self.repo) if "--show-toplevel" in args else "a" * 40).encode()
        if command == "ls-files":
            return b"src/module.py\n"
        if command == "status":
            return ("".join(" M " + name + "\0" for name in changed) +
                    ("?? src/new.py\0" if new else "")).encode()
        if command == "diff" and "--name-only" in args:
            return ("\n".join(changed) + ("\n" if changed else "")).encode()
        if command == "diff" and "--binary" in args:
            return (";".join(name + ":" + (self.repo / name).read_text(encoding="utf-8") for name in changed)).encode()
        if command == "diff" and "--check" in args:
            if any((self.repo / name).read_text(encoding="utf-8").rstrip("\n").endswith("  ") for name in changed):
                raise ValueError("Git evidence command failed")
            return b""
        raise AssertionError("unexpected fake Git call")

    def baseline(self):
        return inspect_example_repo(self.tmp, self.thread, self.repo, "src/module.py", require_clean=True)

    def test_clean_baseline_and_scoped_diff_freeze(self):
        before = self.baseline()
        (self.repo / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        frozen = verify_scoped_diff(self.tmp, self.thread, self.repo, before)
        self.assertEqual(frozen["checks"], {"git_diff_check": "passed"})
        self.assertTrue(verify_frozen_review(self.tmp, self.thread, self.repo, frozen))
        (self.repo / "src" / "module.py").write_text("VALUE = 3\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            verify_frozen_review(self.tmp, self.thread, self.repo, frozen)

    def test_preexisting_change_blocks_baseline(self):
        (self.repo / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pre-existing"):
            self.baseline()

    def test_out_of_scope_or_new_file_blocks_diff(self):
        before = self.baseline()
        (self.repo / "src" / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outside target"):
            verify_scoped_diff(self.tmp, self.thread, self.repo, before)
        (self.repo / "src" / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
        (self.repo / "src" / "new.py").write_text("NEW = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "added or removed"):
            verify_scoped_diff(self.tmp, self.thread, self.repo, before)

    def test_git_metadata_change_blocks_diff(self):
        before = self.baseline()
        (self.repo / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        (self.repo / ".git" / "unexpected-marker").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "added or removed"):
            verify_scoped_diff(self.tmp, self.thread, self.repo, before)

    def test_diff_check_failure_blocks(self):
        before = self.baseline()
        (self.repo / "src" / "module.py").write_text("VALUE = 2  \n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Git evidence"):
            verify_scoped_diff(self.tmp, self.thread, self.repo, before)

    def test_pending_journal_blocks_replay_after_crash_like_write(self):
        folder = self.tmp / "development-runs" / self.thread
        folder.mkdir(parents=True)
        key = claim_pending(self.tmp, folder, self.thread, "work")
        self.assertEqual(key, f"{self.thread}:work:1")
        (self.repo / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            claim_pending(self.tmp, folder, self.thread, "work")
        self.assertIn('"pending"', (folder / "codex-work-receipt.json").read_text())

    def test_spec_target_and_bound_approval(self):
        with self.assertRaisesRegex(ValueError, "Open Questions"):
            validate_spec_and_target("## Open Questions\n\n- unresolved", "src/module.py")
        validate_spec_and_target("## Open Questions\n\nNenhuma.", "src/module.py")
        before = self.baseline()
        now = datetime.now(timezone.utc)
        binding = {"thread_id": self.thread, "issue_key": "LOCAL-1", "plan_sha256": "a" * 64,
                   "repo": str(self.repo.resolve()), "head": before["head"],
                   "target_module": "src/module.py", "decision": "approve-work", "actor": "human-test",
                   "approved_at": now.isoformat(), "expires_at": (now + timedelta(minutes=5)).isoformat()}
        validate_work_binding(binding, thread_id=self.thread, issue_key="LOCAL-1",
                              plan_sha256="a" * 64, repo=self.repo, head=before["head"],
                              target_module="src/module.py")
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            validate_work_binding(binding, thread_id="another-thread", issue_key="LOCAL-1",
                                  plan_sha256="a" * 64, repo=self.repo, head=before["head"],
                                  target_module="src/module.py")


if __name__ == "__main__":
    unittest.main()
