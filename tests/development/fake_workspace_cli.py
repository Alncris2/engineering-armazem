"""Fake root CLI for a PowerShell pilot dry run. Never imports or starts Codex."""

import json
import os
import sys
from pathlib import Path


def main(argv):
    args = [part for part in argv if part != "--json"]
    if len(args) < 4 or args[0] != "development" or args[1] not in ("start", "status"):
        print(json.dumps({"data": None, "error": {"code": "FAKE_INVALID_ARGUMENT"}}))
        return 1
    thread = args[args.index("--thread") + 1]
    root = Path(__file__).resolve().parents[2]
    base = root / "tmp" / "fake-codex-checkpoints"
    base.mkdir(parents=True, exist_ok=True)
    state_file = base / (thread + ".json")
    if args[1] == "start":
        state = {"thread_id": thread, "executor": "codex", "status": "held",
                 "gates": {"plan": {"passed": True, "reason": "pass", "attempt": 1}},
                 "attempts": {"plan": 1}, "next": ["await_human"],
                 "hold": {"reason": "shutdown after plan"}}
        try:
            with state_file.open("x", encoding="utf-8") as stream:
                json.dump(state, stream)
        except FileExistsError:
            print(json.dumps({"data": None, "error": {"code": "FAKE_DUPLICATE"}}))
            return 1
    else:
        if not state_file.is_file():
            print(json.dumps({"data": None, "error": {"code": "FAKE_MISSING"}}))
            return 1
        state = json.loads(state_file.read_text(encoding="utf-8"))
    print(json.dumps({"data": state, "error": None}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
