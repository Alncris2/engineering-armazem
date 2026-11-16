"""Jira GET through direct HTTPS; authorization arrives on stdin."""

import argparse
import json
import sys
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    authorization = sys.stdin.readline().strip()
    if not authorization.startswith("Basic "):
        raise ValueError("Missing Jira authentication")
    site = "evolog.atlassian.net"
    url = (f"https://{site}/rest/api/3/issue/{args.key}"
           "?fields=summary,status,updated&updateHistory=false")
    request = urllib.request.Request(url, headers={"Authorization": authorization,
                                                   "Accept": "application/json"}, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=args.timeout) as response:
        issue = json.load(response)
    fields = issue.get("fields") or {}
    result = {"site": site, "key": issue.get("key"), "issue_id": str(issue.get("id") or ""),
              "summary": fields.get("summary"), "status": (fields.get("status") or {}).get("name"),
              "updated_at": fields.get("updated")}
    if result["key"] != args.key or not all(result.values()):
        raise ValueError("Jira response identity or required fields are invalid")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"Jira GET failed with HTTP {exc.code}.", file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Jira GET failed before a valid response.", file=sys.stderr)
        sys.exit(1)
