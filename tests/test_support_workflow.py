import json
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from services.orchestrator.workflow import ROOT, WorkflowError, archived_run


class SupportWorkflowTest(unittest.TestCase):
    @contextmanager
    def temporary(self):
        directory = ROOT / "tmp"
        directory.mkdir(exist_ok=True)
        target = directory / ("workflow-test-" + uuid.uuid4().hex)
        target.mkdir()
        try:
            yield str(target)
        finally:
            if target.resolve().parent != directory.resolve():
                raise RuntimeError("Test folder escaped the Workspace tmp directory")
            shutil.rmtree(target)

    def test_archived_run_requires_completed_final_step(self):
        with self.temporary() as temporary:
            root = Path(temporary)
            folder = root / "squads" / "webagil-dev" / "output" / "run-1"
            folder.mkdir(parents=True)
            state = {"runId": "run-1", "squad": "webagil-dev", "pipelineId": "support",
                     "status": "completed", "completedAt": "2026-11-13T10:00:00Z",
                     "step": {"current": 5, "total": 5}}
            (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (folder / "report.md").write_text("report", encoding="utf-8")
            self.assertEqual(2, archived_run(root, "run-1"))
            state["step"]["current"] = 4
            (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(WorkflowError) as caught:
                archived_run(root, "run-1")
            self.assertEqual("GATE_UNCONFIRMED", caught.exception.code)

    def test_run_id_cannot_escape_archive(self):
        with self.temporary() as temporary:
            with self.assertRaises(WorkflowError) as caught:
                archived_run(Path(temporary), "../outside")
            self.assertEqual("INVALID_SOURCE_RUN", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
