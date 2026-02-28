#!/usr/bin/env python3

import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "web" / "config.js"


def read_endpoint() -> str:
    override = os.environ.get("RESULTS_ENDPOINT")
    if override:
        return override.strip()

    text = CONFIG_PATH.read_text(encoding="utf-8")
    match = re.search(r"resultsEndpoint\s*:\s*\"([^\"]+)\"", text)
    if not match:
        raise ValueError("resultsEndpoint not found in web/config.js")
    return match.group(1)


def main() -> int:
    try:
        endpoint = read_endpoint()
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    api_key = os.environ.get("TR_QUIZ_API_KEY", "").strip()
    if not api_key:
        print("ERROR: TR_QUIZ_API_KEY is empty")
        return 2

    payload = {
        "timestamp": "2026-02-22T12:00:00Z",
        "word_id": "tr-0001",
        "mode": "tr-en",
        "correct": "true",
        "api_key": api_key,
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"STATUS: {response.status}")
            print(f"BODY: {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"STATUS: {exc.code}")
        print(f"BODY: {body}")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
