#!/usr/bin/env python3
"""Generate spoken audio for deck words, as an approximate pronunciation guide.

The IPA in `pron_tr` says what a word should sound like; this produces something
to listen to, which is how the transcriptions actually get checked. `boğa` was
corrected this way — the ear caught a length mark on the wrong vowel.

Two engines:

  say     macOS's built-in Turkish voice (`say -v Yelda`). Offline, no rate
          limit, no third party. Produces .aiff unless --mp3 is given.
  google  Google Translate's TTS endpoint, which is what the learner uses as a
          reference. Undocumented and unofficial, so it can change or rate-limit
          without notice; requests are throttled and failures are reported
          rather than retried hard.

Audio lands in resources/pron_audio/ (gitignored, like the rest of resources/).
Existing files are skipped, so re-running only fills gaps.

Usage:
  python3 scripts/make_pron_audio.py --tag pronunciation
  python3 scripts/make_pron_audio.py --unit unit-a2-5 --engine say
  python3 scripts/make_pron_audio.py --words boğa,oğlak,doğrudan
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / "web" / "data" / "quiz.json"
OUT = ROOT / "resources" / "pron_audio"
UA = {"User-Agent": "Mozilla/5.0"}
GOOGLE = "https://translate.google.com/translate_tts?ie=UTF-8&q={q}&tl=tr&client=tw-ob"


def forms(turkish: str) -> list[str]:
    """A slash entry holds two answers; each deserves its own recording."""
    return [p.strip() for p in turkish.split("/") if p.strip()]


def safe(name: str) -> str:
    return name.replace(" ", "_").replace("/", "-")


def say(text: str, path: Path, mp3: bool) -> None:
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-v", "Yelda", "-o", str(aiff), text], check=True)
    if mp3:
        subprocess.run(["afconvert", "-f", "mp4f", "-d", "aac", str(aiff), str(path)],
                       check=True, capture_output=True)
        aiff.unlink()


def google(text: str, path: Path) -> None:
    url = GOOGLE.format(q=urllib.parse.quote(text))
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=20).read()
    if len(data) < 500:
        raise RuntimeError(f"suspiciously small response ({len(data)} bytes)")
    path.write_bytes(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=("say", "google"), default="google")
    ap.add_argument("--tag", help="only items carrying this tag")
    ap.add_argument("--unit", help="only items in this unit tag")
    ap.add_argument("--words", help="comma-separated Turkish forms")
    ap.add_argument("--mp3", action="store_true", help="convert say output to m4a")
    ap.add_argument("--delay", type=float, default=0.6, help="seconds between requests")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    items = json.loads(QUIZ.read_text(encoding="utf-8"))["items"]
    if args.words:
        wanted = {w.strip() for w in args.words.split(",")}
        items = [i for i in items if i["turkish"] in wanted
                 or any(f in wanted for f in forms(i["turkish"]))]
    if args.tag:
        items = [i for i in items if args.tag in i.get("tags", [])]
    if args.unit:
        items = [i for i in items if args.unit in i.get("tags", [])]
    if not items:
        print("nothing matched", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    ext = ".m4a" if (args.engine == "say" and args.mp3) else (".aiff" if args.engine == "say" else ".mp3")
    made = skipped = failed = 0
    for item in items[: args.limit]:
        for form in forms(item["turkish"]):
            path = OUT / f"{safe(form)}{ext}"
            if path.exists():
                skipped += 1
                continue
            try:
                if args.engine == "say":
                    say(form, path, args.mp3)
                else:
                    google(form, path)
                    time.sleep(args.delay)
                made += 1
                print(f"  {form:24s} {item.get('pron_tr','') or '—'}")
            except Exception as exc:
                failed += 1
                print(f"  {form:24s} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)

    print(f"\n{made} written, {skipped} already present, {failed} failed -> {OUT.relative_to(ROOT)}")
    return 1 if failed and not made else 0


if __name__ == "__main__":
    raise SystemExit(main())
