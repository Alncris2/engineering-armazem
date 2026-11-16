import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import workspace


class RootCliFailureTests(unittest.TestCase):
    def test_real_work_and_review_are_rejected_before_database_or_executor(self):
        for stage in ("work", "review"):
            with self.subTest(stage=stage), patch("workspace.run", wraps=workspace.run), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                code = workspace.main(["--json", "development", "start", "--thread", "never-launch",
                                       "--issue", "LOCAL-1", "--executor", "codex", "--stage", stage])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["error"]["code"], "CODEX_STAGE_DISABLED")

    def test_nonzero_child_preserves_safe_thread_and_status(self):
        thread = "fake-thread-1"
        child = {"thread_id": thread, "executor": "codex", "status": "held",
                 "gates": {"plan": {"passed": False, "reason": "executor did not succeed", "attempt": 1}},
                 "error": {"code": "CODEX_EXEC_INCONCLUSIVE", "message": "Codex plan did not pass its gate"}}
        completed = subprocess.CompletedProcess([], 2, stdout=json.dumps(child), stderr="SECRET_FAKE_MARKER_DO_NOT_PERSIST")
        with patch("workspace.subprocess.run", return_value=completed):
            with self.assertRaises(workspace.CliError) as caught:
                workspace.subprocess_json(["fake"], Path.cwd(), 3)
        self.assertEqual(caught.exception.code, "CODEX_EXEC_INCONCLUSIVE")
        self.assertEqual(caught.exception.data["thread_id"], thread)
        with patch("workspace.run", side_effect=caught.exception), contextlib.redirect_stdout(io.StringIO()) as output:
            exit_code = workspace.main(["--json", "development", "status", "--thread", thread])
        envelope = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(envelope["data"]["status"], "held")
        self.assertEqual(envelope["error"]["code"], "CODEX_EXEC_INCONCLUSIVE")
        self.assertNotIn("SECRET_FAKE_MARKER_DO_NOT_PERSIST", output.getvalue())


if __name__ == "__main__":
    unittest.main()
