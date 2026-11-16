"""SQLite-only deterministic approval exercise. Never a real-work authority."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .approval_contract import canonical_bytes, digest, issue, validate

DOMAIN = b"workspace-approval-mock-v1\0"
ROOT = Path(__file__).resolve().parents[3]


class ApprovalDenied(ValueError):
    pass


class MockVerifier:
    """Public deterministic proof: deliberately forgeable and test-only."""

    @staticmethod
    def proof(payload: dict[str, Any]) -> str:
        validate(payload)
        return hashlib.sha256(DOMAIN + canonical_bytes(payload)).hexdigest()

    @classmethod
    def verify(cls, payload: dict[str, Any], proof: str) -> bool:
        return isinstance(proof, str) and hmac.compare_digest(cls.proof(payload), proof)


class MockApprovalStore:
    def __init__(self, database: Path, now: Callable[[], datetime] | None = None):
        self.database = database
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _connect(self, *, create: bool = False) -> sqlite3.Connection:
        if not create and not self.database.is_file():
            raise ApprovalDenied("mock store unavailable")
        try:
            conn = sqlite3.connect(self.database, timeout=2, isolation_level=None)
            conn.execute("PRAGMA busy_timeout=2000")
            conn.execute("PRAGMA foreign_keys=ON")
            if create:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS challenges (
                        nonce TEXT PRIMARY KEY CHECK(length(nonce)=64),
                        thread_id TEXT NOT NULL, stage TEXT NOT NULL CHECK(stage='work'),
                        attempt INTEGER NOT NULL CHECK(attempt=1),
                        payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL UNIQUE,
                        issued_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                        state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','consumed')),
                        consumed_at TEXT,
                        UNIQUE(thread_id, stage, attempt)
                    );
                    CREATE INDEX IF NOT EXISTS challenges_expiry ON challenges(state, expires_at);
                    CREATE TABLE IF NOT EXISTS approvals (
                        nonce TEXT PRIMARY KEY REFERENCES challenges(nonce),
                        payload_sha256 TEXT NOT NULL UNIQUE,
                        verifier_kind TEXT NOT NULL CHECK(verifier_kind='mock'),
                        consumed_at TEXT NOT NULL
                    );
                """)
            return conn
        except sqlite3.Error as exc:
            raise ApprovalDenied("mock store unavailable") from exc

    def request(self, fields: dict[str, Any], *, ttl_seconds: int = 120) -> dict[str, Any]:
        payload = issue(fields, secrets.token_hex(32), self.now(), ttl_seconds)
        raw = canonical_bytes(payload).decode("utf-8")
        try:
            with closing(self._connect(create=True)) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO challenges(nonce,thread_id,stage,attempt,payload,payload_sha256,issued_at,expires_at) "
                             "VALUES(?,?,?,?,?,?,?,?)",
                             (payload["nonce"], payload["thread_id"], payload["stage"], payload["attempt"],
                              raw, digest(payload), payload["issued_at"], payload["expires_at"]))
                conn.execute("COMMIT")
        except sqlite3.Error as exc:
            raise ApprovalDenied("mock request denied") from exc
        return {"payload": payload, "mock_proof": MockVerifier.proof(payload),
                "usable_for_real_work": False}

    def status(self, nonce: str) -> dict[str, Any]:
        try:
            with closing(self._connect()) as conn:
                row = conn.execute("SELECT state,expires_at FROM challenges WHERE nonce=?", (nonce,)).fetchone()
        except sqlite3.Error as exc:
            raise ApprovalDenied("mock store unavailable") from exc
        if row is None:
            raise ApprovalDenied("challenge not found")
        state = "expired" if row[0] == "pending" and datetime.fromisoformat(row[1]) <= self.now() else row[0]
        return {"state": state, "mock_only": True, "usable_for_real_work": False}

    def consume(self, payload: dict[str, Any], proof: str, *, fail_before_commit: bool = False) -> dict[str, Any]:
        validate(payload)
        if not MockVerifier.verify(payload, proof):
            raise ApprovalDenied("mock proof invalid")
        raw = canonical_bytes(payload).decode("utf-8")
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT payload,payload_sha256,state FROM challenges WHERE nonce=?",
                                   (payload["nonce"],)).fetchone()
                now = self.now().astimezone(timezone.utc)
                if (row is None or row[0] != raw or row[1] != digest(payload) or
                        row[2] != "pending" or
                        not (datetime.fromisoformat(payload["issued_at"]) <= now <
                             datetime.fromisoformat(payload["expires_at"]))):
                    raise ApprovalDenied("challenge mismatch, expired or already consumed")
                timestamp = now.isoformat()
                updated = conn.execute("UPDATE challenges SET state='consumed',consumed_at=? "
                                       "WHERE nonce=? AND state='pending'", (timestamp, payload["nonce"]))
                if updated.rowcount != 1:
                    raise ApprovalDenied("challenge already consumed")
                conn.execute("INSERT INTO approvals(nonce,payload_sha256,verifier_kind,consumed_at) "
                             "VALUES(?,?,?,?)", (payload["nonce"], digest(payload), "mock", timestamp))
                if fail_before_commit:
                    raise RuntimeError("simulated crash before commit")
                conn.execute("COMMIT")
        except sqlite3.Error as exc:
            raise ApprovalDenied("mock store unavailable") from exc
        return {"state": "consumed", "mock_only": True, "usable_for_real_work": False,
                "payload_sha256": digest(payload)}


def _safe_mock_db(path: Path) -> Path:
    raw_base = ROOT / "tmp" / "approval-mock"
    if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
           for p in (ROOT / "tmp", raw_base, path)):
        raise ApprovalDenied("mock DB link is forbidden")
    base = raw_base.resolve()
    resolved = path.resolve()
    if resolved.parent != base or resolved.suffix != ".sqlite3":
        raise ApprovalDenied("mock DB must be inside Workspace tmp/approval-mock")
    base.mkdir(parents=True, exist_ok=True)
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulation-only approval mock")
    parser.add_argument("action", choices=("request", "status", "consume"))
    parser.add_argument("--mode", choices=("mock",), required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--nonce")
    parser.add_argument("--proof")
    args = parser.parse_args(argv)
    try:
        store = MockApprovalStore(_safe_mock_db(args.db))
        if args.action == "request":
            if not args.input:
                raise ApprovalDenied("request input required")
            result = store.request(json.loads(args.input.read_text(encoding="utf-8")))
        elif args.action == "status":
            if not args.nonce:
                raise ApprovalDenied("nonce required")
            result = store.status(args.nonce)
        else:
            if not args.input or not args.proof:
                raise ApprovalDenied("payload and mock proof required")
            result = store.consume(json.loads(args.input.read_text(encoding="utf-8")), args.proof)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ApprovalDenied, OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"error": {"code": "MOCK_APPROVAL_DENIED", "message": str(exc)}}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
