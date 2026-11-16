"""Versioned work-approval envelope. This module does not authenticate a person."""

from __future__ import annotations

import hashlib
import json
import ntpath
import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any

VERSION = 1
MAX_TTL_SECONDS = 300
FIELDS = frozenset({"version", "thread_id", "issue_key", "stage", "attempt",
                    "plan_sha256", "spec_sha256", "repo", "head", "inventory_sha256",
                    "allowlist", "target_module", "nonce", "issued_at", "expires_at"})
REQUEST_FIELDS = FIELDS - {"nonce", "issued_at", "expires_at", "version"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
THREAD = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
ISSUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
NONCE = re.compile(r"[0-9a-f]{64}\Z")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("UTC timestamp required")
    return parsed.astimezone(timezone.utc)


def _module(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return (not path.is_absolute() and value == path.as_posix() and
            all(part not in (".", "..", ".git") for part in value.split("/")))


def validate(payload: dict[str, Any], *, request: bool = False) -> None:
    if not isinstance(payload, dict) or set(payload) != (REQUEST_FIELDS if request else FIELDS):
        raise ValueError("approval envelope fields mismatch")
    if not request and (type(payload["version"]) is not int or payload["version"] != VERSION):
        raise ValueError("unsupported approval contract")
    if not isinstance(payload["thread_id"], str) or not THREAD.fullmatch(payload["thread_id"]):
        raise ValueError("invalid thread")
    if not isinstance(payload["issue_key"], str) or not ISSUE.fullmatch(payload["issue_key"]):
        raise ValueError("invalid issue")
    if payload["stage"] != "work" or type(payload["attempt"]) is not int or payload["attempt"] != 1:
        raise ValueError("only first work attempt can be requested")
    for key in ("plan_sha256", "spec_sha256", "inventory_sha256"):
        if not isinstance(payload[key], str) or not SHA.fullmatch(payload[key]):
            raise ValueError("invalid hash")
    if not isinstance(payload["head"], str) or not HEAD.fullmatch(payload["head"]):
        raise ValueError("invalid HEAD")
    repo = payload["repo"]
    expected = ("C:\\htdocs\\ai-engineering-workspace\\tmp\\development-sandboxes\\"
                + payload["thread_id"] + "\\example-repo")
    if (not isinstance(repo, str) or not ntpath.isabs(repo) or
            repo != expected or ntpath.normpath(repo) != repo):
        raise ValueError("repo must be canonical thread-local example repo")
    allowed = payload["allowlist"]
    if (not isinstance(allowed, list) or len(allowed) != 1 or
            not _module(allowed[0]) or payload["target_module"] != allowed[0]):
        raise ValueError("allowlist must contain the concrete target only")
    if request:
        return
    if not isinstance(payload["nonce"], str) or not NONCE.fullmatch(payload["nonce"]):
        raise ValueError("invalid nonce")
    issued, expires = _utc(payload["issued_at"]), _utc(payload["expires_at"])
    if not issued < expires <= issued + timedelta(seconds=MAX_TTL_SECONDS):
        raise ValueError("invalid expiry")


def issue(request: dict[str, Any], nonce: str, now: datetime, ttl_seconds: int = 120) -> dict[str, Any]:
    validate(request, request=True)
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        raise ValueError("invalid nonce")
    if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL_SECONDS:
        raise ValueError("invalid TTL")
    if now.tzinfo is None:
        raise ValueError("UTC time required")
    now = now.astimezone(timezone.utc)
    payload = {**request, "version": VERSION, "nonce": nonce,
               "issued_at": now.isoformat(),
               "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat()}
    validate(payload)
    return payload


def digest(payload: dict[str, Any]) -> str:
    validate(payload)
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
