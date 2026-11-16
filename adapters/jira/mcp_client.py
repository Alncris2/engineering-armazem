"""Minimal stdio client for the existing read-only Jira MCP process on Windows."""

import argparse
import datetime
import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path


class McpClient:
    def __init__(self, opensquad_root: Path):
        script = opensquad_root / "tools" / "mcp" / "jira.ps1"
        if not script.is_file():
            raise RuntimeError("OpenSquad Jira MCP launcher was not found")
        self.process = subprocess.Popen(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script)],
            cwd=opensquad_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.messages = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.next_id = 0

    def _read(self):
        for line in self.process.stdout:
            self.messages.put(line)
        self.messages.put(None)

    def send(self, method, params=None, notification=False, timeout=90):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notification:
            self.next_id += 1
            message["id"] = self.next_id
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        if notification:
            return None
        while True:
            try:
                line = self.messages.get(timeout=timeout)
            except queue.Empty as exc:
                raise RuntimeError(f"Jira MCP did not answer {method} in time") from exc
            if line is None:
                raise RuntimeError("Jira MCP process ended before answering")
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Jira MCP returned a non-JSON message") from exc
            if response.get("id") != self.next_id:
                continue
            if "error" in response:
                raise RuntimeError(f"Jira MCP rejected {method}: {response['error'].get('code', 'unknown')}")
            return response.get("result", {})

    def initialize(self):
        self.send("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "workspace-core", "version": "0.1.0"}})
        self.send("notifications/initialized", notification=True)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


def read_issue(client, key):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+-[0-9]+", key):
        raise RuntimeError("Invalid Jira issue key")
    result = client.send("tools/call", {"name": "jira_get_issue", "arguments": {
        "issue_key": key, "fields": "summary,status,updated", "comment_limit": 0,
        "update_history": False,
    }}, timeout=120)
    if result.get("isError"):
        raise RuntimeError("Jira MCP could not read the issue")
    issue = result.get("structuredContent")
    if issue is None:
        content = result.get("content", [])
        text_blocks = [item.get("text", "") for item in content if item.get("type") == "text"]
        if not text_blocks:
            raise RuntimeError("Jira MCP returned no issue data")
        try:
            issue = json.loads(text_blocks[0])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Jira MCP issue format is not JSON") from exc
    if not isinstance(issue, dict):
        raise RuntimeError("Jira MCP issue format is not an object")
    return issue


def normalize_issue(issue, site, key):
    issue = unwrap_issue(issue)
    fields = issue.get("fields", issue)
    if not isinstance(fields, dict):
        raise RuntimeError("Jira MCP issue fields are missing")
    status = fields.get("status")
    if isinstance(status, dict):
        status = status.get("name")
    snapshot = {"site": site, "key": issue.get("key"), "issue_id": str(issue.get("id", "")),
                "summary": fields.get("summary"), "status": status, "updated_at": fields.get("updated")}
    if snapshot["key"] != key or not snapshot["issue_id"].isdigit() or not all(
        isinstance(snapshot[name], str) and snapshot[name] for name in ("summary", "status", "updated_at")
    ):
        raise RuntimeError("Jira MCP issue identity or required fields are missing")
    snapshot["updated_at"] = normalize_updated(snapshot["updated_at"])
    return snapshot


def normalize_updated(value):
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) Hora oficial do Brasil", value)
    if match:
        php = ('$d=DateTimeImmutable::createFromFormat("!Y-m-d H:i:s", $argv[1], '
               'new DateTimeZone("America/Sao_Paulo")); if (!$d) exit(1); '
               'echo $d->format(DateTimeInterface::ATOM);')
        converted = subprocess.run(["php", "-r", php, "--", match.group(1)], capture_output=True,
                                   text=True, encoding="utf-8", timeout=10,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if converted.returncode:
            raise RuntimeError("Jira MCP date could not be converted")
        return converted.stdout.strip()
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone missing")
    except ValueError as exc:
        raise RuntimeError("Jira MCP date has an unsupported format") from exc
    return value


def unwrap_issue(issue):
    for _ in range(3):
        nested = issue.get("result", issue.get("issue"))
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except json.JSONDecodeError:
                break
        if not isinstance(nested, dict):
            break
        issue = nested
    return issue


def main():
    parser = argparse.ArgumentParser(description="Read a Jira issue through the existing OpenSquad MCP launcher")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--inspect-issue", metavar="KEY")
    parser.add_argument("--import-issue", metavar="KEY")
    parser.add_argument("--project")
    parser.add_argument("--site", default="evolog.atlassian.net")
    args = parser.parse_args()
    if sum(bool(value) for value in (args.probe, args.inspect_issue, args.import_issue)) != 1:
        parser.error("choose exactly one of --probe, --inspect-issue or --import-issue")
    if args.import_issue and not args.project:
        parser.error("--project is required with --import-issue")
    if args.import_issue and args.site != "evolog.atlassian.net":
        parser.error("this OpenSquad Jira launcher is configured for evolog.atlassian.net")
    root = Path(os.environ.get("OPENSQUAD_ROOT", r"C:\htdocs\squad-ia"))
    client = McpClient(root)
    try:
        client.initialize()
        tools = client.send("tools/list", timeout=60).get("tools", [])
        target = next((tool for tool in tools if tool.get("name") == "jira_get_issue"), None)
        if not target:
            raise RuntimeError("jira_get_issue is not exposed by this MCP server")
        if args.probe:
            print(json.dumps({"tool": target.get("name"), "inputSchema": target.get("inputSchema")}, ensure_ascii=False))
            return
        key = args.inspect_issue or args.import_issue
        issue = read_issue(client, key)
        if args.inspect_issue:
            issue = unwrap_issue(issue)
            fields = issue.get("fields", {})
            normalized = {"key_matches": issue.get("key") == key,
                          "id_digits": str(issue.get("id", "")).isdigit()}
            for name in ("summary", "status", "updated"):
                value = issue.get(name)
                normalized[name] = {"type": type(value).__name__,
                                    "length": len(value) if isinstance(value, str) else None}
            if isinstance(issue.get("status"), dict):
                normalized["status"]["keys"] = sorted(issue["status"].keys())
                normalized["status"]["name_type"] = type(issue["status"].get("name")).__name__
            normalized["updated"]["value"] = issue.get("updated")
            print(json.dumps({"top_level_keys": sorted(issue.keys()),
                              "field_keys": sorted(fields.keys()) if isinstance(fields, dict) else [],
                              "result_type": type(issue.get("result")).__name__,
                              "metadata": normalized}))
            return
        snapshot = normalize_issue(issue, args.site, key)
    finally:
        client.close()
    api_root = Path(__file__).resolve().parents[2] / "apps" / "control-api"
    command = ["php", "-d", "xdebug.mode=off", "artisan", "workspace:import-jira-mcp",
               args.project, args.site, key, "--stdin"]
    completed = subprocess.run(command, cwd=api_root, input=json.dumps(snapshot), text=True,
                               capture_output=True, encoding="utf-8", timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode:
        detail = (completed.stdout + " " + completed.stderr).strip()[:300]
        raise RuntimeError("Workspace Core rejected the Jira snapshot: " + detail)
    print(completed.stdout.strip())


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
