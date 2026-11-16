"""Read-only Git metadata through the installed Git CLI."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            encoding="utf-8", timeout=15,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError("Git read failed")
    return result.stdout.strip()


def inspect(repo):
    root = Path(repo).resolve(strict=True)
    return {"repository": str(root), "head": git(root, "rev-parse", "HEAD"),
            "branch": git(root, "branch", "--show-current"),
            "dirty": bool(git(root, "status", "--porcelain"))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    args = parser.parse_args()
    try:
        print(json.dumps({"data": inspect(args.repository), "error": None}))
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        print(json.dumps({"data": None, "error": {"code": "GIT_READ_FAILED"}}))
        sys.exit(1)
