"""Read-only Git CLI evidence for future local stage hooks."""

from __future__ import annotations

import subprocess
from pathlib import Path


def snapshot(repo: str | Path) -> dict:
    root = Path(repo).resolve()

    def git(*args: str, allow_unborn: bool = False) -> str:
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=15,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode and not allow_unborn:
            raise ValueError(f"git {' '.join(args)} failed")
        return proc.stdout.strip()

    actual_root = Path(git("rev-parse", "--show-toplevel")).resolve()
    head = git("rev-parse", "--verify", "HEAD", allow_unborn=True) or None
    porcelain = git("status", "--porcelain=v1", "--untracked-files=all")
    changed = sorted({line[3:] for line in porcelain.splitlines() if len(line) >= 4})
    return {"root": str(actual_root), "head": head, "changed_paths": changed}
