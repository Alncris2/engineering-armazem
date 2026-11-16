"""Read-only Codex CLI planning hook for an isolated development thread.

The CLI is ephemeral and cannot be resumed as a Codex session. LangGraph owns
the durable thread. A receipt is reused by operation key after a checkpoint
replay; the Codex invocation itself is restricted to read-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graph import DevelopmentState


MAX_EVENT_BYTES = 2 * 1024 * 1024
PINNED_WRAPPER_RELATIVE = (Path("Author Software") / "nvm" / "installs" /
                           "v26.13.1" / "codex.cmd")
EVENT_TYPES = frozenset({"thread.started", "turn.started", "item.started", "item.completed",
                         "turn.completed", "turn.failed", "error"})
CATEGORIES = (
    ("invalid_flag", re.compile(rb"unknown (?:option|flag)|unrecognized (?:option|argument)|unexpected argument|invalid value|found argument", re.I)),
    ("auth", re.compile(rb"unauthorized|authentication|not logged in|login required|\b401\b", re.I)),
    ("network_or_proxy", re.compile(rb"proxy|connection refused|dns|network|timed? out|connect error", re.I)),
    ("permission", re.compile(rb"permission denied|access denied|winerror 5|os error 5", re.I)),
    ("app_server", re.compile(rb"app[- ]server", re.I)),
)


def pinned_codex_executable() -> Path:
    """Resolve the same NVM wrapper used by the successful external probe."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise ValueError("LOCALAPPDATA is unavailable for the pinned Codex wrapper")
    wrapper = Path(local_app_data) / PINNED_WRAPPER_RELATIVE
    if not wrapper.is_file():
        raise ValueError("Pinned Codex wrapper is unavailable")
    return wrapper.resolve()


@dataclass(frozen=True)
class InvocationResult:
    stdout: bytes
    stderr: bytes
    exit_code: int | None
    started_at: str
    finished_at: str


class InvocationError(RuntimeError):
    def __init__(self, message: str, result: InvocationResult):
        self.result = result
        super().__init__(message)


class OutputLimitError(InvocationError):
    def __init__(self, stdout_bytes: int, stderr_bytes: int, result: InvocationResult):
        self.stdout_bytes = stdout_bytes
        self.stderr_bytes = stderr_bytes
        super().__init__(f"Codex output exceeded capture limit ({stdout_bytes} stdout, "
                         f"{stderr_bytes} stderr; {MAX_EVENT_BYTES} bytes per stream); "
                         "operation is inconclusive", result)


def _diagnostic(result: InvocationResult) -> dict[str, Any]:
    """Only fixed enums, counts, hashes and times; never event text or stderr."""
    combined = result.stderr + b"\n" + result.stdout
    category = next((name for name, pattern in CATEGORIES if pattern.search(combined)), "unknown")
    counts = {name: 0 for name in sorted(EVENT_TYPES)}
    unknown = malformed = 0
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            malformed += 1
            continue
        kind = event.get("type") if isinstance(event, dict) else None
        if isinstance(kind, str) and kind in counts:
            counts[kind] += 1
        else:
            unknown += 1
    return {"category": category, "exit_code": result.exit_code,
            "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr),
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
            "event_counts": counts, "unknown_events": unknown, "malformed_lines": malformed,
            "started_at": result.started_at, "finished_at": result.finished_at}


class CodexPlanHooks:
    def __init__(self, *, codex_root: Path, timeout: float = 120, executable: str = "codex"):
        self.root = codex_root.resolve()
        self.timeout = timeout
        self.executable = executable

    def readiness(self, state: DevelopmentState) -> bool | None:
        return None  # No Jira write or inferred status.

    def confidence(self, state: DevelopmentState) -> int | None:
        return None  # Requires a future reviewed scoring source.

    def run(self, stage: str, state: DevelopmentState, operation_key: str) -> dict[str, Any]:
        if stage != "plan":
            raise ValueError("Codex executor currently supports only the read-only plan stage")
        expected = f"{state['thread_id']}:plan:{state.get('attempts', {}).get('plan', 0) + 1}"
        if operation_key != expected:
            raise ValueError("operation key does not match thread and attempt")
        folder = Path(state["artifact_dir"]).resolve()
        workspace = Path(state["workspace_root"]).resolve()
        if folder != workspace / "development-runs" / state["thread_id"]:
            raise ValueError("unexpected artifact directory")
        if self.root != workspace / "development-sandboxes" / state["thread_id"]:
            raise ValueError("unexpected Codex sandbox directory")
        if not self.root.is_dir():
            raise ValueError("Codex sandbox directory missing")
        folder.mkdir(parents=True, exist_ok=True)
        receipt_path = folder / "codex-plan-receipt.json"
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("status") != "completed":
                raise RuntimeError("Codex operation is inconclusive; reconcile before retry")
            if receipt.get("operation_key") != operation_key:
                raise ValueError("Codex plan receipt belongs to another operation")
            plan_path = folder / receipt["artifact"]
            if hashlib.sha256(plan_path.read_bytes()).hexdigest() != receipt["sha256"]:
                raise ValueError("Codex plan artifact changed after execution")
            return receipt
        lock = folder / "codex-plan.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("Codex operation lock exists; reconcile before retry") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(operation_key)
        _write_atomic(receipt_path, {"status": "pending", "operation_key": operation_key})

        task = state.get("task_text", "")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task_text is required for Codex planning")
        prompt = (
            "Prepare a development plan for the following local task. Read-only analysis. "
            "Do not edit files, call external services, or attempt production operations. "
            "Reply only with a Markdown specification containing '# Spec', '## Objetivo', "
            "and '## Open Questions'. If anything is unclear, list it under Open Questions. "
            "Use 'Nenhuma.' in that section only if there are no questions.\n\n"
            f"Ticket: {state['issue_key']}\nTask:\n{task.strip()}\n"
        )
        command = [self.executable, "exec", "--json", "--ephemeral", "--ignore-user-config",
                   "--sandbox", "read-only", "--cd", str(self.root),
                   "--skip-git-repo-check", "-"]
        try:
            invocation = _invoke_bounded(command, prompt, self.timeout)
        except InvocationError as exc:
            _write_atomic(folder / "diagnostic.json", _diagnostic(exc.result))
            raise
        except OSError:
            now = datetime.now(timezone.utc).isoformat()
            _write_atomic(folder / "diagnostic.json", _diagnostic(InvocationResult(b"", b"", None, now, now)))
            raise RuntimeError("Codex launch failed; operation is inconclusive") from None
        if invocation.exit_code:
            _write_atomic(folder / "diagnostic.json", _diagnostic(invocation))
            raise RuntimeError(f"Codex CLI exited {invocation.exit_code}; operation is inconclusive")
        try:
            stdout = invocation.stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            _write_atomic(folder / "diagnostic.json", _diagnostic(invocation))
            raise ValueError("Codex event stream is not UTF-8; operation is inconclusive") from None
        thread_id = None
        last_message = None
        completed = False
        failed = False
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                _write_atomic(folder / "diagnostic.json", _diagnostic(invocation))
                raise ValueError("Codex event stream malformed; operation is inconclusive") from exc
            if not isinstance(event, dict):
                _write_atomic(folder / "diagnostic.json", _diagnostic(invocation))
                raise ValueError("Codex event stream malformed; operation is inconclusive")
            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id")
            if event.get("type") == "turn.completed":
                completed = True
            if event.get("type") in ("turn.failed", "error"):
                failed = True
            item = event.get("item")
            if event.get("type") == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
                last_message = item.get("text")
        if (failed or not completed or not isinstance(thread_id, str) or
                not re.fullmatch(r"[0-9a-fA-F-]{36}", thread_id) or
                not isinstance(last_message, str) or not last_message.strip()):
            _write_atomic(folder / "diagnostic.json", _diagnostic(invocation))
            raise ValueError("Codex event stream incomplete; operation is inconclusive")
        data = last_message.strip().encode("utf-8")
        plan_path = folder / "plan-1.txt"
        plan_tmp = folder / "plan-1.txt.tmp"
        plan_tmp.write_bytes(data)
        os.replace(plan_tmp, plan_path)
        receipt = {"stage": "plan", "issue_key": state["issue_key"],
                   "operation_key": operation_key, "ok": True, "plan_text": last_message.strip(),
                   "artifact": plan_path.name, "sha256": hashlib.sha256(data).hexdigest(),
                   "executor": "codex", "codex_thread_id": thread_id,
                   "session_resumable": False, "status": "completed"}
        _write_atomic(receipt_path, receipt)
        return receipt


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(encoded)
    os.replace(temp, path)


def _stop_process_tree(proc: subprocess.Popen) -> None:
    """Bounded cleanup of only the child we started; failure stays inconclusive."""
    if proc.poll() is not None:
        return
    tree_stopped = False
    if os.name == "nt":
        try:
            result = subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                    capture_output=True, timeout=5,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            tree_stopped = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not tree_stopped:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _invoke_bounded(command: list[str], prompt: str, timeout: float) -> InvocationResult:
    """Drain both Windows pipes concurrently; return bounded in-memory evidence."""
    started_at = datetime.now(timezone.utc).isoformat()
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    exceeded = threading.Event()
    reader_errors: list[Exception] = []

    def drain(name: str, pipe) -> None:
        try:
            while True:
                chunk = pipe.read1(8192)
                if not chunk:
                    break
                target = captured[name]
                if len(target) + len(chunk) > MAX_EVENT_BYTES:
                    exceeded.set()
                    return
                target.extend(chunk)
        except (OSError, ValueError) as exc:
            reader_errors.append(exc)

    def send_prompt() -> None:
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass  # Child exit is checked below.

    readers = [threading.Thread(target=drain, args=(name, getattr(proc, name)), daemon=True)
               for name in ("stdout", "stderr")]
    writer = threading.Thread(target=send_prompt, daemon=True)
    for thread in (*readers, writer):
        thread.start()
    deadline = time.monotonic() + timeout
    try:
        failure = None
        while True:
            if exceeded.is_set():
                _stop_process_tree(proc)
                failure = "output_limit"
                break
            if time.monotonic() >= deadline:
                _stop_process_tree(proc)
                failure = "timeout"
                break
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        for thread in (*readers, writer):
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in (*readers, writer)) or reader_errors:
            _stop_process_tree(proc)
            failure = failure or "stream_error"
        if exceeded.is_set():
            failure = "output_limit"
        result = InvocationResult(bytes(captured["stdout"]), bytes(captured["stderr"]),
                                  proc.returncode, started_at, datetime.now(timezone.utc).isoformat())
        if failure == "output_limit":
            raise OutputLimitError(len(result.stdout), len(result.stderr), result)
        if failure:
            raise InvocationError(f"Codex {failure}; operation is inconclusive", result)
        return result
    finally:
        for thread in (*readers, writer):
            thread.join(timeout=0.5)
        for thread, pipe in zip(readers, (proc.stdout, proc.stderr)):
            if not thread.is_alive():
                pipe.close()
        if not writer.is_alive():
            proc.stdin.close()
