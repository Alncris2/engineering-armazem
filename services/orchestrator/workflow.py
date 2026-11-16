"""Supervised support workflow. Never starts or resumes an OpenSquad pipeline."""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "control-api"
RESOURCE = "opensquad:webagil-dev"
SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class WorkflowError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class SupportState(TypedDict, total=False):
    run_id: str
    ticket_id: str
    ticket_key: str
    project_id: str
    project_slug: str
    context_runs: int
    source_run_id: str
    approved: bool
    artifact_count: int


def log(code, operation, run_id=None, level="info"):
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "level": level,
                      "code": code, "operation": operation, "run_id": run_id}), file=sys.stderr)


def local_config():
    code = ('require "vendor/autoload.php"; $app=require "bootstrap/app.php"; '
            '$app->make(Illuminate\\Contracts\\Console\\Kernel::class)->bootstrap(); '
            'echo json_encode(["db"=>config("database.connections.pgsql"),'
            '"opensquad"=>config("workspace.opensquad_root")]);')
    result = subprocess.run(["php", "-d", "xdebug.mode=off", "-r", code], cwd=API_ROOT,
                            capture_output=True, text=True, encoding="utf-8", timeout=15,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise WorkflowError("CONFIG_UNAVAILABLE", "Laravel database configuration is unavailable")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise WorkflowError("CONFIG_INVALID", "Laravel returned an invalid database configuration") from exc


def connect(config):
    db = config["db"]
    try:
        return psycopg.connect(host=db["host"], port=db["port"], dbname=db["database"],
                               user=db["username"], password=db["password"], autocommit=True,
                               row_factory=dict_row, connect_timeout=10)
    except (KeyError, psycopg.Error) as exc:
        raise WorkflowError("POSTGRES_UNAVAILABLE", "PostgreSQL connection failed") from exc


def event(conn, run_id, key, kind, payload=None, status=None):
    with conn.transaction():
        conn.execute("SELECT id FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
        exists = conn.execute("SELECT 1 FROM run_events WHERE run_id=%s AND source_event_key=%s",
                              (run_id, key)).fetchone()
        if not exists:
            seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 AS seq FROM run_events WHERE run_id=%s",
                               (run_id,)).fetchone()["seq"]
            now = datetime.now(timezone.utc)
            conn.execute("INSERT INTO run_events (id,run_id,seq,event_type,source_event_key,payload,occurred_at,created_at,updated_at) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                         (str(uuid.uuid4()), run_id, seq, kind, key, json.dumps(payload or {}), now, now, now))
        if status:
            conn.execute("UPDATE runs SET status=%s, updated_at=NOW() WHERE id=%s", (status, run_id))


def archived_run(root, source_id):
    if not SOURCE_PATTERN.fullmatch(source_id):
        raise WorkflowError("INVALID_SOURCE_RUN", "OpenSquad run ID is invalid")
    base = (root / "squads" / "webagil-dev" / "output").resolve()
    folder = (base / source_id).resolve()
    if folder.parent != base or not folder.is_dir():
        raise WorkflowError("SOURCE_RUN_MISSING", "Archived OpenSquad run was not found")
    state_path = folder / "state.json"
    if state_path.is_symlink() or not state_path.is_file() or state_path.stat().st_size > 1048576:
        raise WorkflowError("STATE_INVALID", "Archived state.json is missing or invalid")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise WorkflowError("STATE_INVALID", "Archived state.json is not valid JSON") from exc
    step = state.get("step", {})
    if (state.get("runId") != source_id or state.get("squad") != "webagil-dev" or
        state.get("pipelineId") != "support" or state.get("status") != "completed" or
        not state.get("completedAt") or not isinstance(step, dict) or
        step.get("current") != step.get("total") or not isinstance(step.get("total"), int)):
        raise WorkflowError("GATE_UNCONFIRMED", "Archived state does not confirm all support steps completed")
    artifacts = [path for path in folder.rglob("*") if path.is_file() and not path.is_symlink()]
    if not artifacts:
        raise WorkflowError("ARTIFACT_MISSING", "Archived run has no files")
    return len(artifacts)


def build_graph(conn, opensquad_root):
    def identify(state: SupportState):
        row = conn.execute("SELECT id FROM tickets WHERE id=%s AND project_id=%s",
                           (state["ticket_id"], state["project_id"])).fetchone()
        if not row:
            raise WorkflowError("TICKET_NOT_FOUND", "Ticket no longer belongs to this project")
        event(conn, state["run_id"], "lg:identify", "workflow.ticket_identified", status="identifying")
        return {}

    def context(state: SupportState):
        count = conn.execute("SELECT COUNT(*) AS n FROM runs WHERE ticket_id=%s AND id<>%s",
                             (state["ticket_id"], state["run_id"])).fetchone()["n"]
        event(conn, state["run_id"], "lg:context", "workflow.context_retrieved", {"runs": count}, "context_ready")
        return {"context_runs": count}

    def prepare(state: SupportState):
        root = opensquad_root
        script = root / "tools" / "opensquad" / "preflight.mjs"
        if not script.is_file():
            raise WorkflowError("PREFLIGHT_MISSING", "OpenSquad preflight script was not found")
        try:
            result = subprocess.run(["node", str(script), "webagil-dev"], cwd=root, capture_output=True,
                                    text=True, encoding="utf-8", timeout=20,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkflowError("PREFLIGHT_FAILED", "OpenSquad preflight did not complete") from exc
        if result.returncode or "PREFLIGHT:PASS" not in result.stdout:
            raise WorkflowError("PREFLIGHT_FAILED", "OpenSquad preflight rejected the configuration")
        shared = root / "squads" / "webagil-dev" / "state.json"
        if shared.is_file():
            try:
                current = json.loads(shared.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise WorkflowError("EXTERNAL_STATE_UNKNOWN", "Shared OpenSquad state is invalid") from exc
            if current.get("status") in ("running", "waiting"):
                raise WorkflowError("EXTERNAL_STATE_CONFLICT", "OpenSquad already has an active shared state")
        event(conn, state["run_id"], "lg:prepare", "workflow.opensquad_prepared",
              {"preflight": "PASS", "execution": "supervised"}, "waiting_investigation")
        return {}

    def investigate(state: SupportState):
        answer = interrupt({"stage": "investigation", "ticket_key": state["ticket_key"],
                            "message": "Investigate in a supervised terminal; provide an archived OpenSquad run ID."})
        if not isinstance(answer, dict) or answer.get("decision") != "investigated" or not answer.get("source_run_id"):
            raise WorkflowError("INVESTIGATION_REQUIRED", "Investigation needs a source run ID")
        event(conn, state["run_id"], "lg:investigate", "workflow.investigation_recorded",
              {"source_run_id": answer["source_run_id"]}, "waiting_approval")
        return {"source_run_id": answer["source_run_id"]}

    def approval(state: SupportState):
        answer = interrupt({"stage": "approval", "ticket_key": state["ticket_key"],
                            "source_run_id": state["source_run_id"]})
        if not isinstance(answer, dict) or answer.get("decision") not in ("approve", "reject"):
            raise WorkflowError("APPROVAL_REQUIRED", "Approval decision is required")
        approved = answer["decision"] == "approve"
        event(conn, state["run_id"], "lg:approval", "workflow.approval_recorded",
              {"approved": approved}, "validating" if approved else "rejected")
        return {"approved": approved}

    def validate(state: SupportState):
        count = archived_run(opensquad_root, state["source_run_id"])
        event(conn, state["run_id"], "lg:validate", "workflow.gates_checked",
              {"source_run_id": state["source_run_id"], "archived_files": count}, "persisting")
        return {"artifact_count": count}

    def persist(state: SupportState):
        final = "completed" if state.get("approved") else "rejected"
        event(conn, state["run_id"], "lg:persist", "workflow.result_persisted",
              {"result": final}, final)
        with conn.transaction():
            conn.execute("DELETE FROM workflow_leases WHERE resource=%s AND run_id=%s", (RESOURCE, state["run_id"]))
        return {}

    graph = StateGraph(SupportState)
    for name, action in (("identify", identify), ("context", context), ("prepare", prepare),
                         ("investigate", investigate), ("approval", approval), ("validate", validate),
                         ("persist", persist)):
        graph.add_node(name, action)
    graph.add_edge(START, "identify")
    graph.add_edge("identify", "context")
    graph.add_edge("context", "prepare")
    graph.add_edge("prepare", "investigate")
    graph.add_edge("investigate", "approval")
    graph.add_conditional_edges("approval", lambda state: "validate" if state.get("approved") else "persist")
    graph.add_edge("validate", "persist")
    graph.add_edge("persist", END)
    return graph


def create_run(conn, project_slug, ticket_key, client_key):
    if not re.fullmatch(r"[a-z0-9-]+", project_slug) or not re.fullmatch(r"[A-Z][A-Z0-9_]+-[0-9]+", ticket_key):
        raise WorkflowError("INVALID_INPUT", "Project slug or ticket key is invalid")
    if not client_key or len(client_key) > 255:
        raise WorkflowError("INVALID_INPUT", "Client request key is required")
    with conn.transaction():
        project = conn.execute("SELECT id FROM projects WHERE slug=%s", (project_slug,)).fetchone()
        if not project:
            raise WorkflowError("PROJECT_NOT_FOUND", "Project was not found")
        ticket = conn.execute("SELECT id FROM tickets WHERE project_id=%s AND ticket_key=%s",
                              (project["id"], ticket_key)).fetchone()
        if not ticket:
            raise WorkflowError("TICKET_NOT_FOUND", "Ticket was not found in project")
        existing = conn.execute("SELECT id,ticket_id,status FROM runs WHERE project_id=%s AND client_request_key=%s",
                                (project["id"], client_key)).fetchone()
        if existing:
            if existing["ticket_id"] != ticket["id"]:
                raise WorkflowError("IDEMPOTENCY_CONFLICT", "Request key belongs to another ticket")
            return str(existing["id"]), False
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        conn.execute("INSERT INTO runs (id,project_id,ticket_id,source,source_squad,pipeline_id,status,client_request_key,created_at,updated_at) "
                     "VALUES (%s,%s,%s,'workspace','webagil-dev','support-langgraph','created',%s,%s,%s)",
                     (run_id, project["id"], ticket["id"], client_key, now, now))
        lease = conn.execute("INSERT INTO workflow_leases (resource,run_id,created_at,updated_at) "
                             "VALUES (%s,%s,%s,%s) ON CONFLICT (resource) DO NOTHING RETURNING resource",
                             (RESOURCE, run_id, now, now)).fetchone()
        if not lease:
            raise WorkflowError("CONCURRENT_RUN", "Another support workflow owns the shared OpenSquad state")
        return run_id, True


def describe(conn, compiled, run_id):
    row = conn.execute("SELECT id,status,ticket_id,client_request_key FROM runs WHERE id=%s", (run_id,)).fetchone()
    if not row:
        raise WorkflowError("RUN_NOT_FOUND", "Run was not found")
    snapshot = compiled.get_state({"configurable": {"thread_id": run_id}})
    stage = None
    if snapshot.tasks:
        interrupts = snapshot.tasks[0].interrupts
        if interrupts:
            stage = interrupts[0].value.get("stage")
    return {"run_id": str(row["id"]), "status": row["status"], "next": list(snapshot.next),
            "checkpoint_stage": stage, "ticket_id": str(row["ticket_id"]),
            "client_request_key": row["client_request_key"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "status", "resume"])
    parser.add_argument("--project")
    parser.add_argument("--ticket")
    parser.add_argument("--key")
    parser.add_argument("--run")
    parser.add_argument("--decision", choices=["investigated", "approve", "reject"])
    parser.add_argument("--source-run")
    args = parser.parse_args()
    config = local_config()
    opensquad_root = Path(os.environ.get("OPENSQUAD_ROOT") or config["opensquad"])
    with connect(config) as conn, connect(config) as checkpoint_conn:
        saver = PostgresSaver(checkpoint_conn)
        saver.setup()
        compiled = build_graph(conn, opensquad_root).compile(checkpointer=saver)
        if args.action == "start":
            if not all((args.project, args.ticket, args.key)):
                raise WorkflowError("INVALID_INPUT", "Start requires project, ticket and request key")
            run_id, created = create_run(conn, args.project, args.ticket, args.key)
            if created or conn.execute("SELECT status FROM runs WHERE id=%s", (run_id,)).fetchone()["status"] == "created":
                row = conn.execute("SELECT r.ticket_id,r.project_id,t.ticket_key FROM runs r JOIN tickets t ON t.id=r.ticket_id WHERE r.id=%s",
                                   (run_id,)).fetchone()
                initial: SupportState = {"run_id": run_id, "ticket_id": str(row["ticket_id"]),
                                         "project_id": str(row["project_id"]), "project_slug": args.project,
                                         "ticket_key": row["ticket_key"]}
                compiled.invoke(initial, {"configurable": {"thread_id": run_id}})
            result = describe(conn, compiled, run_id)
        else:
            if not args.run or not re.fullmatch(r"[0-9a-fA-F-]{36}", args.run):
                raise WorkflowError("INVALID_INPUT", "Run UUID is required")
            run_id = args.run
            if args.action == "resume":
                current = describe(conn, compiled, run_id)
                stage = current["checkpoint_stage"]
                if stage == "investigation" and args.decision == "investigated" and args.source_run:
                    answer = {"decision": "investigated", "source_run_id": args.source_run}
                elif stage == "approval" and args.decision in ("approve", "reject"):
                    answer = {"decision": args.decision}
                else:
                    raise WorkflowError("INVALID_TRANSITION", "Decision does not match the pending checkpoint")
                owner = conn.execute("SELECT run_id FROM workflow_leases WHERE resource=%s", (RESOURCE,)).fetchone()
                if not owner or str(owner["run_id"]) != run_id:
                    raise WorkflowError("LEASE_MISSING", "Run does not own the support workflow lease")
                compiled.invoke(Command(resume=answer), {"configurable": {"thread_id": run_id}})
            result = describe(conn, compiled, run_id)
        print(json.dumps(result, ensure_ascii=False, default=str))
        log("OK", args.action, result["run_id"])
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except WorkflowError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}))
        log(exc.code, "workflow", level="error")
        sys.exit(1)
    except Exception:
        print(json.dumps({"error": {"code": "WORKFLOW_FAILED", "message": "Workflow failed; inspect local logs"}}))
        log("WORKFLOW_FAILED", "workflow", level="error")
        sys.exit(1)
