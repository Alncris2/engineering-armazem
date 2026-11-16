"""No real Codex: pinned wrapper selection and synthetic doctor inputs."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
from development.cli import codex_hooks_for
from development.codex_cli import PINNED_WRAPPER_RELATIVE, pinned_codex_executable
from development.spec_gate import check_spec_open_questions


class CommonPilotTests(unittest.TestCase):
    def test_start_selects_explicit_pinned_wrapper(self):
        fake_wrapper = ROOT / "tmp" / "fake-codex.cmd"
        with patch("development.cli.pinned_codex_executable", return_value=fake_wrapper) as resolve:
            hook = codex_hooks_for("start", ROOT / "tmp" / "fake-sandbox", 12)
        resolve.assert_called_once_with()
        self.assertEqual(hook.executable, str(fake_wrapper))
        self.assertEqual(hook.timeout, 12)

    def test_status_never_resolves_or_launches_wrapper(self):
        with patch("development.cli.pinned_codex_executable") as resolve:
            hook = codex_hooks_for("status", ROOT / "tmp" / "fake-sandbox", 12)
        resolve.assert_not_called()
        self.assertEqual(hook.executable, "codex")

    def test_pinned_path_from_localappdata(self):
        local = ROOT / "tmp" / "fake-localapp"
        expected = local / PINNED_WRAPPER_RELATIVE
        with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}), \
                patch.object(Path, "is_file", return_value=True):
            self.assertEqual(pinned_codex_executable(), expected.resolve())

    def test_doctor_spec_is_complete_and_has_no_open_questions(self):
        spec = (ROOT / "config" / "development" / "doctor-common-spec.md").read_text(encoding="utf-8")
        task = (ROOT / "config" / "development" / "doctor-common-task.txt").read_text(encoding="utf-8")
        valid, reason = check_spec_open_questions(spec)
        self.assertTrue(valid, reason)
        self.assertIn("## Objetivo", spec)
        self.assertIn("## Comportamento e critérios de aceite", spec)
        self.assertIn("do not create or edit", task)


if __name__ == "__main__":
    unittest.main()
