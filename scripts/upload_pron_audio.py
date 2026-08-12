#!/usr/bin/env python3
"""Push the pronunciation clips into Supabase, so they never touch the repo.

The mp3s in resources/pron_audio/ come from Google Translate's undocumented
translate_tts endpoint. Keeping them for personal use is one thing; committing
them to a public repo and serving them from GitHub Pages would be
redistribution. This puts them in the database instead, behind the same
`x-app-secret` gate that already protects the answer history, so the audio
reaches the learner's own devices and nobody else's.

Create the table first with supabase/pron_audio.sql.

Words already present are skipped, so a run that dies half way costs nothing
to repeat. `--refresh` re-sends them, but that is an upsert onto an existing
row, which Postgres treats as an UPDATE — the table grants only select and
insert, so --refresh needs an update policy added first.

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

    by_stem = {p.stem.replace("_", " "): p for p in AUDIO.glob("*.mp3")}
    if not by_stem:
        sys.exit(f"no clips in {AUDIO.relative_to(ROOT)} — run make_pron_audio.py first")
    folded = {k.casefold(): v for k, v in by_stem.items()}

    # Key each row by the form the deck holds, not by the filename. macOS has a
    # case-insensitive filesystem, so Mısır/mısır, Ocak/ocak and Pazar/pazar each
    # collapsed into a single clip — same pronunciation either way, but the app
    # looks a word up by its exact spelling and would have missed the capitalised
    # one. Both spellings get a row, pointing at the same bytes.
    wanted = sorted({f.strip() for i in json.loads(QUIZ.read_text(encoding="utf-8"))["items"]
                     for f in i["turkish"].split("/")})
    pairs = [(w, by_stem.get(w) or folded.get(w.casefold())) for w in wanted]
    missing = [w for w, p in pairs if p is None]
    pairs = [(w, p) for w, p in pairs if p is not None]

    present: set[str] = set()
    if not args.refresh:
        # PostgREST caps a response at 1000 rows whatever `limit` says, so this
        # has to page. Reading it in one go reported 1000 of 2036 present and
        # queued the rest for re-upload, which then failed: an upsert onto an
        # existing row needs an UPDATE policy, and the table has only select and
        # insert. The bad count was the cause; the RLS error was the symptom.
        offset = 0
        while True:
            _, rows = request(
                f"{base}/rest/v1/pron_audio?select=word&order=word"
                f"&offset={offset}&limit=1000", "GET", hdrs)
            if not rows:
                break
            present |= {r["word"] for r in rows}
            offset += len(rows)
        print(f"{len(present)} already in the table")

    todo = [(w, p) for w, p in pairs if w not in present][: args.limit]
    total = sum(p.stat().st_size for _, p in todo)
    print(f"{len(pairs)} of {len(wanted)} deck forms have a clip"
          + (f" ({len(missing)} without: {', '.join(missing[:6])})" if missing else "")
          + f"; {len(todo)} to send ({total/1e6:.1f} MB raw, ~{total*4/3/1e6:.1f} MB encoded)")
    if args.dry_run or not todo:
        return 0

    sent = 0
    url = f"{base}/rest/v1/pron_audio?on_conflict=word"
    post = dict(hdrs, Prefer="resolution=merge-duplicates,return=minimal")
    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        rows = [{"word": word,
                 "mp3_b64": base64.b64encode(path.read_bytes()).decode(),
                 "engine": "google"} for word, path in chunk]
        request(url, "POST", post, json.dumps(rows).encode())
        sent += len(chunk)
        print(f"  {sent}/{len(todo)}", flush=True)

    print(f"\ndone, {sent} clips uploaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
