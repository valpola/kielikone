#!/usr/bin/env python3
"""Cache TDK's pronunciation field for every word in the deck.

TDK (sozluk.gov.tr) publishes a `telaffuz` only for words whose pronunciation
does not follow from the spelling — overwhelmingly Arabic, Persian and French
loans with phonemic length, a stress that is not final, or an `l` that stays
clear next to a back vowel. Regular Turkish words return nothing at all, so the
presence of the field is itself the signal that a word is worth recording.

Its notation is *not* IPA:

    ada:let      `:` marks the preceding vowel long
    a'nkara      `'` follows the *stressed vowel* (IPA's ˈ precedes the syllable)
    l ince okunur   prose note: the l is clear, not the dark [ɫ] a back vowel
                    would normally give

so the conversion is done separately, deliberately, not here. This script only
fetches and caches, and never edits the deck.

Needs a browser User-Agent: the default urllib one is refused, which once made
an entire run look like "no entry" for every word.

Usage:
  python3 scripts/fetch_tdk_pron.py            # fill gaps in the cache
  python3 scripts/fetch_tdk_pron.py --refetch  # ignore the cache
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / "web" / "data" / "quiz.json"
CACHE = ROOT / "resources" / "tdk_pron_cache.json"
UA = {"User-Agent": "Mozilla/5.0"}


def forms(turkish: str) -> list[str]:
    """Every single word worth looking up in an entry.

    Phrases are looked up word by word: `şahit olmak` hides the long vowel of
    `şahit`, and `olmak` is regular, so querying the phrase would find nothing.
    """
    out: list[str] = []
    for part in turkish.split("/"):
        for word in part.split():
            w = word.strip("()!?,.").strip()
            if len(w) > 1:
                out.append(w)
    return out


def query(word: str) -> dict:
    url = "https://sozluk.gov.tr/gts?ara=" + urllib.parse.quote(word)
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()
    data = json.loads(raw.decode())
    if isinstance(data, dict):           # {"error": "Sonuç bulunamadı"}
        return {"found": False}
    out = {"found": True, "telaffuz": None, "lisan": None, "senses": []}
    for entry in data:
        if entry.get("telaffuz") and not out["telaffuz"]:
            out["telaffuz"] = entry["telaffuz"]
            out["lisan"] = entry.get("lisan")
        for sense in (entry.get("anlamlarListe") or [])[:1]:
            out["senses"].append(sense.get("anlam", "")[:60])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--delay", type=float, default=0.35)
    args = ap.parse_args()

    cache = {} if args.refetch or not CACHE.exists() else json.loads(CACHE.read_text(encoding="utf-8"))
    items = json.loads(QUIZ.read_text(encoding="utf-8"))["items"]
    words = sorted({w for i in items for w in forms(i["turkish"])})
    todo = [w for w in words if w not in cache]
    print(f"{len(words)} distinct words in the deck; {len(todo)} not yet cached", flush=True)

    failed = 0
    for n, word in enumerate(todo, 1):
        try:
            cache[word] = query(word)
        except Exception as exc:
            failed += 1
            print(f"  FAILED {word}: {type(exc).__name__}", file=sys.stderr, flush=True)
        if n % 100 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            have = sum(1 for v in cache.values() if v.get("telaffuz"))
            print(f"  {n}/{len(todo)} fetched, {have} with a pronunciation so far", flush=True)
        time.sleep(args.delay)

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    have = [w for w, v in cache.items() if v.get("telaffuz")]
    print(f"\ncached {len(cache)} words, {len(have)} carry a TDK pronunciation, {failed} failed")
    print(f"-> {CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
