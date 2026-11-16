import io
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "orchestrator"))
from development.codex_cli import (CodexPlanHooks, InvocationResult, MAX_EVENT_BYTES,
                                   OutputLimitError, _diagnostic, _invoke_bounded)
from development.graph import build_graph


BASE = Path(__file__).resolve().parents[2] / "tmp" / "codex-hook-tests"
THREAD_ID = "codex-test"
UUID = "01a1d5db-f0d7-75a1-8361-f0ee4a7824c1"


class FakeProcess:
    returncode = 0
    def __init__(self, events):
        payload = "\n".join(json.dumps(event) if isinstance(event, dict) else event
                            for event in events).encode("utf-8")
        self.stdin = io.BytesIO()
        self.stdout = io.BufferedReader(io.BytesIO(payload))
        self.stderr = io.BufferedReader(io.BytesIO(b""))
    def poll(self):
        return self.returncode


class FailedProcess(FakeProcess):
    returncode = 1
    def __init__(self, events, stderr):
        super().__init__(events)
        self.stderr = io.BufferedReader(io.BytesIO(stderr))


class TimeoutProcess:
    pid = 43210
    returncode = None
    def __init__(self):
        self.killed = False
        self.wait_timeouts = []
        self.stdin = io.BytesIO()
        self.stdout = io.BufferedReader(io.BytesIO(b""))
        self.stderr = io.BufferedReader(io.BytesIO(b""))
    def poll(self):
        return self.returncode
    def kill(self):
        self.killed = True
    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        self.returncode = -9
        return self.returncode


class CodexHookTests(unittest.TestCase):
    def setUp(self):
        self.root = BASE / f"run-{uuid.uuid4().hex} with spaces"
        self.root.mkdir(parents=True)
        self.addCleanup(self.cleanup)
        self.sandbox = self.root / "development-sandboxes" / THREAD_ID
        self.sandbox.mkdir(parents=True)
        self.hook = CodexPlanHooks(codex_root=self.sandbox, timeout=10)
        self.state = {"thread_id": THREAD_ID, "issue_key": "TEST-1",
                      "workspace_root": str(self.root),
                      "artifact_dir": str(self.root / "development-runs" / THREAD_ID),
                      "task_text": "Explain a local validation task.", "executor": "codex",
                      "shutdown_after": "plan"}

    def cleanup(self):
        target = self.root.resolve()
        if target.parent != BASE.resolve() or not target.name.startswith("run-"):
            raise ValueError("unsafe test cleanup path")
        for attempt in range(3):
            try:
                shutil.rmtree(target)
                return
            except OSError as exc:
                if getattr(exc, "winerror", None) != 145 or attempt == 2:
                    raise
                time.sleep(0.1)

    def fake(self, text, *, extra=(), complete=True):
        events = [{"type": "thread.started", "thread_id": UUID},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": text}}]
        if complete:
            events.append({"type": "turn.completed"})
        events.extend(extra)
        return lambda *args, **kwargs: FakeProcess(events)

    def test_graph_plan_is_read_only_and_holds_after_spec_gate(self):
        graph = build_graph(self.hook, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": THREAD_ID}}
        plan = "# Spec\n\n## Objetivo\n\nValidate locally.\n\n## Open Questions\n\nNenhuma."
        with patch("development.codex_cli.subprocess.Popen", side_effect=self.fake(plan)) as launch:
            graph.invoke(self.state, config)
        snap = graph.get_state(config)
        self.assertEqual(snap.values["status"], "held")
        self.assertTrue(snap.values["gates"]["plan"]["passed"])
        self.assertEqual(snap.values["attempts"]["plan"], 1)
        self.assertNotIn("work", snap.values["attempts"])
        self.assertIn("--sandbox", launch.call_args.args[0])
        self.assertIn("read-only", launch.call_args.args[0])
        receipt = snap.values["results"]["plan"]
        self.assertEqual(receipt["codex_thread_id"], UUID)
        self.assertFalse(receipt["session_resumable"])
        with patch("development.codex_cli.subprocess.Popen") as no_launch:
            self.assertEqual(self.hook.run("plan", self.state, "codex-test:plan:1"), receipt)
        no_launch.assert_not_called()

    def test_open_question_blocks_spec_gate(self):
        graph = build_graph(self.hook, checkpointer=InMemorySaver())
        plan = "# Spec\n\n## Objetivo\n\nValidate locally.\n\n## Open Questions\n\n- Who approves?"
        with patch("development.codex_cli.subprocess.Popen", side_effect=self.fake(plan)):
            graph.invoke(self.state, {"configurable": {"thread_id": THREAD_ID}})
        snap = graph.get_state({"configurable": {"thread_id": THREAD_ID}})
        self.assertFalse(snap.values["gates"]["plan"]["passed"])
        self.assertNotIn("plan_record", snap.values)

    def test_failed_cli_writes_redacted_diagnostic_and_preserves_pending(self):
        secret = "SECRET_FAKE_MARKER_DO_NOT_PERSIST"
        events = [{"type": "thread.started", "thread_id": UUID},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": secret}}]
        graph = build_graph(self.hook, checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": THREAD_ID}}
        with patch("development.codex_cli.subprocess.Popen",
                   return_value=FailedProcess(events, ("permission denied " + secret).encode())):
            graph.invoke(self.state, config)
        snap = graph.get_state(config)
        self.assertEqual(snap.values["status"], "held")
        self.assertFalse(snap.values["gates"]["plan"]["passed"])
        folder = Path(self.state["artifact_dir"])
        diagnostic_text = (folder / "diagnostic.json").read_text(encoding="utf-8")
        diagnostic = json.loads(diagnostic_text)
        self.assertEqual(diagnostic["category"], "permission")
        self.assertEqual(diagnostic["exit_code"], 1)
        self.assertEqual(diagnostic["event_counts"]["thread.started"], 1)
        self.assertEqual(diagnostic["event_counts"]["turn.completed"], 0)
        self.assertLess(len(diagnostic_text), 2048)
        self.assertNotIn(secret, diagnostic_text)
        self.assertEqual(json.loads((folder / "codex-plan-receipt.json").read_text())["status"], "pending")
        self.assertTrue((folder / "codex-plan.lock").exists())
        self.assertFalse((folder / "plan-1.txt").exists())
        with patch("development.codex_cli.subprocess.Popen") as no_launch:
            with self.assertRaisesRegex(RuntimeError, "reconcile"):
                self.hook.run("plan", self.state, "codex-test:plan:1")
        no_launch.assert_not_called()

    def test_unknown_diagnostic_never_embeds_unclassified_text(self):
        secret = b"SECRET_FAKE_UNKNOWN_MARKER"
        record = _diagnostic(InvocationResult(b'{"type":"untrusted.kind","text":"SECRET_FAKE_UNKNOWN_MARKER"}\n',
                                              secret, 1, "2026-11-13T00:00:00+00:00",
                                              "2026-11-13T00:00:01+00:00"))
        self.assertEqual(record["category"], "unknown")
        self.assertEqual(record["unknown_events"], 1)
        self.assertNotIn(secret.decode(), json.dumps(record))

    def test_incomplete_event_stream_is_inconclusive_and_not_relaunched(self):
        with patch("development.codex_cli.subprocess.Popen", side_effect=self.fake("# Spec", complete=False)):
            with self.assertRaisesRegex(ValueError, "inconclusive"):
                self.hook.run("plan", self.state, "codex-test:plan:1")
        with patch("development.codex_cli.subprocess.Popen") as no_launch:
            with self.assertRaisesRegex(RuntimeError, "reconcile"):
                self.hook.run("plan", self.state, "codex-test:plan:1")
        no_launch.assert_not_called()

    def test_rejects_cross_thread_artifact_location(self):
        self.state["artifact_dir"] = str(self.root / "development-runs" / "other")
        with patch("development.codex_cli.subprocess.Popen") as no_launch:
            with self.assertRaisesRegex(ValueError, "unexpected artifact"):
                self.hook.run("plan", self.state, "codex-test:plan:1")
        no_launch.assert_not_called()

    def test_existing_atomic_lock_blocks_duplicate_launch(self):
        folder = Path(self.state["artifact_dir"])
        folder.mkdir(parents=True)
        (folder / "codex-plan.lock").write_text("claimed", encoding="utf-8")
        with patch("development.codex_cli.subprocess.Popen") as no_launch:
            with self.assertRaisesRegex(RuntimeError, "lock exists"):
                self.hook.run("plan", self.state, "codex-test:plan:1")
        no_launch.assert_not_called()

    def test_other_stage_fails_closed(self):
        with patch("development.codex_cli.subprocess.Popen") as no_launch:
            with self.assertRaisesRegex(ValueError, "only the read-only plan"):
                self.hook.run("work", self.state, "codex-test:work:1")
        no_launch.assert_not_called()

    def test_graph_direct_work_entry_fails_closed(self):
        graph = build_graph(self.hook, checkpointer=InMemorySaver())
        with patch("development.codex_cli.subprocess.Popen") as no_launch:
            result = graph.invoke(dict(self.state, codex_stage="work"),
                                  {"configurable": {"thread_id": THREAD_ID}})
        self.assertEqual(result["status"], "failed")
        self.assertIn("disabled", result["failure"])
        no_launch.assert_not_called()

    def test_timeout_with_taskkill_failure_is_bounded_and_inconclusive(self):
        process = TimeoutProcess()
        self.hook.timeout = 0.05
        with patch("development.codex_cli.subprocess.Popen", return_value=process), \
                patch("development.codex_cli.subprocess.run",
                      return_value=subprocess.CompletedProcess([], 1)) as taskkill:
            with self.assertRaisesRegex(RuntimeError, "inconclusive"):
                self.hook.run("plan", self.state, "codex-test:plan:1")
        if os.name == "nt":
            self.assertEqual(taskkill.call_args.args[0][:2], ["taskkill", "/PID"])
        self.assertTrue(process.killed)
        self.assertEqual(process.wait_timeouts, [5])
        receipt = json.loads((Path(self.state["artifact_dir"]) / "codex-plan-receipt.json").read_text())
        self.assertEqual(receipt["status"], "pending")

    def test_malformed_event_line_is_inconclusive(self):
        with patch("development.codex_cli.subprocess.Popen",
                   side_effect=self.fake("# Spec", extra=("{bad-json",))):
            with self.assertRaisesRegex(ValueError, "malformed"):
                self.hook.run("plan", self.state, "codex-test:plan:1")

    def test_failure_after_completed_is_inconclusive(self):
        with patch("development.codex_cli.subprocess.Popen",
                   side_effect=self.fake("# Spec", extra=({"type": "turn.failed"},))):
            with self.assertRaisesRegex(ValueError, "inconclusive"):
                self.hook.run("plan", self.state, "codex-test:plan:1")

    def test_oversized_event_stream_is_inconclusive(self):
        with patch("development.codex_cli.subprocess.Popen",
                   side_effect=self.fake("x" * MAX_EVENT_BYTES)):
            with self.assertRaisesRegex(RuntimeError, "capture limit"):
                self.hook.run("plan", self.state, "codex-test:plan:1")

    def test_local_continuous_output_stops_at_byte_limit(self):
        script = ("import sys,time\n"
                  "while True:\n"
                  " sys.stdout.buffer.write(b'x'*8192); sys.stdout.flush()\n"
                  " sys.stderr.buffer.write(b'y'*8192); sys.stderr.flush()\n"
                  " time.sleep(0.001)\n")
        started = time.monotonic()
        with self.assertRaises(OutputLimitError) as caught:
            _invoke_bounded([sys.executable, "-u", "-c", script], "", timeout=8)
        self.assertLess(time.monotonic() - started, 8)
        self.assertLessEqual(caught.exception.stdout_bytes, MAX_EVENT_BYTES)
        self.assertLessEqual(caught.exception.stderr_bytes, MAX_EVENT_BYTES)
        self.assertGreater(max(caught.exception.stdout_bytes, caught.exception.stderr_bytes),
                           MAX_EVENT_BYTES // 2)

    @unittest.skipUnless(os.environ.get("DEVELOPMENT_CHECKPOINT_DSN"), "no test PostgreSQL DSN")
    def test_postgres_checkpoint_reopens_in_new_cli_process(self):
        thread = "codex-pg-" + uuid.uuid4().hex[:12]
        sandbox = self.root / "development-sandboxes" / thread
        sandbox.mkdir(parents=True)
        hook = CodexPlanHooks(codex_root=sandbox, timeout=10)
        state = dict(self.state, thread_id=thread,
                     artifact_dir=str(self.root / "development-runs" / thread))
        plan = "# Spec\n\n## Objetivo\n\nValidate locally.\n\n## Open Questions\n\nNenhuma."
        dsn = os.environ["DEVELOPMENT_CHECKPOINT_DSN"]
        with psycopg.connect(dsn, autocommit=True) as connection:
            saver = PostgresSaver(connection)
            saver.setup()
            graph = build_graph(hook, checkpointer=saver)
            with patch("development.codex_cli.subprocess.Popen", side_effect=self.fake(plan)):
                graph.invoke(state, {"configurable": {"thread_id": thread}})
        repository = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, str(repository / "workspace.py"), "--json",
                                 "development", "status", "--thread", thread],
                                cwd=repository, capture_output=True, text=True, encoding="utf-8",
                                timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["data"]
        self.assertEqual(output["status"], "held")
        self.assertEqual(output["executor"], "codex")
        self.assertTrue(output["gates"]["plan"]["passed"])
