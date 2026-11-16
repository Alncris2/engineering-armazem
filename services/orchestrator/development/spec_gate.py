"""Deterministic approval gate for a Markdown development spec."""

from __future__ import annotations

import re


def check_spec_open_questions(markdown: str) -> tuple[bool, str]:
    if not isinstance(markdown, str):
        return False, "spec text missing"
    text = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    match = re.search(r"(?im)^##\s+Open Questions\s*$", text)
    if not match:
        return False, "Open Questions section missing"
    rest = text[match.end():]
    boundary = re.search(r"(?m)^#{1,2}\s+", rest)
    section = (rest[:boundary.start()] if boundary else rest).strip()
    if section in ("Nenhuma.", "None."):
        return True, "no open questions"
    return False, "Open Questions must contain only 'Nenhuma.' before approval"
