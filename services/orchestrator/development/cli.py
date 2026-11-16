"""Windows native development CLI with PostgreSQL checkpoints.

Run as ``python -m development.cli`` from services/orchestrator.
The DSN is read from DEVELOPMENT_CHECKPOINT_DSN and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from .graph import build_graph
from .simulation import ScenarioHooks
from .codex_cli import CodexPlanHooks, pinned_codex_executable


def codex_hooks_for(action: str, codex_root: Path, timeout: float) -> CodexPlanHooks:
    # Status and abort never launch Codex. A start always pins the same NVM
    # wrapper that passed the external PowerShell probe.
    executable = str(pinned_codex_executable()) if action == "start" else "codex"
    return CodexPlanHooks(codex_root=codex_root, timeout=timeout, executable=executable)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Development graph")
    parser.add_argument("action", choices=("start", "status", "resume"))
    parser.add_argument("--thread", required=True)
    parser.add_argument("--issue")
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--executor", choices=("simulation", "codex"), default="simulation")
    parser.add_argument("--stage", choices=("plan", "work", "review"), default="plan")
    parser.add_argument("--task-file", type=Path, help="Local task text for read-only Codex planning")
    parser.add_argument("--executor-timeout", type=float, default=120)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--decision", choices=("resume", "abort"))
    parser.add_argument("--from-stage", choices=("plan", "work", "simplify", "review", "fix", "activate"))
    parser.add_argument("--state-file", type=Path, help="Prior local receipts for --from-stage")
    args = parser.parse_args(argv)
    if args.stage != "plan":
        print(json.dumps({"error": {"code": "CODEX_STAGE_DISABLED",
                                    "message": "Real work/review require authenticated approval and sandbox verification"}}),
              file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", args.thread):
        parser.error("thread must contain only letters, numbers, underscore or hyphen")
    if args.action == "start" and (not args.issue or not args.workspace_root):
        parser.error("start requires --issue and --workspace-root")
    if args.action == "start" and args.executor == "simulation" and not args.scenario:
        parser.error("simulation start requires --scenario")
    if args.action == "start" and args.executor == "codex" and not args.task_file:
        parser.error("Codex start requires --task-file")
    if args.action == "resume" and not args.decision:
        parser.error("resume requires --decision")
    if args.executor_timeout <= 0 or args.executor_timeout > 600:
        parser.error("executor timeout must be between 1 and 600 seconds")
    dsn = os.environ.get("DEVELOPMENT_CHECKPOINT_DSN")
    if not dsn:
        parser.error("DEVELOPMENT_CHECKPOINT_DSN is required")
    with psycopg.connect(dsn, autocommit=True) as checkpoint_conn:
        saver = PostgresSaver(checkpoint_conn)
        saver.setup()
        config = {"configurable": {"thread_id": args.thread}}
        # A read-only graph can inspect the prior checkpoint before selecting hooks.
        probe = build_graph(ScenarioHooks({}), checkpointer=saver)
        prior = probe.get_state(config)
        selected = args.executor if args.action == "start" else prior.values.get("executor", "simulation")
        if selected == "codex":
            repo_root = Path(__file__).resolve().parents[3]
            safe_tmp = (repo_root / "tmp").resolve()
            if args.action == "start" and args.workspace_root.resolve() != safe_tmp:
                parser.error("Codex workspace root must be this repository's tmp directory")
            codex_root = safe_tmp / "development-sandboxes" / args.thread
            if args.action == "start":
                task_path = args.task_file.resolve()
                if repo_root not in task_path.parents or not task_path.is_file():
                    parser.error("task file must be a regular file inside this repository")
                task_text = task_path.read_text(encoding="utf-8")
                if not task_text.strip() or len(task_text) > 16000:
                    parser.error("task file must contain 1 to 16000 characters")
                # Resolve before creating a sandbox or a launch lock.
                hooks = codex_hooks_for(args.action, codex_root, args.executor_timeout)
                codex_root.mkdir(parents=True, exist_ok=True)
            else:
                hooks = codex_hooks_for(args.action, codex_root, args.executor_timeout)
        else:
            if args.scenario is None:
                parser.error("simulation requires --scenario")
            scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
            hooks = ScenarioHooks(scenario)
        graph = build_graph(hooks, checkpointer=saver)
        before = graph.get_state(config)
        if args.action == "start":
            if before.values:
                raise ValueError("thread already exists; use status or resume")
            root = args.workspace_root.resolve()
            if selected == "codex":
                run_dir = root / "development-runs" / args.thread
                run_dir.mkdir(parents=True, exist_ok=True)
                try:
                    descriptor = os.open(run_dir / "launch.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError as exc:
                    raise ValueError("Codex thread launch already claimed; reconcile before retry") from exc
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(json.dumps({"thread_id": args.thread, "issue_key": args.issue}))
            initial = {"thread_id": args.thread, "issue_key": args.issue,
                       "workspace_root": str(root), "artifact_dir": str(root / "development-runs" / args.thread),
                       "executor": selected}
            if selected == "codex":
                initial.update({"task_text": task_text, "codex_root": str(codex_root),
                                "shutdown_after": "plan"})
            if args.from_stage:
                initial["from_stage"] = args.from_stage
                if args.state_file:
                    previous = json.loads(args.state_file.read_text(encoding="utf-8"))
                    initial["results"] = previous.get("results", {})
                    initial["attempts"] = previous.get("attempts", {})
            graph.invoke(initial, config)
        elif args.action == "resume":
            if not before.values or not before.tasks or not before.tasks[0].interrupts:
                raise ValueError("thread is not waiting for a person")
            if selected == "codex" and args.decision != "abort":
                raise ValueError("Codex planning mode can only be aborted; later stages are not enabled")
            graph.invoke(Command(resume={"decision": args.decision}), config)
        after = graph.get_state(config)
        output = {"thread_id": args.thread, "executor": selected,
                          "status": after.values.get("status"),
                          "next": list(after.next), "hold": after.values.get("pending_hold")
                          if after.tasks and after.tasks[0].interrupts else None,
                          "attempts": after.values.get("attempts", {}),
                          "gates": after.values.get("gates", {})}
        if selected == "codex" and after.values.get("gates", {}).get("plan", {}).get("passed") is False:
            receipt = after.values.get("results", {}).get("plan", {})
            code = "CODEX_EXEC_INCONCLUSIVE" if receipt.get("ok") is False else "PLAN_GATE_FAILED"
            output["error"] = {"code": code, "message": "Codex plan did not pass its gate"}
            print(json.dumps(output, ensure_ascii=False))
            return 2
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, psycopg.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
