import os
import sys
import shutil
import uuid
import unittest
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "orchestrator"))
from development.graph import build_graph, gate_result
from development.git_cli import snapshot as git_snapshot
from development.simulation import ScenarioHooks


TMP_BASE = Path(__file__).resolve().parents[2] / "tmp" / "development-tests"


def make_test_dir():
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    path = TMP_BASE / f"test-run-{uuid.uuid4().hex}"
    path.mkdir()
    return path


def clean_test_dir(path):
    base = TMP_BASE.resolve()
    target = path.resolve()
    if target.parent != base or not target.name.startswith("test-run-"):
        raise ValueError("refusing to clean path outside development test tmp")
    shutil.rmtree(target)


def scenario(*, confidence=82, readiness=True, review_open=False):
    review = [{"id": "F1", "status": "open"}] if review_open else []
    reviews = [{"ok": True, "checks_passed": True, "findings": review}]
    if review_open:
        reviews.append({"ok": True, "checks_passed": True,
                        "findings": [{"id": "F1", "status": "closed"}]})
    return {"readiness": readiness, "confidence": confidence, "stages": {
        "plan": [{"ok": True, "plan_text": "# Spec\n\n## Objetivo\n\nImplement local change\n\n## Open Questions\n\nNenhuma."}],
        "work": [{"ok": True, "changed_files": ["src/example.py"], "checks_passed": True}],
        "simplify": [{"ok": True, "checks_passed": True}],
        "review": reviews,
        "fix": [{"ok": True, "checks_passed": True, "resolved_ids": ["F1"]}],
        "activate": [{"ok": True, "checks_passed": True, "handoff_ready": True}],
    }}


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.root = make_test_dir()
        self.addCleanup(clean_test_dir, self.root)
        self.config = {"configurable": {"thread_id": "case-1"}}

    def initial(self, **overrides):
        value = {"issue_key": "EVOLOG-1", "thread_id": "case-1",
                 "workspace_root": str(self.root), "artifact_dir": str(self.root / "runs" / "case-1")}
        value.update(overrides)
        return value

    def test_complete_with_review_fix_and_record(self):
        graph = build_graph(ScenarioHooks(scenario(review_open=True)), checkpointer=InMemorySaver())
        output = graph.invoke(self.initial(), self.config)
        self.assertEqual(output["status"], "done")
        self.assertEqual(output["attempts"]["review"], 2)
        self.assertEqual(output["attempts"]["fix"], 1)
        self.assertTrue(all(g["passed"] for g in output["gates"].values()))
        record = Path(output["plan_record"])
        self.assertTrue(record.is_file())
        before = record.read_bytes()
        graph.invoke(None, self.config)
        self.assertEqual(record.read_bytes(), before)

    def test_low_confidence_holds_then_rechecks(self):
        data = scenario(confidence=60)
        graph = build_graph(ScenarioHooks(data), checkpointer=InMemorySaver())
        graph.invoke(self.initial(), self.config)
        snap = graph.get_state(self.config)
        self.assertEqual(snap.values["status"], "held")
        self.assertEqual(snap.tasks[0].interrupts[0].value["hold"]["resume"], "run_plan")
        data["confidence"] = 80
        data["stages"]["plan"].append({"ok": True, "plan_text": "# Spec\n\n## Open Questions\n\nNenhuma."})
        graph.invoke(Command(resume={"decision": "resume"}), self.config)
        self.assertEqual(graph.get_state(self.config).values["status"], "done")

    def test_not_ready_holds_and_abort(self):
        graph = build_graph(ScenarioHooks(scenario(readiness=False)), checkpointer=InMemorySaver())
        graph.invoke(self.initial(), self.config)
        self.assertEqual(graph.get_state(self.config).values["status"], "held")
        graph.invoke(Command(resume={"decision": "abort"}), self.config)
        self.assertEqual(graph.get_state(self.config).values["status"], "aborted")

    def test_gate_retry_then_hold_at_limit(self):
        data = scenario()
        data["stages"]["work"] = [{"ok": True, "changed_files": [], "checks_passed": True}] * 2
        graph = build_graph(ScenarioHooks(data), checkpointer=InMemorySaver())
        graph.invoke(self.initial(), self.config)
        snap = graph.get_state(self.config)
        self.assertEqual(snap.values["status"], "held")
        self.assertEqual(snap.values["attempts"]["work"], 2)
        self.assertIn("work gate", snap.values["pending_hold"]["reason"])

    def test_unreadable_readiness_allows_plan_but_score_holds(self):
        graph = build_graph(ScenarioHooks(scenario(readiness=None, confidence=None)), checkpointer=InMemorySaver())
        graph.invoke(self.initial(), self.config)
        snap = graph.get_state(self.config)
        self.assertEqual(snap.values["status"], "held")
        self.assertEqual(snap.values["pending_hold"]["reason"], "confidence unreadable")
        self.assertEqual(snap.values["attempts"]["plan"], 1)

    def test_open_question_blocks_plan_approval_even_with_high_confidence(self):
        data = scenario(confidence=99)
        data["stages"]["plan"] = [{"ok": True, "plan_text": "# Spec\n\n## Open Questions\n\n- Quem aprova?"}] * 2
        graph = build_graph(ScenarioHooks(data), checkpointer=InMemorySaver())
        graph.invoke(self.initial(), self.config)
        snap = graph.get_state(self.config)
        self.assertEqual(snap.values["status"], "held")
        self.assertEqual(snap.values["attempts"]["plan"], 2)
        self.assertIn("Open Questions", snap.values["pending_hold"]["reason"])
        self.assertNotIn("plan_record", snap.values)

    def test_from_stage_rejects_missing_prerequisites(self):
        graph = build_graph(ScenarioHooks(scenario()), checkpointer=InMemorySaver())
        output = graph.invoke(self.initial(from_stage="activate"), self.config)
        self.assertEqual(output["status"], "failed")
        self.assertIn("entry artifact invalid", output["failure"])

    def test_shutdown_boundary_resumes_at_next_stage(self):
        graph = build_graph(ScenarioHooks(scenario()), checkpointer=InMemorySaver())
        graph.invoke(self.initial(shutdown_after="work"), self.config)
        snap = graph.get_state(self.config)
        self.assertEqual(snap.values["pending_hold"]["resume"], "run_simplify")
        self.assertEqual(snap.values["attempts"]["work"], 1)
        graph.invoke(Command(resume={"decision": "resume"}), self.config)
        self.assertEqual(graph.get_state(self.config).values["status"], "done")
        self.assertEqual(graph.get_state(self.config).values["attempts"]["work"], 1)

    def test_review_limit_holds_after_two_fixes(self):
        data = scenario(review_open=True)
        data["stages"]["review"] = [{"ok": True, "checks_passed": True,
                                     "findings": [{"id": "F1", "status": "open"}]}] * 3
        data["stages"]["fix"] = [{"ok": True, "checks_passed": True, "resolved_ids": ["F1"]}] * 2
        graph = build_graph(ScenarioHooks(data), checkpointer=InMemorySaver())
        graph.invoke(self.initial(), self.config)
        snap = graph.get_state(self.config)
        self.assertEqual(snap.values["status"], "held")
        self.assertEqual(snap.values["attempts"]["review"], 3)
        self.assertEqual(snap.values["attempts"]["fix"], 2)
        self.assertEqual(snap.values["pending_hold"]["reason"], "review/fix loop limit")

    def test_git_cli_receipt_is_required_in_local_mode(self):
        repo = Path(__file__).resolve().parents[2]
        observed = git_snapshot(repo)
        self.assertEqual(Path(observed["root"]), repo)
        if not observed["changed_paths"]:
            self.skipTest("working tree has no changed path")
        state = self.initial(evidence_mode="local_git", git_repo=str(repo))
        data = scenario()
        data["stages"]["work"][0]["changed_files"] = [observed["changed_paths"][0]]
        result = ScenarioHooks(data).run("work", state, "case-1:work:1")
        passed, reason = gate_result("work", state, result)
        self.assertFalse(passed)
        self.assertEqual(reason, "Git CLI receipt missing")
        result["git_snapshot"] = observed
        passed, reason = gate_result("work", state, result)
        self.assertTrue(passed, reason)


class PostgresCheckpointTest(unittest.TestCase):
    @unittest.skipUnless(os.getenv("DEVELOPMENT_CHECKPOINT_DSN"), "no test PostgreSQL DSN")
    def test_survives_new_connection_and_graph(self):
        import uuid
        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver

        directory = make_test_dir()
        try:
            thread = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread}}
            initial = {"issue_key": "EVOLOG-1", "thread_id": thread,
                       "workspace_root": str(directory), "artifact_dir": str(directory / "runs" / thread)}
            data = scenario(readiness=False)
            with psycopg.connect(os.environ["DEVELOPMENT_CHECKPOINT_DSN"], autocommit=True) as conn:
                saver = PostgresSaver(conn)
                saver.setup()
                graph = build_graph(ScenarioHooks(data), checkpointer=saver)
                graph.invoke(initial, config)
                self.assertEqual(graph.get_state(config).values["status"], "held")
            data["readiness"] = True
            with psycopg.connect(os.environ["DEVELOPMENT_CHECKPOINT_DSN"], autocommit=True) as conn:
                graph = build_graph(ScenarioHooks(data), checkpointer=PostgresSaver(conn))
                graph.invoke(Command(resume={"decision": "resume"}), config)
                self.assertEqual(graph.get_state(config).values["status"], "done")
        finally:
            clean_test_dir(directory)


if __name__ == "__main__":
    unittest.main()
