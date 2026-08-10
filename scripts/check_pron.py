#!/usr/bin/env python3
"""Check every pron_tr in the deck against Wiktionary.

The transcriptions are hand-written, which means they can be hand-wrong: a rule
applied where it does not hold, a consonant dropped. This looks each word up on
en.wiktionary (Turkish section only) and tr.wiktionary and prints what they say
next to what the deck says, so disagreements can be adjudicated by hand.

It deliberately does not edit anything. Wiktionary is a good check, not an
authority to copy blindly: it is inconsistent about narrow vs broad transcription
and about which allophones it marks.

eSpeak was tried here as a third column and removed. It is a letter-to-sound
transducer with a short exception list, so it cannot know lexical facts: it
misses the long vowel in misafir, adalet, ifade, sade, adet, terazi and vahşi
alike, and ignores the circumflex. Worse for a checker, its output agreeing with
a rule-derived transcription is not corroboration — it is the same rule twice.

Usage:
  python3 scripts/check_pron.py                # everything carrying pron_tr
  python3 scripts/check_pron.py --words boğa,oğlak
  python3 scripts/check_pron.py --unit unit-a2-5 --all   # include untranscribed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / "web" / "data" / "quiz.json"
UA = {"User-Agent": "kielikone-pron/1.0 (personal vocabulary deck; github valpola/kielikone)"}
IPA_SPAN = re.compile(r'class="IPA[^"]*"[^>]*>([^<]+)<')


class Failed(Exception):
    """A request that never got an answer — distinct from a page with no IPA.

    Swallowing these makes a network problem look like evidence of absence, which
    has already produced one wrong conclusion in this project.
    """


def fetch(site: str, word: str, tries: int = 3) -> list[str]:
    url = (f"https://{site}.wiktionary.org/w/api.php?action=parse"
           f"&page={urllib.parse.quote(word)}&prop=text&format=json&formatversion=2")
    last = None
    for attempt in range(tries):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
            data = json.loads(raw.decode())
            break
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    else:
        raise Failed(f"{site}:{word}: {type(last).__name__}")
    if "error" in data:
        return []
    html = data["parse"]["text"]
    if site == "en":
        # en.wiktionary stacks many languages on one page; keep only Turkish
        m = re.search(r'id="Turkish".*?(?=<h2\b|\Z)', html, re.S)
        html = m.group(0) if m else ""
    seen, out = set(), []
    for hit in IPA_SPAN.findall(html):
        hit = hit.strip()
        if hit and hit not in seen:
            seen.add(hit)
            out.append(hit)
    return out[:3]


def heads(turkish: str) -> list[str]:
    """Look up the lexical head, not the phrase: 'şahit olmak' -> 'şahit'."""
    parts = [p.strip() for p in turkish.split("/") if p.strip()]
    out = []
    for p in parts:
        words = p.split()
        out.append(words[0] if len(words) > 1 else p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--words")
    ap.add_argument("--unit")
    ap.add_argument("--all", action="store_true", help="include items with no pron_tr")
    ap.add_argument("--delay", type=float, default=0.4)
    args = ap.parse_args()

    items = json.loads(QUIZ.read_text(encoding="utf-8"))["items"]
    if args.unit:
        items = [i for i in items if args.unit in i.get("tags", [])]
    if args.words:
        want = {w.strip() for w in args.words.split(",")}
        items = [i for i in items if i["turkish"] in want or any(h in want for h in heads(i["turkish"]))]
    elif not args.all:
        items = [i for i in items if i.get("pron_tr")]

    agree = differ = nosource = 0
    print(f"{'word':22s} {'deck':22s} {'en.wiktionary':26s} tr.wiktionary")
    print("-" * 100)
    for item in sorted(items, key=lambda i: i["turkish"]):
        for head in heads(item["turkish"]):
            try:
                en, tr = fetch("en", head), fetch("tr", head)
            except Failed as exc:
                print(f"{head:22s} REQUEST FAILED — {exc}", file=sys.stderr)
                continue
            time.sleep(args.delay)
            mine = item.get("pron_tr", "") or "—"
            src = " ".join(en + tr)
            if not src:
                nosource += 1
                flag = "no source"
            else:
                # compare on symbols that matter, ignoring brackets and diacritics
                # Strip only notation: brackets, syllable dots, ties, secondary
                # stress. Never fold vowel quality — an earlier version stripped
                # enough to call bæn a match for /ˈben/, hiding a real error.
                norm = lambda s: re.sub(r"[/\[\]()ˌ.‿ \u0361]", "", s).replace("ɑ", "a").replace("ɫ", "l")
                flag = "ok" if any(norm(mine) == norm(x) for x in en + tr) else "DIFFERS"
                agree += flag == "ok"
                differ += flag == "DIFFERS"
            print(f"{head:22s} {mine:22s} {(en[0] if en else '—')[:25]:26s} "
                  f"{(tr[0] if tr else '—')[:22]:24s} {flag}")
    print(f"\nmatched {agree}, differ {differ}, no source {nosource}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
