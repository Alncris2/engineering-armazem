"""Interface local do Workspace Core, independente do terminal que a executa."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
API_ROOT = ROOT / "apps" / "control-api"
WORKFLOW = ROOT / "services" / "orchestrator" / "workflow.py"
VENV_PYTHON = ROOT / "services" / "orchestrator" / ".venv-workspace" / "Scripts" / "python.exe"
JIRA_SCRIPT = ROOT / "adapters" / "jira" / "get-issue.ps1"


class CliError(Exception):
    def __init__(self, code, message, data=None):
        self.code = code
        self.data = data
        super().__init__(message)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CliError("INVALID_ARGUMENT", message)


def log(code, operation, elapsed_ms, level="info"):
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "level": level,
                      "code": code, "operation": operation, "duration_ms": elapsed_ms}), file=sys.stderr)


def api_request(base, timeout, method, path, payload=None):
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.path not in ("", "/"):
        raise CliError("INVALID_API_URL", "API must use loopback HTTP")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base.rstrip("/") + path, data=body, method=method,
                                     headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error = json.load(exc).get("error", {})
        except (ValueError, OSError):
            error = {}
        raise CliError(error.get("code", "HTTP_ERROR"), error.get("message", f"HTTP {exc.code}")) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CliError("API_UNAVAILABLE", "Workspace API is unavailable or timed out") from exc
    if not isinstance(result, dict) or "data" not in result:
        raise CliError("INVALID_RESPONSE", "Workspace API returned an invalid response")
    return result["data"]


def subprocess_json(command, cwd, timeout, input_text=None, env=None):
    try:
        result = subprocess.run(command, cwd=cwd, input=input_text, capture_output=True,
                                text=True, encoding="utf-8", timeout=timeout,
                                env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliError("EXTERNAL_UNAVAILABLE", "External command failed to start or timed out") from exc
    if result.returncode:
        for line in reversed(result.stdout.splitlines()):
            if line.lstrip().startswith("{"):
                try:
                    error = json.loads(line).get("error")
                    if isinstance(error, dict) and "code" in error:
                        payload = json.loads(line)
                        data = {key: payload.get(key) for key in ("thread_id", "executor", "status", "next", "hold", "attempts", "gates")
                                if key in payload}
                        raise CliError(error["code"], error.get("message", "External command failed"), data or None)
                except ValueError:
                    pass
        raise CliError("EXTERNAL_FAILED", "External command returned a failure")
    lines = [line for line in result.stdout.splitlines() if line.lstrip().startswith("{")]
    if not lines:
        raise CliError("INVALID_RESPONSE", "External command did not return JSON")
    try:
        return json.loads(lines[-1])
    except ValueError as exc:
        raise CliError("INVALID_RESPONSE", "External command returned invalid JSON") from exc


def find_project(api, timeout, slug):
    if re.fullmatch(r"[0-9a-fA-F-]{36}", slug):
        return api_request(api, timeout, "GET", "/api/projects/" + slug)
    matches = [row for row in api_request(api, timeout, "GET", "/api/projects") if row["slug"] == slug]
    if len(matches) != 1:
        raise CliError("PROJECT_NOT_FOUND", "Project slug was not found")
    return matches[0]


def find_ticket(api, timeout, key_or_id):
    if re.fullmatch(r"[0-9a-fA-F-]{36}", key_or_id):
        return {"id": key_or_id}
    matches = api_request(api, timeout, "GET", "/api/tickets?key=" + urllib.parse.quote(key_or_id))
    if len(matches) != 1:
        raise CliError("TICKET_NOT_UNIQUE", "Ticket key was not found or is ambiguous; use its UUID")
    return matches[0]


def run(args):
    api, timeout = args.api, args.timeout
    request = lambda method, path, payload=None: api_request(api, timeout, method, path, payload)
    if args.group == "projects":
        if args.action == "list": return request("GET", "/api/projects")
        if args.action == "show": return request("GET", "/api/projects/" + find_project(api, timeout, args.slug)["id"])
        return request("POST", "/api/projects", {"slug": args.slug, "name": args.name})
    if args.group == "repositories":
        project = find_project(api, timeout, args.project)
        path = f"/api/projects/{project['id']}/repositories"
        if args.action == "list": return request("GET", path)
        return request("POST", path, {"name": args.name, "path": args.path, "role": args.role})
    if args.group == "tickets":
        if args.action == "list": return request("GET", "/api/tickets")
        if args.action == "history":
            ticket = find_ticket(api, timeout, args.key)
            return request("GET", f"/api/tickets/{ticket['id']}/history")
        if args.action == "add":
            project = find_project(api, timeout, args.project)
            return request("POST", "/api/tickets", {"project_id": project["id"],
                          "site_key": args.site, "ticket_key": args.key})
        if args.action == "sync":
            if not re.fullmatch(r"[A-Z][A-Z0-9_]+-[0-9]+", args.key):
                raise CliError("INVALID_ARGUMENT", "Invalid Jira issue key")
            snapshot = subprocess_json(["pwsh", "-NoProfile", "-File", str(JIRA_SCRIPT),
                                        "-Key", args.key, "-TimeoutSec", str(int(timeout))], ROOT, timeout + 10)
            return subprocess_json(["php", "-d", "xdebug.mode=off", "artisan", "workspace:import-jira-snapshot",
                                    args.project, "evolog.atlassian.net", args.key, "--stdin"], API_ROOT,
                                   timeout, json.dumps(snapshot))
    if args.group == "runs":
        if args.action == "show": return request("GET", f"/api/runs/{args.id}")
        project = find_project(api, timeout, args.project)
        ticket = find_ticket(api, timeout, args.ticket) if args.ticket else None
        return request("POST", "/api/runs", {"project_id": project["id"],
                      "ticket_id": ticket["id"] if ticket else None, "pipeline_id": args.pipeline,
                      "client_request_key": args.key})
    if args.group == "sessions":
        return request("POST", f"/api/runs/{args.run}/sessions", {"executor": args.executor,
                      "external_session_id": args.external_id, "capture_method": args.capture_method})
    if args.group == "memory":
        if args.action == "search":
            return request("GET", "/api/memory/search?q=" + urllib.parse.quote(args.query))
        return request("POST", f"/api/runs/{args.run}/evidence", {"source": args.source, "claim": args.claim})
    if args.group == "opensquad":
        return subprocess_json(["php", "-d", "xdebug.mode=off", "artisan", "workspace:import-opensquad",
                                args.project, args.squad, args.run, "--ticket=" + args.ticket], API_ROOT, timeout)
    if args.group == "pipelines":
        python = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable
        command = [python, str(WORKFLOW), args.action]
        if args.action == "start":
            command += ["--project", args.project, "--ticket", args.ticket, "--key", args.key]
        else:
            command += ["--run", args.run]
        if args.action == "resume":
            command += ["--decision", args.decision]
            if args.source_run: command += ["--source-run", args.source_run]
        return subprocess_json(command, ROOT, timeout)
    if args.group == "development":
        if args.action == "start" and args.stage != "plan":
            raise CliError("CODEX_STAGE_DISABLED", "Real work/review require authenticated approval and sandbox verification")
        from services.orchestrator.workflow import local_config
        db = local_config()["db"]
        user = urllib.parse.quote(str(db["username"]), safe="")
        password = urllib.parse.quote(str(db["password"]), safe="")
        database = urllib.parse.quote(str(db["database"]), safe="")
        dsn = f"postgresql://{user}:{password}@{db['host']}:{db['port']}/{database}"
        env = os.environ.copy()
        env["DEVELOPMENT_CHECKPOINT_DSN"] = dsn
        command = [str(VENV_PYTHON), "-m", "development.cli", args.action,
                   "--thread", args.thread]
        if args.scenario:
            scenario = Path(args.scenario)
            if not scenario.is_absolute(): scenario = ROOT / scenario
            command += ["--scenario", str(scenario)]
        if args.action == "start":
            command += ["--issue", args.issue, "--workspace-root", str(ROOT / "tmp")]
            if args.executor:
                command += ["--executor", args.executor]
            command += ["--stage", args.stage]
            if args.task_file:
                task_file = Path(args.task_file)
                if not task_file.is_absolute(): task_file = ROOT / task_file
                command += ["--task-file", str(task_file)]
            if args.executor_timeout:
                command += ["--executor-timeout", str(args.executor_timeout)]
            if args.from_stage: command += ["--from-stage", args.from_stage]
            if args.state_file:
                state_file = Path(args.state_file)
                if not state_file.is_absolute(): state_file = ROOT / state_file
                command += ["--state-file", str(state_file)]
        if args.action == "resume": command += ["--decision", args.decision]
        child_timeout = max(timeout, (args.executor_timeout or 120) + 30) if args.action == "start" and args.executor == "codex" else timeout
        return subprocess_json(command, ROOT / "services" / "orchestrator", child_timeout, env=env)
    raise CliError("INVALID_ARGUMENT", "Unknown command")


def parser():
    root = Parser(prog="workspace", description="Local Workspace Core CLI")
    root.add_argument("--api", default="http://127.0.0.1:8088")
    root.add_argument("--timeout", type=float, default=30)
    groups = root.add_subparsers(dest="group", required=True, parser_class=Parser)
    def group(name, actions):
        top = groups.add_parser(name)
        return top.add_subparsers(dest="action", required=True, parser_class=Parser)
    projects = group("projects", ["list", "show", "add"])
    projects.add_parser("list")
    projects.add_parser("show").add_argument("slug")
    p = projects.add_parser("add"); p.add_argument("slug"); p.add_argument("name")
    repositories = group("repositories", ["list", "add"])
    repositories.add_parser("list").add_argument("project")
    p = repositories.add_parser("add"); p.add_argument("project"); p.add_argument("name"); p.add_argument("path"); p.add_argument("role", choices=["backend","frontend","fullstack","shared"])
    tickets = group("tickets", ["list", "history", "add", "sync"])
    tickets.add_parser("list")
    tickets.add_parser("history").add_argument("key")
    p = tickets.add_parser("add"); p.add_argument("project"); p.add_argument("key"); p.add_argument("--site", default="evolog.atlassian.net")
    p = tickets.add_parser("sync"); p.add_argument("project"); p.add_argument("key")
    runs = group("runs", ["show", "add"])
    runs.add_parser("show").add_argument("id")
    p = runs.add_parser("add"); p.add_argument("project"); p.add_argument("--ticket"); p.add_argument("--pipeline", required=True); p.add_argument("--key", required=True)
    sessions = group("sessions", ["add"])
    p = sessions.add_parser("add"); p.add_argument("run"); p.add_argument("executor", choices=["codex","claude"]); p.add_argument("--external-id"); p.add_argument("--capture-method")
    memory = group("memory", ["search", "add"])
    memory.add_parser("search").add_argument("query")
    p = memory.add_parser("add"); p.add_argument("run"); p.add_argument("source"); p.add_argument("claim")
    opensquad = group("opensquad", ["import"])
    p = opensquad.add_parser("import"); p.add_argument("project"); p.add_argument("squad"); p.add_argument("run"); p.add_argument("--ticket", required=True)
    pipelines = group("pipelines", ["start", "status", "resume"])
    p = pipelines.add_parser("start"); p.add_argument("--project", required=True); p.add_argument("--ticket", required=True); p.add_argument("--key", required=True)
    pipelines.add_parser("status").add_argument("--run", required=True)
    p = pipelines.add_parser("resume"); p.add_argument("--run", required=True); p.add_argument("--decision", choices=["investigated","approve","reject"], required=True); p.add_argument("--source-run")
    development = group("development", ["start", "status", "resume"])
    p = development.add_parser("start"); p.add_argument("--thread", required=True); p.add_argument("--issue", required=True); p.add_argument("--scenario"); p.add_argument("--executor", choices=["simulation","codex"], default="simulation"); p.add_argument("--stage", choices=["plan","work","review"], default="plan"); p.add_argument("--task-file"); p.add_argument("--executor-timeout", type=float); p.add_argument("--from-stage"); p.add_argument("--state-file")
    p = development.add_parser("status"); p.add_argument("--thread", required=True); p.add_argument("--scenario")
    p = development.add_parser("resume"); p.add_argument("--thread", required=True); p.add_argument("--scenario"); p.add_argument("--decision", choices=["resume","abort"], required=True)
    return root


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    json_output = "--json" in argv
    argv = [arg for arg in argv if arg != "--json"]
    started = time.monotonic()
    try:
        args = parser().parse_args(argv)
        if args.timeout <= 0 or args.timeout > 300:
            raise CliError("INVALID_ARGUMENT", "Timeout must be between 0 and 300 seconds")
        data = run(args)
        print(json.dumps({"data": data, "error": None}, ensure_ascii=False, separators=(",", ":") if json_output else None,
                         indent=None if json_output else 2))
        log("OK", f"{args.group}.{args.action}", int((time.monotonic() - started) * 1000))
        return 0
    except CliError as exc:
        print(json.dumps({"data": exc.data, "error": {"code": exc.code, "message": str(exc)}}, ensure_ascii=False))
        log(exc.code, "workspace", int((time.monotonic() - started) * 1000), "error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
