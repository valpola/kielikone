#!/usr/bin/env python3
"""Convert TDK's telaffuz notation into the IPA the deck stores.

TDK gives exactly the facts that cannot be derived — vowel length, stress that
is not final, and an occasional prose note about `l` — in a notation of its own:

    ada:let          `:` makes the *preceding* vowel long
    sine'ma          `'` follows the *stressed vowel*; IPA's ˈ precedes the
                     whole syllable, so the mark has to move left past the onset
    la:civert, l ince okunur    the l is clear [l], not the dark [ɫ] a back
                                vowel would otherwise give

Everything else is spelling-to-sound, which Turkish makes regular, plus the
allophony this project has already checked against sources: `[æ]` before a
sonorant against `[e]` elsewhere, `k`/`g` palatalised to `[c]`/`[ɟ]` beside
front vowels, and `[l]`/`[ɫ]` by vowel backness.

What is *sourced* here is length and stress. What is *derived* is the segments.
That split is worth keeping in mind when reading the output: the derivation has
been wrong before, and the note on each entry records which half is which.

Entries whose telaffuz is really an inflected form — `akrep → akrebi`, showing
final-consonant softening rather than pronunciation — are skipped, not converted.

Usage:
  python3 scripts/tdk_to_ipa.py --sample 25      # look before applying
  python3 scripts/tdk_to_ipa.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / "web" / "data" / "quiz.json"
CACHE = ROOT / "resources" / "tdk_pron_cache.json"
CANDIDATES = ROOT / "data" / "candidates"

VOWELS = "aeıioöuü"
FRONT = "eiöü"
SONORANT = "rlmn"

CONS = {"c": "dʒ", "ç": "tʃ", "ş": "ʃ", "j": "ʒ", "y": "j", "r": "ɾ",
        "v": "v", "b": "b", "d": "d", "f": "f", "h": "h", "m": "m",
        "n": "n", "p": "p", "s": "s", "t": "t", "z": "z"}
VOW = {"a": "ɑ", "e": "e", "ı": "ɯ", "i": "i", "o": "o", "ö": "ø", "u": "u", "ü": "y"}


def strip_note(telaffuz: str) -> tuple[str, bool]:
    """Split the prose note off. Returns (bare form, l-is-clear)."""
    parts = [p.strip() for p in telaffuz.split(",")]
    clear_l = any("ince" in p for p in parts[1:])
    return parts[0], clear_l


def is_inflected(word: str, bare: str) -> bool:
    """TDK sometimes gives an inflected form to show consonant softening."""
    plain = bare.replace(":", "").replace("'", "").replace("â", "a").replace("î", "i")
    w = word.lower().replace("â", "a").replace("î", "i").replace("İ", "i")
    # A suffixed form is simply longer: akrep -> akrebi, balık -> balığı.
    return len(plain) > len(w) or not plain.startswith(w[:-1])


def convert(word: str, telaffuz: str) -> str | None:
    bare, clear_l = strip_note(telaffuz)
    if not bare or is_inflected(word, bare):
        return None

    # Walk the string, emitting IPA and remembering where each syllable starts.
    out: list[str] = []
    stress_at: int | None = None          # index in `out` of the stressed vowel
    syllable_starts: list[int] = []
    chars = list(bare)
    i = 0
    while i < len(chars):
        ch = chars[i]
        low = ch.lower()
        if low in VOWELS:
            syllable_starts.append(len(out))
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            after = chars[i + 2] if i + 2 < len(chars) else ""
            # e is open before a sonorant that closes the syllable
            if low == "e" and nxt.lower() in SONORANT and (after == "" or after.lower() not in VOWELS):
                out.append("æ")
            else:
                out.append(VOW[low])
            if nxt == ":":
                out.append("ː")
                i += 1
            if i + 1 < len(chars) and chars[i + 1] == "'":
                stress_at = len(syllable_starts) - 1
                i += 1
        elif low in ("k", "g", "l"):
            prev = next((c.lower() for c in reversed(chars[:i]) if c.lower() in VOWELS), "")
            nxt = next((c.lower() for c in chars[i + 1:] if c.lower() in VOWELS), "")
            front = (nxt or prev) in FRONT
            if low == "k":
                out.append("c" if front else "k")
            elif low == "g":
                out.append("ɟ" if front else "ɡ")
            else:
                out.append("l" if (front or clear_l) else "ɫ")
        elif low in CONS:
            out.append(CONS[low])
        elif low == "ğ":
            return None                    # ğ is never taken from a rule here
        elif low in "âîû":
            syllable_starts.append(len(out))
            out.append({"â": "ɑ", "î": "i", "û": "u"}[low] + "ː")
        i += 1

    if not syllable_starts:
        return None
    # IPA marks the syllable, not the vowel: walk left past a single onset.
    idx = stress_at if stress_at is not None else len(syllable_starts) - 1
    target = syllable_starts[idx]
    onset = target
    # Move left over this syllable's onset. Turkish allows one onset consonant,
    # so stop at the previous vowel (or the start of the word).
    floor = syllable_starts[idx - 1] + 1 if idx > 0 else 0
    if onset > floor and out[onset - 1] != "ː":
        onset -= 1
    out.insert(onset, "ˈ")
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not CACHE.exists():
        print("no cache yet — run fetch_tdk_pron.py first", file=sys.stderr)
        return 1
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    have = {w: v["telaffuz"] for w, v in cache.items() if v.get("telaffuz")}

    converted, skipped = {}, []
    for word, tel in have.items():
        ipa = convert(word, tel)
        (converted.__setitem__(word, (tel, ipa)) if ipa else skipped.append((word, tel)))

    print(f"{len(have)} words with a TDK pronunciation; "
          f"{len(converted)} converted, {len(skipped)} skipped (inflected form or ğ)")
    if args.sample:
        print(f"\n{'word':16s} {'TDK':22s} IPA")
        for w, (tel, ipa) in list(sorted(converted.items()))[: args.sample]:
            print(f"  {w:16s} {tel:22s} {ipa}")
        print(f"\nskipped, e.g.: {[f'{w} -> {t}' for w, t in skipped[:6]]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
