"""Explicit local simulation for graph testing; no agent or remote integration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .graph import DevelopmentState


class ScenarioHooks:
    """Scenario values are evidence inputs, not real Jira/Git/CI observations."""

    def __init__(self, scenario: dict[str, Any]):
        self.scenario = scenario

    def readiness(self, state: DevelopmentState) -> bool | None:
        return self.scenario.get("readiness")

    def confidence(self, state: DevelopmentState) -> int | None:
        return self.scenario.get("confidence")

    def run(self, stage: str, state: DevelopmentState, operation_key: str) -> dict[str, Any]:
        number = state.get("attempts", {}).get(stage, 0) + 1
        variants = self.scenario.get("stages", {}).get(stage, [])
        if not isinstance(variants, list) or number > len(variants):
            raise ValueError(f"no simulated result for {stage} attempt {number}")
        template = variants[number - 1]
        if not isinstance(template, dict):
            raise ValueError("stage result must be an object")
        result = dict(template)
        result.update({"stage": stage, "issue_key": state["issue_key"], "operation_key": operation_key})
        folder = Path(state["artifact_dir"])
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{stage}-{number}.json" if stage != "plan" else f"plan-{number}.txt"
        path = folder / name
        if stage == "plan":
            data = str(result.get("plan_text", "")).encode("utf-8")
        else:
            data = json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")
        if path.exists() and path.read_bytes() != data:
            raise ValueError("operation key artifact conflict")
        if not path.exists():
            path.write_bytes(data)
        result.update({"artifact": name, "sha256": hashlib.sha256(data).hexdigest()})
        return result
