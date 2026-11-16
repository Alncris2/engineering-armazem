"""Read structured ticket history from the local Workspace Core API."""

import argparse
import json
import urllib.request


def history(ticket_id: str, base_url: str = "http://127.0.0.1:8088") -> dict:
    if not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError("The API must be on loopback")
    with urllib.request.urlopen(f"{base_url}/api/tickets/{ticket_id}/history", timeout=10) as response:
        return json.load(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticket_id")
    parser.add_argument("--api", default="http://127.0.0.1:8088")
    args = parser.parse_args()
    print(json.dumps(history(args.ticket_id, args.api), ensure_ascii=False, indent=2))
