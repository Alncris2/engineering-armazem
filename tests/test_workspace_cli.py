import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch

import workspace


class WorkspaceCliTest(unittest.TestCase):
    def capture(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = workspace.main(args)
        return code, json.loads(stdout.getvalue()), json.loads(stderr.getvalue())

    def test_rejects_non_loopback_api_before_request(self):
        code, response, log = self.capture(["--api", "https://example.com", "projects", "list", "--json"])
        self.assertEqual(1, code)
        self.assertEqual("INVALID_API_URL", response["error"]["code"])
        self.assertEqual("error", log["level"])

    def test_projects_list_has_standard_envelope_and_structured_log(self):
        with patch("workspace.api_request", return_value=[{"id": "1", "slug": "webagil"}]):
            code, response, log = self.capture(["projects", "list", "--json"])
        self.assertEqual(0, code)
        self.assertEqual("webagil", response["data"][0]["slug"])
        self.assertIsNone(response["error"])
        self.assertEqual("projects.list", log["operation"])

    def test_external_failure_preserves_error_code(self):
        failed = subprocess.CompletedProcess([], 1, '{"error":{"code":"CONCURRENT_RUN","message":"Busy"}}', '')
        with patch("workspace.subprocess.run", return_value=failed):
            with self.assertRaises(workspace.CliError) as caught:
                workspace.subprocess_json(["external"], workspace.ROOT, 1)
        self.assertEqual("CONCURRENT_RUN", caught.exception.code)

    def test_development_parser_selects_codex_without_simulation_scenario(self):
        args = workspace.parser().parse_args([
            "development", "start", "--thread", "local-plan-1", "--issue", "LOCAL-1",
            "--executor", "codex", "--task-file", "config/development/task.txt",
        ])
        self.assertEqual(args.executor, "codex")
        self.assertIsNone(args.scenario)
        self.assertEqual(args.task_file, "config/development/task.txt")


if __name__ == "__main__":
    unittest.main()
