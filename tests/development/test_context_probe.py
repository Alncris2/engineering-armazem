"""Fake-only checks for the external PowerShell Codex probe."""

import json
import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
from development.codex_cli import InvocationResult
from development.context_probe import EXPECTED_WRAPPER, claim_once, run_probe


class ContextProbeTests(unittest.TestCase):
    def invoke_fake(self, outcome):
        script = ROOT / "scripts" / "windows" / "probe-codex-context.ps1"
        proc = subprocess.run(["pwsh", "-NoProfile", "-File", str(script),
                               "-Mode", "Fake", "-FakeOutcome", outcome,
                               "-TimeoutSeconds", "5"],
                              cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", timeout=20)
        data = json.loads(proc.stdout.strip())
        self.assertNotIn("FAKE_SECRET_MARKER", proc.stdout)
        self.assertNotIn("PROBE_OK", proc.stdout)
        self.assertNotIn(str(ROOT), proc.stdout)
        self.assertEqual(data["context"]["executed_executable_kind"], "fake_python")
        self.assertTrue(data["context"]["sandbox_empty_before"])
        return proc, data

    def test_fake_success_reports_only_normalized_evidence(self):
        proc, data = self.invoke_fake("Success")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(data["status"], "passed")
        self.assertEqual(data["diagnostic"]["exit_code"], 0)
        self.assertEqual(data["diagnostic"]["event_counts"]["thread.started"], 1)
        self.assertEqual(data["diagnostic"]["event_counts"]["turn.completed"], 1)

    def test_fake_permission_is_sanitized_and_nonzero(self):
        proc, data = self.invoke_fake("Permission")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["diagnostic"]["exit_code"], 1)
        self.assertEqual(data["diagnostic"]["category"], "permission")
        self.assertGreater(data["diagnostic"]["stderr_bytes"], 0)
        self.assertEqual(data["diagnostic"]["stdout_bytes"], 0)

    def test_persistent_claim_prevents_second_call(self):
        base = ROOT / "tmp"
        folder = base / ("codex-claim-test-" + uuid.uuid4().hex)
        folder.mkdir()
        try:
            marker = folder / "once.lock"
            self.assertTrue(claim_once(marker))
            self.assertFalse(claim_once(marker))
        finally:
            self.assertEqual(folder.resolve().parent, base.resolve())
            marker.unlink(missing_ok=True)
            folder.rmdir()

    def test_real_mode_pins_wrapper_even_when_path_resolves_elsewhere(self):
        local = ROOT / "tmp" / "fake-localapp"
        expected = local / EXPECTED_WRAPPER
        events = [
            {"type": "thread.started", "thread_id": "01a1d5db-f0d7-75a1-8361-f0ee4a7824c1"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "PROBE_OK"}},
            {"type": "turn.completed"},
        ]
        stdout = "\n".join(json.dumps(event) for event in events).encode()
        fake_result = InvocationResult(stdout, b"", 0, "start", "finish")
        with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}), \
                patch("development.context_probe.shutil.which", return_value=None), \
                patch.object(Path, "is_file", return_value=True), \
                patch("development.context_probe.claim_once", return_value=True), \
                patch("development.context_probe.tempfile.mkdtemp", return_value=str(ROOT / "tmp" / "fake-exclusive")), \
                patch("development.context_probe._invoke_bounded", return_value=fake_result) as invoke:
            result = run_probe(ROOT, "real", "success", 5)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["context"]["resolved_executable_kind"], "other_or_missing")
        self.assertEqual(result["context"]["executed_executable_kind"], "pinned_nvm_codex_cmd")
        self.assertEqual(invoke.call_args.args[0][0], str(expected))


if __name__ == "__main__":
    unittest.main()
