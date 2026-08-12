#!/usr/bin/env python3
"""Fill `infl_tr` from TDK's `taki` field: the stem alternation, shown not told.

Turkish spelling hides what happens when a vowel-initial suffix lands on a stem,
and the change is not derivable from the letters — `dört` softens but `üç` does
not, `mektup` and `akrep` soften but `direkt` does not. TDK records the outcome
per word in `taki`, a tail such as `bi` (akrep) or `hri` (şehir). This turns that
tail back into the full form, so a card can show `akrep → akrebi` instead of
leaving the learner to guess.

The tail encodes four different operations and its *shape* is what says which:

    bi            plain softening          akrep  -> akrebi
    hri           a dropped stem vowel     şehir  -> şehri
    rrı           gemination               sır    -> sırrı
    yı            a buffer consonant       ayakkabı -> ayakkabıyı
    mzu, -uzu     two accepted forms       omuz   -> omzu / omuzu
    k'ı           proper noun, apostrophe  Baltık -> Baltık'ı
    der / ır      a verb aorist            gitmek -> gider

A single rule over all of these produces confident nonsense — an earlier version
gave `gitmek → gitmeder`, `ayakkabı → ayı` and `sır → rrı` — so each shape is
handled on its own and the whole output is meant to be read before applying.

Verbs are reported but not written: an aorist is a different phenomenon from a
stem alternation, and `alır` on a card without a label would puzzle rather than
teach. Nominals only, and single-word entries only — in a phrase it would not be
clear which word the form belongs to.

`taki` is a *positive* attestation and nothing more. Where it is absent TDK has
simply not said: for nouns that usually does mean no softening (`sepet`,
`avukat`, `bilet`), but `yumuşak` carries no tail on either TDK endpoint despite
`yumuşağı` being right. So absence is never written as "does not soften".

Usage:
  python3 scripts/tdk_alternations.py             # list what it would write
  python3 scripts/tdk_alternations.py --verbs     # the verb aorists too
  python3 scripts/tdk_alternations.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "resources" / "tdk_cache.jsonl"
CANDIDATES = ROOT / "data" / "candidates"

VOWELS = "aeıioöuüâîû"
LATER_SENSE_ONLY: list[str] = []

# Where the deck's sense is not TDK's first. Checked one by one against the
# gloss the deck actually carries: of the twelve homographs the first-sense rule
# sets aside, only `sır` is the later sense here — the deck means "secret"
# (TDK sense 2, rrı), not the glaze of sense 1. The rest are correctly dropped:
# the deck's `koyun` is the sheep, not the bosom that gives `koynu`, and its
# `şık` is "elegant", not the "option" that gives `şıkkı`.
OVERRIDE = {"sır": "rrı"}
NOTE = ("Inflected form from TDK's taki field, which attests the stem "
        "alternation rather than leaving it to a rule.")


def is_verb(word: str, taki: str) -> bool:
    """A verb, not a noun that happens to end in -mek.

    The infinitive ending is not enough: `ekmek` (bread) and `mercimek` are
    nouns, and treating them as verbs produced `eği` and `mercği`. An aorist
    tail always ends in -r, and a nominal tail never does, which separates them
    cleanly.
    """
    return word.endswith(("mak", "mek")) and taki.split(",")[0].strip().endswith("r")


def inflect(word: str, taki: str) -> list[str]:
    """Rebuild the full inflected form(s) from TDK's tail."""
    out: list[str] = []
    for raw in (x.strip() for x in taki.split(",")):
        if not raw:
            continue
        # A leading hyphen marks the variant that keeps the stem vowel: the tail
        # then starts *inside* the stem (omuz, -uzu -> om|uzu).
        keeps_vowel = raw.startswith("-")
        tail = raw.lstrip("-")
        if "'" in tail:                                   # Baltık, k'ı
            out.append(word[:-1] + tail)
        elif keeps_vowel:
            out.append(word[: -(len(tail) - 1)] + tail)
        elif is_verb(word, taki):                         # aorist, on the stem
            stem = word[:-3]
            out.append(stem + tail if tail[0] in VOWELS else stem[:-1] + tail)
        elif word[-1] in VOWELS:                          # buffer y
            out.append(word + tail)
        elif len(tail) >= 3 and tail[0] == tail[1]:        # sır, rrı
            out.append(word[:-1] + tail)
        elif len(tail) >= 3:                               # şehir, hri
            out.append(word[: -len(tail)] + tail)
        else:                                              # akrep, bi
            out.append(word[:-1] + tail)
    return out


def alters_stem(word: str, forms: list[str], k: str) -> bool:
    """Is there actually something to show?

    TDK lists a tail for reasons beyond alternation — to fix the vowel harmony of
    an `l` word, or to show a proper noun's apostrophe. `terminal -> terminali`
    teaches nothing, and `sol -> solü` is worse than nothing: that is TDK's
    musical note G, while the deck's `sol` means "left" and gives `solu`. So a
    tail only earns a card when the stem itself comes out different.

    Gemination is exempt: `sır -> sırrı` leaves the stem intact at the front but
    is exactly the kind of surprise this field exists for.
    """
    if k == "gemination":
        return True
    if any(f[: len(word)] != word for f in forms):
        return True
    # A tail that changes nothing still teaches something when the word ends in
    # p/ç/t/k, because softening was the thing to expect and it did not happen:
    # saat -> saati, not saadi, against the polysyllabic tendency. Proper nouns
    # are excluded — there the apostrophe is the lesson, not the consonant.
    return word[-1].lower() in "pçtk" and k != "proper"


def kind(word: str, taki: str) -> str:
    if is_verb(word, taki):
        return "aorist"
    first = taki.split(",")[0].strip()
    if "'" in first:
        return "proper"
    if word[-1] in VOWELS:
        return "buffer"
    if len(first) >= 3 and first[0] == first[1]:
        return "gemination"
    if len(first) >= 3:
        return "vowel drop"
    return "softening"


def load_taki() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["status"] != "found":
            continue
        # The first sense only. `sol` lists no tail for "left" and `lü` for the
        # musical note G; taking the first *non-empty* tail imported the note's
        # morphology onto the deck's "left" card.
        first = rec["response"][0] if rec["response"] else {}
        if first.get("taki"):
            out[rec["word"]] = first["taki"]
        elif any(e.get("taki") for e in rec["response"][1:]):
            LATER_SENSE_ONLY.append(rec["word"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verbs", action="store_true", help="also list verb aorists")
    args = ap.parse_args()

    if not CACHE.exists():
        print("no TDK cache — run scripts/fetch_tdk.py first", file=sys.stderr)
        return 1
    taki = load_taki() | OVERRIDE

    files = sorted(CANDIDATES.glob("*.candidates.json"))
    planned: list[tuple[str, str, str, str]] = []   # file, word, kind, forms
    verbs: list[tuple[str, str]] = []
    changed: dict[Path, dict] = {}

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for item in data["items"]:
            word = item["turkish"].strip()
            if " " in word or "/" in word or word not in taki:
                continue
            k = kind(word, taki[word])
            forms = inflect(word, taki[word])
            if not forms or any(len(f) < len(word) for f in forms):
                print(f"  SUSPECT {word} + {taki[word]!r} -> {forms}", file=sys.stderr)
                continue
            if k == "aorist":
                verbs.append((word, " / ".join(forms)))
                continue
            if not alters_stem(word, forms, k):
                continue
            value = " / ".join(forms)
            planned.append((path.name, word, k, value))
            if item.get("infl_tr") != value:
                item["infl_tr"] = value
                note = item.get("notes", "").rstrip()
                if NOTE not in note:
                    item["notes"] = (note + " " + NOTE).strip()
                touched = True
        if touched:
            changed[path] = data

    by_kind: dict[str, list[tuple[str, str]]] = {}
    for _, word, k, value in planned:
        by_kind.setdefault(k, []).append((word, value))
    for k in sorted(by_kind):
        rows = by_kind[k]
        print(f"\n{k} ({len(rows)})")
        for word, value in sorted(rows):
            print(f"    {word:18s} -> {value}")
    if args.verbs:
        print(f"\naorist, not written ({len(verbs)})")
        for word, value in sorted(verbs):
            print(f"    {word:18s} -> {value}")

    if LATER_SENSE_ONLY:
        print(f"\nskipped, tail only on a later sense ({len(LATER_SENSE_ONLY)}): "
              + ", ".join(sorted(LATER_SENSE_ONLY)))
    print(f"\n{len(planned)} nominal alternations, {len(verbs)} verb aorists "
          f"(not written), across {len(changed)} file(s)")
    if args.apply:
        for path, data in changed.items():
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"written to {len(changed)} candidate file(s)")
    else:
        print("dry run — pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
