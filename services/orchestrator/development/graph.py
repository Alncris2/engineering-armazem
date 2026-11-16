"""Checkpointable SDLC graph, with explicit local execution hooks.

Hooks receive stable operation keys. A production hook must make each key
idempotent before it performs a side effect. This module never calls Jira,
GitHub, Linear, Claude, MCP, or a pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .git_cli import snapshot as git_snapshot
from .spec_gate import check_spec_open_questions


STAGES = ("plan", "work", "simplify", "review", "fix", "activate")
MAX_ATTEMPTS = {"plan": 2, "work": 2, "simplify": 2, "review": 3, "fix": 2, "activate": 2}
NEXT = {"plan": "record_plan", "work": "run_simplify", "simplify": "run_review",
        "fix": "run_review", "activate": "done"}


class DevelopmentState(TypedDict, total=False):
    issue_key: str
    thread_id: str
    workspace_root: str
    artifact_dir: str
    confidence_threshold: int
    readiness_enabled: bool
    simplify_enabled: bool
    holds_enabled: bool
    shutdown_after: str
    from_stage: str
    status: str
    failure: str
    route: str
    readiness: bool | None
    confidence: int | None
    attempts: dict[str, int]
    results: dict[str, dict[str, Any]]
    gates: dict[str, dict[str, Any]]
    pending_hold: dict[str, Any]
    human_answer: dict[str, Any]
    plan_record: str
    evidence_mode: str
    git_repo: str
    executor: str
    task_text: str
    codex_root: str
    codex_stage: str


class DevelopmentHooks(Protocol):
    def readiness(self, state: DevelopmentState) -> bool | None:
        """True/False/None (unreadable). No service writes."""

    def confidence(self, state: DevelopmentState) -> int | None:
        """Score from 0 to 100; None means unreadable."""

    def run(self, stage: str, state: DevelopmentState, operation_key: str) -> dict[str, Any]:
        """Return local evidence. Must honor operation_key for safe replay."""


def _artifact(result: dict[str, Any], state: DevelopmentState) -> tuple[bool, str]:
    """Verify a stage artifact is a regular file inside this run's directory."""
    name, digest = result.get("artifact"), result.get("sha256")
    if not isinstance(name, str) or not name or not isinstance(digest, str) or len(digest) != 64:
        return False, "artifact receipt missing"
    base = Path(state["artifact_dir"]).resolve()
    path = (base / name).resolve()
    if path == base or base not in path.parents or not path.is_file() or path.is_symlink():
        return False, "artifact outside run directory or missing"
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return False, "artifact unreadable"
    return (actual == digest, "ok" if actual == digest else "artifact hash mismatch")


def gate_result(stage: str, state: DevelopmentState, result: dict[str, Any]) -> tuple[bool, str]:
    """Deterministic checks over local receipts; never trust a success flag alone."""
    if result.get("stage") != stage or result.get("issue_key") != state.get("issue_key"):
        return False, "stage or issue mismatch"
    if result.get("ok") is not True:
        return False, "executor did not succeed"
    if state.get("executor") == "codex":
        if stage != "plan" or result.get("executor") != "codex" or result.get("status") != "completed":
            return False, "Codex receipt invalid"
        attempt = state.get("attempts", {}).get(stage, 0)
        if result.get("operation_key") != f"{state.get('thread_id')}:{stage}:{attempt}":
            return False, "Codex operation key mismatch"
        if result.get("session_resumable") is not False:
            return False, "Codex session claim invalid"
        receipt_path = Path(state["artifact_dir"]) / "codex-plan-receipt.json"
        try:
            saved = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False, "Codex receipt missing"
        if saved != result:
            return False, "Codex receipt differs from checkpoint"
    valid, reason = _artifact(result, state)
    if not valid:
        return False, reason
    if state.get("evidence_mode", "simulation") == "local_git" and stage != "plan":
        receipt = result.get("git_snapshot")
        if not isinstance(receipt, dict) or not state.get("git_repo"):
            return False, "Git CLI receipt missing"
        try:
            observed = git_snapshot(state["git_repo"])
        except (OSError, ValueError, TimeoutError):
            return False, "Git CLI inspection failed"
        if receipt != observed:
            return False, "Git state changed since stage receipt"
        if stage == "work":
            files = result.get("changed_files")
            if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
                return False, "changed files missing"
            if not set(files).issubset(set(observed["changed_paths"])):
                return False, "reported files absent from Git status"
    if stage == "plan":
        if not isinstance(result.get("plan_text"), str) or not result["plan_text"].strip():
            return False, "plan text missing"
        try:
            plan_body = (Path(state["artifact_dir"]) / result["artifact"]).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return False, "plan artifact unreadable"
        if plan_body != result["plan_text"]:
            return False, "plan artifact differs from plan text"
        spec_valid, spec_reason = check_spec_open_questions(result["plan_text"])
        if not spec_valid:
            return False, spec_reason
    elif stage == "work":
        files = result.get("changed_files")
        if not isinstance(files, list) or not files or not all(isinstance(p, str) and p for p in files):
            return False, "changed files missing"
        if result.get("checks_passed") is not True:
            return False, "work checks failed"
    elif stage in ("simplify", "fix"):
        if result.get("checks_passed") is not True:
            return False, f"{stage} checks failed"
        if stage == "fix" and (not isinstance(result.get("resolved_ids"), list) or
                               not all(isinstance(item, str) for item in result["resolved_ids"])):
            return False, "resolved finding IDs missing"
        if stage == "fix":
            open_ids = {f["id"] for f in state.get("results", {}).get("review", {}).get("findings", [])
                        if f.get("status") == "open"}
            if not open_ids or not open_ids.issubset(set(result["resolved_ids"])):
                return False, "open findings not all resolved"
    elif stage == "review":
        findings = result.get("findings")
        if not isinstance(findings, list) or any(
            not isinstance(f, dict) or not isinstance(f.get("id"), str) or
            f.get("status") not in ("open", "closed") for f in findings
        ):
            return False, "findings malformed"
        ids = [f["id"] for f in findings]
        if len(ids) != len(set(ids)) or result.get("checks_passed") is not True:
            return False, "review findings or checks invalid"
    elif stage == "activate":
        if result.get("handoff_ready") is not True or result.get("checks_passed") is not True:
            return False, "handoff gate failed"
        review = state.get("results", {}).get("review", {})
        if any(f.get("status") == "open" for f in review.get("findings", [])):
            return False, "open findings remain"
    else:
        return False, "unknown stage"
    return True, "pass"


def _safe_artifact_dir(state: DevelopmentState) -> Path:
    root = Path(state["workspace_root"]).resolve()
    folder = Path(state["artifact_dir"]).resolve()
    if root not in folder.parents or folder == root:
        raise ValueError("artifact_dir must be inside workspace_root")
    return folder


def build_graph(hooks: DevelopmentHooks, *, checkpointer=None):
    """Compile the graph; caller supplies MemorySaver or PostgresSaver."""
    graph = StateGraph(DevelopmentState)

    def setup(state: DevelopmentState):
        key = state.get("issue_key", "")
        if not isinstance(key, str) or not key or not isinstance(state.get("thread_id"), str):
            return {"failure": "issue_key and thread_id required", "route": "fail"}
        try:
            _safe_artifact_dir(state)
        except (KeyError, ValueError, OSError) as exc:
            return {"failure": str(exc), "route": "fail"}
        threshold = state.get("confidence_threshold", 70)
        if not isinstance(threshold, int) or not 0 <= threshold <= 100:
            return {"failure": "invalid confidence threshold", "route": "fail"}
        if state.get("evidence_mode", "simulation") not in ("simulation", "local_git"):
            return {"failure": "invalid evidence mode", "route": "fail"}
        if state.get("evidence_mode") == "local_git" and not state.get("git_repo"):
            return {"failure": "git_repo required for local_git", "route": "fail"}
        if state.get("executor", "simulation") not in ("simulation", "codex"):
            return {"failure": "invalid executor", "route": "fail"}
        if state.get("executor") == "codex" and (state.get("codex_stage", "plan") != "plan" or state.get("from_stage")):
            return {"failure": "Codex work/review are disabled", "route": "fail"}
        selected = state.get("from_stage")
        if selected and selected not in STAGES:
            return {"failure": "invalid --from stage", "route": "fail"}
        return {"status": "running", "route": "entry_probe" if selected else "readiness"}

    def entry_probe(state: DevelopmentState):
        selected = state["from_stage"]
        prerequisites = {
            "plan": (), "work": ("plan",), "simplify": ("plan", "work"),
            "review": ("plan", "work"), "fix": ("plan", "work", "review"),
            "activate": ("plan", "work", "review"),
        }[selected]
        for stage in prerequisites:
            receipt = state.get("results", {}).get(stage)
            if not receipt or not gate_result(stage, state, receipt)[0]:
                return {"failure": f"entry artifact invalid: {stage}", "route": "fail"}
        return {"route": f"run_{selected}"}

    def readiness(state: DevelopmentState):
        if state.get("readiness_enabled", True) is False:
            return {"readiness": None, "route": "run_plan"}
        try:
            value = hooks.readiness(state)
        except Exception:
            value = None
        if value is False:
            return {"readiness": False, "pending_hold": {"reason": "issue not ready", "resume": "readiness"}, "route": "hold"}
        # Unreadable readiness allows planning, per source diagram.
        return {"readiness": value if value is True else None, "route": "run_plan"}

    def confidence(state: DevelopmentState):
        try:
            score = hooks.confidence(state)
        except Exception:
            score = None
        if not isinstance(score, int) or not 0 <= score <= 100:
            return {"confidence": None, "pending_hold": {"reason": "confidence unreadable", "resume": "run_plan"}, "route": "hold"}
        if score < state.get("confidence_threshold", 70):
            return {"confidence": score, "pending_hold": {"reason": "confidence below threshold", "resume": "run_plan"}, "route": "hold"}
        return {"confidence": score, "route": "record_plan"}

    def record_plan(state: DevelopmentState):
        try:
            folder = _safe_artifact_dir(state)
            folder.mkdir(parents=True, exist_ok=True)
            plan = state["results"]["plan"]
            if not gate_result("plan", state, plan)[0]:
                raise ValueError("plan artifact invalid")
            record = {"issue_key": state["issue_key"], "plan_sha256": plan["sha256"],
                      "plan_text": plan["plan_text"]}
            target = folder / "workplan.json"
            payload = json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
            if target.exists():
                if target.read_bytes() != payload:
                    raise ValueError("existing plan record differs")
            else:
                temp = folder / "workplan.json.tmp"
                temp.write_bytes(payload)
                os.replace(temp, target)
            return {"plan_record": str(target), "route": "run_work"}
        except (KeyError, OSError, ValueError) as exc:
            return {"failure": f"record_plan: {exc}", "route": "fail"}

    def make_run(stage: str):
        def run(state: DevelopmentState):
            attempts = dict(state.get("attempts", {}))
            attempts[stage] = attempts.get(stage, 0) + 1
            operation_key = f"{state['thread_id']}:{stage}:{attempts[stage]}"
            try:
                result = hooks.run(stage, state, operation_key)
                if not isinstance(result, dict):
                    raise TypeError("hook result must be an object")
            except Exception as exc:
                result = {"stage": stage, "issue_key": state["issue_key"], "ok": False,
                          "error": f"{type(exc).__name__}: {exc}"}
            results = dict(state.get("results", {}))
            results[stage] = result
            return {"attempts": attempts, "results": results, "route": f"gate_{stage}"}
        return run

    def make_gate(stage: str):
        def gate(state: DevelopmentState):
            passed, reason = gate_result(stage, state, state.get("results", {}).get(stage, {}))
            gates = dict(state.get("gates", {}))
            gates[stage] = {"passed": passed, "reason": reason,
                            "attempt": state.get("attempts", {}).get(stage, 0)}
            if passed:
                route = f"auto_shutdown_after_{stage}"
            elif state.get("executor") != "codex" and state.get("attempts", {}).get(stage, 0) < MAX_ATTEMPTS[stage]:
                route = f"run_{stage}"
            else:
                route = "hold"
            update: DevelopmentState = {"gates": gates, "route": route}
            if route == "hold":
                update["pending_hold"] = {"reason": f"{stage} gate: {reason}", "resume": f"gate_{stage}"}
            return update
        return gate

    def make_boundary(stage: str):
        def boundary(state: DevelopmentState):
            if state.get("shutdown_after") == stage:
                return {"pending_hold": {"reason": f"shutdown after {stage}",
                                         "resume": next_route(stage, state)}, "route": "hold"}
            return {"route": next_route(stage, state)}
        return boundary

    def next_route(stage: str, state: DevelopmentState) -> str:
        if stage == "plan":
            return "plan_confidence"
        if stage == "work" and state.get("simplify_enabled", True) is False:
            return "run_review"
        if stage == "review":
            findings = state["results"]["review"]["findings"]
            if any(f["status"] == "open" for f in findings):
                if state.get("attempts", {}).get("fix", 0) >= MAX_ATTEMPTS["fix"] or state.get("attempts", {}).get("review", 0) >= MAX_ATTEMPTS["review"]:
                    return "review_limit"
                return "run_fix"
            return "run_activate"
        return NEXT[stage]

    def review_limit(state: DevelopmentState):
        return {"pending_hold": {"reason": "review/fix loop limit", "resume": "gate_review"}, "route": "hold"}

    def hold(state: DevelopmentState):
        if state.get("holds_enabled", True) is False:
            return {"failure": state["pending_hold"]["reason"], "route": "fail"}
        return {"status": "held", "route": "await_human"}

    def await_human(state: DevelopmentState):
        answer = interrupt({"stage": "await_human", "issue_key": state["issue_key"],
                            "hold": state["pending_hold"], "decisions": ["resume", "abort"]})
        return {"human_answer": answer, "route": "recovery"}

    def recovery(state: DevelopmentState):
        answer = state.get("human_answer")
        if not isinstance(answer, dict):
            return {"failure": "invalid human answer", "route": "fail"}
        if answer.get("decision") == "abort":
            return {"route": "aborted"}
        if answer.get("decision") != "resume":
            return {"failure": "invalid human decision", "route": "fail"}
        target = state["pending_hold"]["resume"]
        # A failed gate may be rechecked after a person repairs its local artifact.
        # Its attempt budget stays exhausted; a second failure parks again.
        return {"status": "running", "route": target, "human_answer": {}}

    def fail(state: DevelopmentState):
        return {"status": "failed", "route": "end"}

    def done(state: DevelopmentState):
        return {"status": "done", "route": "end"}

    def aborted(state: DevelopmentState):
        return {"status": "aborted", "route": "end"}

    nodes = {"setup": setup, "entry_probe": entry_probe, "readiness": readiness,
             "plan_confidence": confidence, "record_plan": record_plan,
             "review_limit": review_limit, "hold": hold, "await_human": await_human,
             "recovery": recovery, "fail": fail, "done": done, "aborted": aborted}
    for stage in STAGES:
        nodes[f"run_{stage}"] = make_run(stage)
        nodes[f"gate_{stage}"] = make_gate(stage)
        nodes[f"auto_shutdown_after_{stage}"] = make_boundary(stage)
    for name, fn in nodes.items():
        graph.add_node(name, fn)
    graph.add_edge(START, "setup")
    for name in nodes:
        if name in ("fail", "done", "aborted"):
            graph.add_edge(name, END)
        else:
            graph.add_conditional_edges(name, lambda state: state["route"],
                                        {target: target for target in nodes})
    return graph.compile(checkpointer=checkpointer)
