"""Read Loki query results from Grafana using HTTP GET only."""

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request


def query_range(base_url, token, query, start, end, timeout=20, datasource_uid=None, username=None, password=None):
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")):
        raise ValueError("Grafana URL must use HTTPS or loopback HTTP")
    if not query or len(query) > 2000:
        raise ValueError("Invalid Loki query")
    params = urllib.parse.urlencode({"query": query, "start": start, "end": end, "limit": 100})
    if datasource_uid and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", datasource_uid):
        raise ValueError("Invalid Grafana datasource UID")
    path = (f"/api/datasources/proxy/uid/{datasource_uid}" if datasource_uid else "")
    url = base_url.rstrip("/") + path + "/loki/api/v1/query_range?" + params
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    elif username and password:
        pair = (username + ":" + password).encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(pair).decode("ascii")
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        result = query_range(os.environ["GRAFANA_URL"], os.environ.get("GRAFANA_TOKEN"),
                             args.query, args.start, args.end, args.timeout,
                             os.environ.get("GRAFANA_DATASOURCE_UID"),
                             os.environ.get("GRAFANA_USERNAME"), os.environ.get("GRAFANA_PASSWORD"))
        print(json.dumps({"data": result, "error": None}))
    except (KeyError, OSError, ValueError) as exc:
        print(json.dumps({"data": None, "error": {"code": "GRAFANA_READ_FAILED",
                                                 "message": "Grafana query failed or is not configured"}}))
        sys.exit(1)
