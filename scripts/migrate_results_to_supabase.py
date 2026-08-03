#!/usr/bin/env python3
"""Copy the Google Sheets results history into Supabase.

Reads the current sheet CSV (via the Apps Script endpoint, same as
stats_analysis.py) and inserts every event into public.results.

Each row gets a deterministic client_event_id derived from the event itself, so
the import is idempotent: re-running it inserts nothing new, and any duplicate
rows still present in the sheet collapse into one.

Usage:
  python3 scripts/migrate_results_to_supabase.py --dry-run
  python3 scripts/migrate_results_to_supabase.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_today import (  # noqa: E402
    build_results_csv_url,
    parse_correct,
    parse_timestamp,
    read_api_key,
    resolve_results_source,
)

ROOT = Path(__file__).resolve().parents[1]
KEYS = ROOT / "resources" / "access_keys"
SHEET_KEY_PATH = KEYS / "personal_key.txt"
SUPABASE_URL_PATH = KEYS / "supabase_url.txt"
SUPABASE_ANON_PATH = KEYS / "supabase_anon_key.txt"
SUPABASE_SECRET_PATH = KEYS / "supabase_app_secret.txt"
BATCH = 500


def read_text(path: Path, what: str) -> str:
    if not path.exists():
        raise SystemExit(f"Missing {what}: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit(f"Empty {what}: {path}")
    return value


def event_id(answered_at: str, word_id: str, mode: str, correct: bool) -> str:
    """Stable id for an event that predates client_event_id being stored."""
    raw = f"{answered_at}|{word_id}|{mode}|{correct}"
    return "sheet-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def read_endpoint_from_config() -> str:
    import re

    config = (ROOT / "web" / "config.js").read_text(encoding="utf-8")
    match = re.search(r'resultsEndpoint:\s*\n?\s*"([^"]+)"', config)
    if not match:
        raise SystemExit("Could not find resultsEndpoint in web/config.js")
    return match.group(1)


def load_sheet_rows() -> list[dict[str, str]]:
    source = resolve_results_source(read_endpoint_from_config())
    url = build_results_csv_url(source, read_api_key(SHEET_KEY_PATH))
    with urllib.request.urlopen(url, timeout=120) as response:
        text = response.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def to_records(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    skipped = 0
    for row in rows:
        ts = parse_timestamp(row.get("timestamp", ""))
        word_id = str(row.get("word_id", "")).strip()
        mode = str(row.get("mode", "")).strip()
        correct = parse_correct(row.get("correct", ""))
        if not ts or not word_id or not mode or correct is None:
            skipped += 1
            continue
        answered_at = ts.isoformat()
        cid = event_id(answered_at, word_id, mode, correct)
        # dict keyed by id => duplicate sheet rows collapse here
        records[cid] = {
            "client_event_id": cid,
            "word_id": word_id,
            "mode": mode,
            "correct": correct,
            "answered_at": answered_at,
        }
    if skipped:
        print(f"skipped {skipped} unparseable row(s)")
    return sorted(records.values(), key=lambda r: str(r["answered_at"]))


def insert(records: list[dict[str, object]], url: str, anon: str, secret: str) -> None:
    # on_conflict names the unique key so ignore-duplicates actually applies:
    # without it PostgREST targets the primary key and a repeat raises 409.
    endpoint = url.rstrip("/") + "/rest/v1/results?on_conflict=client_event_id"
    for start in range(0, len(records), BATCH):
        chunk = records[start : start + BATCH]
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(chunk).encode("utf-8"),
            method="POST",
            headers={
                "apikey": anon,
                "Authorization": f"Bearer {anon}",
                "Content-Type": "application/json",
                # ignore-duplicates makes re-running the import a no-op
                "Prefer": "resolution=ignore-duplicates,return=minimal",
                "x-app-secret": secret,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                print(f"  rows {start + 1}-{start + len(chunk)}: HTTP {response.status}")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")[:500]
            raise SystemExit(f"insert failed at row {start + 1}: HTTP {error.code}\n{body}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="parse only, do not insert")
    args = parser.parse_args()

    rows = load_sheet_rows()
    records = to_records(rows)
    print(f"sheet rows: {len(rows)} -> distinct events: {len(records)}")
    if records:
        print(f"  first: {records[0]['answered_at']}  last: {records[-1]['answered_at']}")
    if args.dry_run:
        print("dry run; nothing inserted")
        return

    insert(
        records,
        read_text(SUPABASE_URL_PATH, "Supabase project URL"),
        read_text(SUPABASE_ANON_PATH, "Supabase anon key"),
        read_text(SUPABASE_SECRET_PATH, "Supabase app secret"),
    )
    print(f"done: {len(records)} event(s) submitted")


if __name__ == "__main__":
    main()
