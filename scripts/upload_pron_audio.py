#!/usr/bin/env python3
"""Push the pronunciation clips into Supabase, so they never touch the repo.

The mp3s in resources/pron_audio/ come from Google Translate's undocumented
translate_tts endpoint. Keeping them for personal use is one thing; committing
them to a public repo and serving them from GitHub Pages would be
redistribution. This puts them in the database instead, behind the same
`x-app-secret` gate that already protects the answer history, so the audio
reaches the learner's own devices and nobody else's.

Create the table first with supabase/pron_audio.sql.

Rows are upserted on `word`, and words already present are skipped unless
--refresh is given, so a run that dies half way costs nothing to repeat.

Usage:
  python3 scripts/upload_pron_audio.py --dry-run
  python3 scripts/upload_pron_audio.py
  python3 scripts/upload_pron_audio.py --refresh      # re-send what is there
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "resources" / "pron_audio"
KEYS = ROOT / "resources" / "access_keys"
QUIZ = ROOT / "web" / "data" / "quiz.json"
BATCH = 20          # ~20 clips a request keeps each POST around 200 KB


def secret(name: str) -> str:
    path = KEYS / name
    if not path.exists():
        sys.exit(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8").strip()


def headers(url_key: str) -> dict[str, str]:
    return {
        "apikey": url_key,
        "Authorization": f"Bearer {url_key}",
        "x-app-secret": secret("supabase_app_secret.txt"),
        "Content-Type": "application/json",
    }


def request(url: str, method: str, hdrs: dict, body: bytes | None = None):
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        # The body carries PostgREST's actual complaint; without it every
        # failure looks like a bare 400 and says nothing about the cause.
        sys.exit(f"{method} {url.split('?')[0]} -> {exc.code}: {exc.read().decode()[:400]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-send words already there")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    base = secret("supabase_url.txt").rstrip("/")
    key = secret("supabase_anon_key.txt")
    hdrs = headers(key)

    files = sorted(AUDIO.glob("*.mp3"))
    if not files:
        sys.exit(f"no clips in {AUDIO.relative_to(ROOT)} — run make_pron_audio.py first")

    # Only words the deck actually asks for; a stale clip helps nobody.
    wanted = {f.strip() for i in json.loads(QUIZ.read_text(encoding="utf-8"))["items"]
              for f in i["turkish"].split("/")}
    files = [f for f in files if f.stem.replace("_", " ") in wanted]

    present: set[str] = set()
    if not args.refresh:
        status, rows = request(f"{base}/rest/v1/pron_audio?select=word", "GET", hdrs)
        present = {r["word"] for r in (rows or [])}
        print(f"{len(present)} already in the table")

    todo = [f for f in files if f.stem.replace("_", " ") not in present][: args.limit]
    total = sum(f.stat().st_size for f in todo)
    print(f"{len(files)} clips match the deck; {len(todo)} to send "
          f"({total/1e6:.1f} MB raw, ~{total*4/3/1e6:.1f} MB encoded)")
    if args.dry_run or not todo:
        return 0

    sent = 0
    url = f"{base}/rest/v1/pron_audio?on_conflict=word"
    post = dict(hdrs, Prefer="resolution=merge-duplicates,return=minimal")
    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        rows = [{"word": f.stem.replace("_", " "),
                 "mp3_b64": base64.b64encode(f.read_bytes()).decode(),
                 "engine": "google"} for f in chunk]
        request(url, "POST", post, json.dumps(rows).encode())
        sent += len(chunk)
        print(f"  {sent}/{len(todo)}", flush=True)

    print(f"\ndone, {sent} clips uploaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
