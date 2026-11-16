"""Fail-closed local evidence helpers for future Codex work/review stages.

These helpers do not launch Codex. Work and review remain disabled in the CLI.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .spec_gate import check_spec_open_questions


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise ValueError("Git evidence command failed")
    return result.stdout


def _safe_path(path: Path) -> None:
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError("symlink or junction is forbidden")


def _inventory(repo: Path) -> dict[str, str]:
    found = {}
    for parent, dirs, files in os.walk(repo, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            _safe_path(path)
            if path.is_file():
                if path.stat().st_nlink != 1:
                    raise ValueError("linked file is forbidden")
                found[path.relative_to(repo).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(found.items()))


def inspect_example_repo(workspace_tmp: Path, thread_id: str, repo: Path,
                         target_module: str, *, require_clean: bool) -> dict[str, Any]:
    """Inventory every pre-existing file, including .git, in a thread-local repo."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", thread_id):
        raise ValueError("invalid thread")
    target = PurePosixPath(target_module)
    if (not target_module or "\\" in target_module or target.is_absolute() or
            any(part in (".", "..", ".git") for part in target.parts)):
        raise ValueError("invalid target module")
    base = workspace_tmp.resolve()
    expected = base / "development-sandboxes" / thread_id / "example-repo"
    if repo.resolve() != expected or not repo.is_dir():
        raise ValueError("repo must be the thread's example-repo")
    for path in (base / "development-sandboxes", expected.parent, repo, repo / ".git"):
        _safe_path(path)
    if not (repo / ".git").is_dir():
        raise ValueError("real .git directory required")
    actual = Path(_git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != expected:
        raise ValueError("Git root escaped example-repo")
    head = _git(repo, "rev-parse", "--verify", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise ValueError("committed HEAD required")
    module = repo / target_module
    _safe_path(module)
    if not module.is_file():
        raise ValueError("concrete target module required")
    _git(repo, "ls-files", "--error-unmatch", "--", target_module)
    status = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if require_clean and status:
        raise ValueError("pre-existing Git changes are forbidden")
    inventory = _inventory(repo)
    return {"head": head, "target_module": target_module, "inventory": inventory,
            "status_sha256": hashlib.sha256(status).hexdigest()}


def verify_scoped_diff(workspace_tmp: Path, thread_id: str, repo: Path,
                       baseline: dict[str, Any]) -> dict[str, Any]:
    """Reject new/removed/out-of-scope files and changed HEAD or .git contents."""
    target = baseline["target_module"]
    after = inspect_example_repo(workspace_tmp, thread_id, repo, target, require_clean=False)
    if after["head"] != baseline["head"]:
        raise ValueError("HEAD changed")
    before_files = baseline["inventory"]
    after_files = after["inventory"]
    if before_files.keys() != after_files.keys():
        raise ValueError("file added or removed")
    changed = [name for name in before_files if before_files[name] != after_files[name]]
    if changed != [target]:
        raise ValueError("diff outside target or no target change")
    names = _git(repo, "diff", "--name-only", "--").decode().splitlines()
    if names != [target]:
        raise ValueError("Git diff outside target")
    diff = _git(repo, "diff", "--binary", "--")
    _git(repo, "diff", "--check", "--")
    if not diff:
        raise ValueError("empty diff")
    return {"head": after["head"], "target_module": target,
            "inventory": after_files, "diff_sha256": hashlib.sha256(diff).hexdigest(),
            "diff_bytes": len(diff), "checks": {"git_diff_check": "passed"}}


def verify_frozen_review(workspace_tmp: Path, thread_id: str, repo: Path,
                         frozen: dict[str, Any]) -> bool:
    """A read-only review is valid only while every file and the diff stay frozen."""
    target = frozen["target_module"]
    current = inspect_example_repo(workspace_tmp, thread_id, repo, target, require_clean=False)
    if current["head"] != frozen["head"] or current["inventory"] != frozen["inventory"]:
        raise ValueError("review input changed")
    diff = _git(repo, "diff", "--binary", "--")
    _git(repo, "diff", "--check", "--")
    if hashlib.sha256(diff).hexdigest() != frozen["diff_sha256"]:
        raise ValueError("review diff changed")
    return True


def validate_work_binding(binding: dict[str, Any], *, thread_id: str, issue_key: str,
                          plan_sha256: str, repo: Path, head: str, target_module: str) -> None:
    """Validate a persisted approval record; provenance must be authenticated upstream."""
    if not re.fullmatch(r"[0-9a-f]{64}", plan_sha256):
        raise ValueError("invalid plan hash")
    expected = {"thread_id": thread_id, "issue_key": issue_key, "plan_sha256": plan_sha256,
                "repo": str(repo.resolve()), "head": head, "target_module": target_module,
                "decision": "approve-work"}
    if any(binding.get(key) != value for key, value in expected.items()):
        raise ValueError("work approval binding mismatch")
    if not isinstance(binding.get("actor"), str) or not binding["actor"].strip():
        raise ValueError("human actor missing")
    try:
        expiry = datetime.fromisoformat(binding["expires_at"])
        approved = datetime.fromisoformat(binding["approved_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("approval timestamps invalid") from exc
    now = datetime.now(timezone.utc)
    if (not approved.tzinfo or not expiry.tzinfo or approved > now or expiry <= now or
            approved >= expiry or expiry - approved > timedelta(hours=1)):
        raise ValueError("approval expired or invalid")


def validate_spec_and_target(spec: str, target_module: str) -> None:
    passed, reason = check_spec_open_questions(spec)
    if not passed:
        raise ValueError(reason)
    if not isinstance(target_module, str) or not target_module.strip():
        raise ValueError("concrete target module required")


def claim_pending(workspace_tmp: Path, folder: Path, thread_id: str, stage: str) -> str:
    """Claim once. Existing lock or pending journal always blocks replay."""
    if stage not in ("work", "review") or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", thread_id):
        raise ValueError("invalid stage or thread")
    key = f"{thread_id}:{stage}:1"
    expected = workspace_tmp.resolve() / "development-runs" / thread_id
    if folder.resolve() != expected or not folder.is_dir():
        raise ValueError("invalid journal directory")
    _safe_path(folder)
    lock = folder / f"codex-{stage}.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(key)
    receipt = folder / f"codex-{stage}-receipt.json"
    if receipt.exists():
        raise ValueError("existing receipt blocks replay")
    temp = receipt.with_suffix(".json.tmp")
    temp.write_text(json.dumps({"status": "pending", "operation_key": key}), encoding="utf-8")
    os.replace(temp, receipt)
    return key
