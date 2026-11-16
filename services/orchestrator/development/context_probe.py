"""One-shot, bounded Codex context probe. Only emits sanitized JSON."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .codex_cli import (PINNED_WRAPPER_RELATIVE, InvocationError, InvocationResult,
                        _diagnostic, _invoke_bounded)


EXPECTED_WRAPPER = PINNED_WRAPPER_RELATIVE
ENV_NAMES = ("CODEX_PERMISSION_PROFILE", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_CI",
             "CODEX_THREAD_ID", "CODEX_VERSION", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
             "TEMP", "TMP")
FAKE_CODE = """import json,sys
if sys.argv[1] == 'permission':
 sys.stderr.buffer.write(b'permission denied FAKE_SECRET_MARKER')
 sys.exit(1)
for event in ({'type':'thread.started','thread_id':'01a1d5db-f0d7-75a1-8361-f0ee4a7824c1'},
              {'type':'item.completed','item':{'type':'agent_message','text':'PROBE_OK'}},
              {'type':'turn.completed'}):
 print(json.dumps(event), flush=True)
"""


def claim_once(path: Path) -> bool:
    """Persistent, atomic claim. A failed run must not be silently repeated."""
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.close(descriptor)
    return True


def _empty_diagnostic() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return _diagnostic(InvocationResult(b"", b"", None, now, now))


def _valid_probe_answer(stdout: bytes) -> bool:
    try:
        events = [json.loads(line) for line in stdout.decode("utf-8", "strict").splitlines()]
    except (UnicodeError, ValueError):
        return False
    if not all(isinstance(event, dict) for event in events):
        return False
    kinds = [event.get("type") for event in events]
    messages = [event.get("item", {}).get("text") for event in events
                if event.get("type") == "item.completed" and isinstance(event.get("item"), dict)
                and event["item"].get("type") == "agent_message"]
    return ("thread.started" in kinds and "turn.completed" in kinds and
            not any(kind in ("turn.failed", "error") for kind in kinds) and
            messages and messages[-1].strip() == "PROBE_OK")


def run_probe(root: Path, mode: str, fake_outcome: str, timeout: int) -> dict:
    root = root.resolve()
    tmp = (root / "tmp").resolve()
    context = {
        "cwd_kind": "workspace_root" if Path.cwd().resolve() == root else "other",
        "environment_names_present": [name for name in ENV_NAMES if name in os.environ],
        "argv_template": ["<pinned-nvm-codex.cmd>", "exec", "--json", "--ephemeral", "--ignore-user-config",
                          "--sandbox", "read-only", "--cd", "<new-empty-tmp-sandbox>",
                          "--skip-git-repo-check", "-"],
        "mode": mode,
    }
    if context["cwd_kind"] != "workspace_root" or not tmp.is_dir():
        return {"status": "preflight_failed", "reason": "workspace_context", "context": context}
    resolved = shutil.which("codex")
    expected = Path(os.environ.get("LOCALAPPDATA", "")) / EXPECTED_WRAPPER
    wrapper_match = bool(resolved and os.path.normcase(os.path.abspath(resolved)) ==
                         os.path.normcase(os.path.abspath(expected)))
    context["resolved_executable_kind"] = "nvm_codex_cmd" if wrapper_match else "other_or_missing"
    context["pinned_wrapper_available"] = expected.is_file()
    if mode == "real" and not context["pinned_wrapper_available"]:
        return {"status": "preflight_failed", "reason": "pinned_wrapper_missing", "context": context}
    if mode == "real" and not claim_once(tmp / "codex-context-probe.real.once"):
        return {"status": "preflight_failed", "reason": "duplicate_blocked", "context": context}
    sandbox = Path(tempfile.mkdtemp(prefix="codex-context-", dir=tmp))
    # mkdtemp creates a new, exclusive directory. Some managed Windows
    # sandboxes deny enumeration even to the process that created it.
    context["sandbox_empty_before"] = True
    if mode == "real":
        command = [str(expected), "exec", "--json", "--ephemeral", "--ignore-user-config",
                   "--sandbox", "read-only", "--cd", str(sandbox), "--skip-git-repo-check", "-"]
        context["executed_executable_kind"] = "pinned_nvm_codex_cmd"
    else:
        command = [sys.executable, "-u", "-c", FAKE_CODE, fake_outcome,
                   "exec", "--json", "--ephemeral", "--ignore-user-config", "--sandbox",
                   "read-only", "--cd", str(sandbox), "--skip-git-repo-check", "-"]
        context["executed_executable_kind"] = "fake_python"
    try:
        result = _invoke_bounded(command, "Reply only PROBE_OK.", timeout)
    except InvocationError as exc:
        result = exc.result
        outcome = "invocation_inconclusive"
    except OSError:
        return {"status": "failed", "reason": "launch_error", "context": context,
                "diagnostic": _empty_diagnostic()}
    else:
        outcome = "passed" if result.exit_code == 0 and _valid_probe_answer(result.stdout) else "failed"
    return {"status": outcome, "context": context, "diagnostic": _diagnostic(result)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mode", choices=("real", "fake"), required=True)
    parser.add_argument("--fake-outcome", choices=("success", "permission"), default="success")
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 30:
        print(json.dumps({"status": "preflight_failed", "reason": "invalid_timeout"}))
        return 1
    try:
        result = run_probe(args.root, args.mode, args.fake_outcome, args.timeout)
    except Exception:
        result = {"status": "failed", "reason": "internal_error"}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
