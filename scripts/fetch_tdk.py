#!/usr/bin/env python3
"""Cache TDK's full dictionary response for every word in the deck.

Stores the *whole* response rather than the fields wanted today. An earlier
version extracted only `telaffuz`, which meant the `taki` field — the one that
actually carries the stem alternations (`şehir` → `hri`, `akrep` → `bi`) — was
discarded on 1963 requests and had to be fetched again. The response is ~9 KB a
word, so the entire deck is about 18 MB: cheaper to keep than to re-fetch.

What a response holds, beyond the two fields used so far:

    telaffuz     pronunciation, only where it does not follow from spelling
    taki         the inflected tail: softening and vowel drop
    lisan        source language ("Arapça ʿaḳreb", "Farsça şehr")
    birlesikler  compounds the word heads ("şehir merkezi, büyükşehir, …")
    atasozu      proverbs and idioms containing it
    anlamlarListe  every sense, with example sentences and their authors,
                   plus ozelliklerListe giving part of speech and register

Written as JSONL, one line per word, appended as it goes: a run that dies
half way loses nothing and re-running picks up the rest.

Needs a browser User-Agent — urllib's default is refused, which once made a
whole run look like "no entry" for every word.

Usage:
  python3 scripts/fetch_tdk.py             # fetch whatever is missing
  python3 scripts/fetch_tdk.py --refetch   # start over
  python3 scripts/fetch_tdk.py --stats     # summarise the cache, fetch nothing
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / "web" / "data" / "quiz.json"
CACHE = ROOT / "resources" / "tdk_cache.jsonl"
UA = {"User-Agent": "Mozilla/5.0"}


def forms(turkish: str) -> list[str]:
    """Every single word worth looking up.

    Phrases go word by word: `şahit olmak` hides the long vowel of `şahit`, and
    querying the phrase itself finds nothing.
    """
    out: list[str] = []
    for part in turkish.split("/"):
        for word in part.split():
            w = word.strip("()!?,.").strip()
            if len(w) > 1:
                out.append(w)
    return out


def load() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    out = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["word"]] = rec
    return out


def stats(cache: dict[str, dict]) -> None:
    found = [r for r in cache.values() if r["status"] == "found"]
    def has(field):
        return sum(1 for r in found for e in r["response"] if e.get(field))
    print(f"  cached          {len(cache)}")
    print(f"  found in TDK    {len(found)}")
    print(f"  with telaffuz   {sum(1 for r in found if any(e.get('telaffuz') for e in r['response']))}")
    print(f"  with taki       {sum(1 for r in found if any(e.get('taki') for e in r['response']))}")
    print(f"  with lisan      {sum(1 for r in found if any(e.get('lisan') for e in r['response']))}")
    print(f"  with atasozu    {sum(1 for r in found if any(e.get('atasozu') for e in r['response']))}")
    print(f"  with birlesikler{sum(1 for r in found if any(e.get('birlesikler') for e in r['response'])):>4}")
    if CACHE.exists():
        print(f"  file size       {CACHE.stat().st_size / 1_000_000:.1f} MB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--delay", type=float, default=0.35)
    args = ap.parse_args()

    cache = {} if args.refetch else load()
    if args.stats:
        stats(cache)
        return 0
    if args.refetch and CACHE.exists():
        CACHE.unlink()

    items = json.loads(QUIZ.read_text(encoding="utf-8"))["items"]
    words = sorted({w for i in items for w in forms(i["turkish"])})
    # A recorded failure still needs fetching — otherwise a transient network
    # error becomes a permanent hole that looks like a completed cache.
    todo = [w for w in words if w not in cache or cache[w]["status"] == "failed"]
    print(f"{len(words)} distinct words; {len(todo)} to fetch", flush=True)

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    failed = 0
    with CACHE.open("a", encoding="utf-8") as fh:
        for n, word in enumerate(todo, 1):
            url = "https://sozluk.gov.tr/gts?ara=" + urllib.parse.quote(word)
            rec = {"word": word, "fetched_at": datetime.now(timezone.utc).isoformat()}
            try:
                raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()
                data = json.loads(raw.decode())
                if isinstance(data, dict):        # {"error": "Sonuç bulunamadı"}
                    rec |= {"status": "notfound", "response": []}
                else:
                    rec |= {"status": "found", "response": data}
            except Exception as exc:
                failed += 1
                # Recorded, not silently skipped: an absent line means "not tried",
                # which is a different thing from "TDK has nothing".
                rec |= {"status": "failed", "error": f"{type(exc).__name__}", "response": []}
                print(f"  FAILED {word}: {type(exc).__name__}", file=sys.stderr, flush=True)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if n % 200 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
            time.sleep(args.delay)

    print(f"\ndone, {failed} failed\n")
    stats(load())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
