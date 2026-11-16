"""Probe installed official executor CLIs without starting an agent session."""

import json
import shutil
import subprocess


def probe(name):
    path = shutil.which(name)
    if not path:
        return {"executor": name, "available": False}
    try:
        result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return {"executor": name, "available": False}
    return {"executor": name, "available": result.returncode == 0,
            "version": result.stdout.strip()[:100] if result.returncode == 0 else None}


if __name__ == "__main__":
    print(json.dumps({"data": [probe(name) for name in ("claude", "codex", "orca")], "error": None}))
