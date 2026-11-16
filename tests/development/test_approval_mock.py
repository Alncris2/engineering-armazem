import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
from development.approval_contract import canonical_bytes, digest
from development.approval_mock import ApprovalDenied, MockApprovalStore, MockVerifier

BASE = ROOT / "tmp" / "approval-mock"


class ApprovalMockTests(unittest.TestCase):
    def setUp(self):
        self.folder = BASE / f"test-{uuid.uuid4().hex}"
        self.folder.mkdir(parents=True)
        self.addCleanup(self.cleanup)
        self.database = self.folder / "mock.sqlite3"
        self.clock = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
        self.store = MockApprovalStore(self.database, now=lambda: self.clock)
        self.thread = "new-test-" + uuid.uuid4().hex
        self.fields = {
            "thread_id": self.thread, "issue_key": "LOCAL-1", "stage": "work", "attempt": 1,
            "plan_sha256": "a" * 64, "spec_sha256": "b" * 64,
            "repo": f"C:\\htdocs\\ai-engineering-workspace\\tmp\\development-sandboxes\\{self.thread}\\example-repo",
            "head": "c" * 40, "inventory_sha256": "d" * 64,
            "allowlist": ["src/module.py"], "target_module": "src/module.py",
        }

    def cleanup(self):
        target = self.folder.resolve()
        if target.parent != BASE.resolve() or not target.name.startswith("test-"):
            raise ValueError("unsafe test cleanup")
        shutil.rmtree(target)

    def test_request_status_consume_and_replay(self):
        receipt = self.store.request(self.fields)
        payload = receipt["payload"]
        self.assertFalse(receipt["usable_for_real_work"])
        self.assertEqual(self.store.status(payload["nonce"])["state"], "pending")
        consumed = self.store.consume(payload, receipt["mock_proof"])
        self.assertEqual(consumed["state"], "consumed")
        self.assertFalse(consumed["usable_for_real_work"])
        self.assertEqual(self.store.status(payload["nonce"])["state"], "consumed")
        with self.assertRaises(ApprovalDenied):
            self.store.consume(payload, receipt["mock_proof"])
        with self.assertRaises(ApprovalDenied):
            self.store.request(self.fields)

    def test_field_swap_even_with_recomputed_mock_proof_fails(self):
        payload = self.store.request(self.fields)["payload"]
        for key, value in (("issue_key", "LOCAL-2"), ("spec_sha256", "e" * 64),
                           ("head", "f" * 40), ("target_module", "src/other.py")):
            swapped = {**payload, key: value}
            if key == "target_module":
                swapped["allowlist"] = [value]
            with self.subTest(key=key), self.assertRaises(ApprovalDenied):
                self.store.consume(swapped, MockVerifier.proof(swapped))

    def test_expiry_and_invalid_contract(self):
        receipt = self.store.request(self.fields, ttl_seconds=2)
        self.clock += timedelta(seconds=2)
        self.assertEqual(self.store.status(receipt["payload"]["nonce"])["state"], "expired")
        with self.assertRaises(ApprovalDenied):
            self.store.consume(receipt["payload"], receipt["mock_proof"])
        for bad in ({**self.fields, "stage": "review"},
                    {**self.fields, "attempt": 2},
                    {**self.fields, "repo": "C:\\product\\repo"},
                    {**self.fields, "repo": self.fields["repo"].lower()},
                    {**self.fields, "allowlist": ["src/module.py", "src/other.py"]}):
            with self.assertRaises(ValueError):
                self.store.request(bad)

    def test_boolean_version_cannot_pass_contract_validation(self):
        payload = self.store.request(self.fields)["payload"]
        with self.assertRaises(ValueError):
            digest({**payload, "version": True})

    def test_two_consumers_one_wins(self):
        receipt = self.store.request(self.fields)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            calls = [pool.submit(self.store.consume, receipt["payload"], receipt["mock_proof"])
                     for _ in range(2)]
            outcomes = [call.exception() or call.result() for call in calls]
        self.assertEqual(sum(isinstance(x, dict) for x in outcomes), 1)
        self.assertEqual(sum(isinstance(x, ApprovalDenied) for x in outcomes), 1)

    def test_consume_uses_one_instant_for_expiry_and_timestamp(self):
        receipt = self.store.request(self.fields, ttl_seconds=2)
        calls = []
        def advancing_clock():
            calls.append(None)
            return self.clock + timedelta(seconds=len(calls))
        self.store.now = advancing_clock
        self.assertEqual(self.store.consume(receipt["payload"], receipt["mock_proof"])["state"],
                         "consumed")
        self.assertEqual(len(calls), 1)
        with closing(self.store._connect()) as conn:
            consumed_at = conn.execute("SELECT consumed_at FROM approvals WHERE nonce=?",
                                       (receipt["payload"]["nonce"],)).fetchone()[0]
        self.assertEqual(consumed_at, (self.clock + timedelta(seconds=1)).isoformat())

    def test_crash_rolls_back_and_database_failure_denies(self):
        receipt = self.store.request(self.fields)
        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            self.store.consume(receipt["payload"], receipt["mock_proof"], fail_before_commit=True)
        self.assertEqual(self.store.status(receipt["payload"]["nonce"])["state"], "pending")
        self.assertEqual(self.store.consume(receipt["payload"], receipt["mock_proof"])["state"], "consumed")
        unavailable = MockApprovalStore(self.folder / "missing" / "db.sqlite3", now=lambda: self.clock)
        with self.assertRaises(ApprovalDenied):
            unavailable.status(receipt["payload"]["nonce"])
        with self.assertRaises(ApprovalDenied):
            unavailable.consume(receipt["payload"], receipt["mock_proof"])

    def test_canonical_hash_stable_and_cli_mock_only(self):
        receipt = self.store.request(self.fields)
        payload = receipt["payload"]
        self.assertEqual(digest(payload), digest(dict(reversed(list(payload.items())))))
        self.assertEqual(json.loads(canonical_bytes(payload)), payload)
        cmd = [sys.executable, "workspace.py", "--json", "development", "start",
               "--thread", self.thread, "--issue", "LOCAL-1", "--stage", "work"]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CODEX_STAGE_DISABLED", result.stdout)

    def test_local_cli_request_status_consume(self):
        database = BASE / f"cli-{uuid.uuid4().hex}.sqlite3"
        self.addCleanup(lambda: database.unlink(missing_ok=True)
                        if database.resolve().parent == BASE.resolve() and database.name.startswith("cli-")
                        else None)
        request_file = self.folder / "request.json"
        payload_file = self.folder / "payload.json"
        request_file.write_text(json.dumps(self.fields), encoding="utf-8")
        common = [sys.executable, "-m", "development.approval_mock"]
        cwd = ROOT / "services" / "orchestrator"
        def run(*args):
            result = subprocess.run([*common, *args, "--mode", "mock", "--db", str(database)],
                                    cwd=cwd, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return json.loads(result.stdout)
        receipt = run("request", "--input", str(request_file))
        payload = receipt["payload"]
        payload_file.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(run("status", "--nonce", payload["nonce"])["state"], "pending")
        self.assertEqual(run("consume", "--input", str(payload_file),
                             "--proof", receipt["mock_proof"])["state"], "consumed")
        self.assertEqual(run("status", "--nonce", payload["nonce"])["state"], "consumed")


class MigrationIsolationTests(unittest.TestCase):
    def test_laravel_migration_on_in_memory_sqlite(self):
        api = ROOT / "apps" / "control-api"
        env = os.environ.copy()
        env.update({"DB_CONNECTION": "sqlite", "DB_DATABASE": ":memory:",
                    "CACHE_STORE": "array", "SESSION_DRIVER": "array", "QUEUE_CONNECTION": "sync"})
        result = subprocess.run(["php", "artisan", "migrate", "--database=sqlite", "--force", "--no-ansi"],
                                cwd=api, env=env, capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertIn("create_work_approval_contract", result.stdout)
