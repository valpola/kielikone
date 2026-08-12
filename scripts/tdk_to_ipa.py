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
been wrong before.

Three things are refused rather than guessed:

  * `ğ`, whose effect varies word by word and is only ever written by ear.
  * A telaffuz that is really an inflected form (akrep -> akrebi).
  * A word whose TDK senses disagree about the pronunciation. There are five —
    ama/âmâ, hala/hâlâ, ilahi, tabii — and each is two different words sharing a
    spelling. Reading across senses is what produced `sol -> solü` in
    tdk_alternations.py and what made one `ilahi` out of three, so the sense is
    taken from the first entry only and a disagreement stops the word entirely.

An existing pron_tr is never overwritten: those were hand-written and checked
against sources, so a difference is reported for a human to settle.

Usage:
  python3 scripts/tdk_to_ipa.py --sample 30      # look before applying
  python3 scripts/tdk_to_ipa.py --conflicts      # where TDK differs from the deck
  python3 scripts/tdk_to_ipa.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "resources" / "tdk_cache.jsonl"
CANDIDATES = ROOT / "data" / "candidates"

VOWELS = "aeıioöuü"
FRONT = "eiöüî"          # î is a long i, so it fronts a neighbouring k/g/l too
SONORANT = "rlmn"

CONS = {"c": "dʒ", "ç": "tʃ", "ş": "ʃ", "j": "ʒ", "y": "j", "r": "ɾ",
        "v": "v", "b": "b", "d": "d", "f": "f", "h": "h", "m": "m",
        "n": "n", "p": "p", "s": "s", "t": "t", "z": "z"}
VOW = {"a": "ɑ", "e": "e", "ı": "ɯ", "i": "i", "o": "o", "ö": "ø", "u": "u", "ü": "y"}

NOTE = ("Pronunciation from TDK's telaffuz field, which records the length and "
        "stress that the spelling does not; the segments follow the deck's "
        "established allophony.")


def is_vowel(ch: str) -> bool:
    """Guarded membership test.

    `"" in "aeiou"` is True, which has now produced two separate bugs in this
    file: every word-final `e` came out as [æ], and every word-final `k` was
    treated as a syllable onset and palatalised (birçok -> ˈbiɾtʃoc). Every
    lookahead here can run off the end of the word, so none of them may use a
    bare `in`.
    """
    return bool(ch) and (ch in VOWELS or ch in "âîû")


def strip_note(telaffuz: str) -> tuple[str, bool]:
    """Split the prose note off. Returns (bare form, l-is-clear)."""
    parts = [p.strip() for p in telaffuz.split(",")]
    clear_l = any("ince" in p for p in parts[1:])
    return parts[0], clear_l


def is_inflected(word: str, bare: str) -> bool:
    """TDK sometimes gives an inflected form to show consonant softening."""
    plain = bare.replace(":", "").replace("'", "").replace("â", "a").replace("î", "i")
    w = word.lower().replace("â", "a").replace("î", "i").replace("İ", "i")
    return len(plain) > len(w) or not plain.startswith(w[:-1])


def convert(word: str, telaffuz: str) -> str | None:
    bare, clear_l = strip_note(telaffuz)
    if not bare or is_inflected(word, bare):
        return None

    # Pull the length and stress marks out of the letter stream first. Leaving
    # them in breaks every lookahead: TDK writes belki as be'lki, so the `e`
    # looking for a following sonorant found an apostrophe and missed the [æ].
    letters: list[str] = []
    long_at: set[int] = set()
    stress_letter: int | None = None
    for ch in bare:
        if ch == ":":
            if letters:
                long_at.add(len(letters) - 1)
        elif ch == "'":
            # The mark follows the stressed vowel, so walk back to it.
            for j in range(len(letters) - 1, -1, -1):
                if is_vowel(letters[j]):
                    stress_letter = j
                    break
        else:
            letters.append(ch.lower())

    out: list[str] = []
    stress_at: int | None = None
    syllable_starts: list[int] = []
    for i, low in enumerate(letters):
        if is_vowel(low):
            syllable_starts.append(len(out))
            if stress_letter == i:
                stress_at = len(syllable_starts) - 1
            nxt = letters[i + 1] if i + 1 < len(letters) else ""
            after = letters[i + 2] if i + 2 < len(letters) else ""
            # e is open before a sonorant that closes the syllable. `nxt` must be
            # tested for truth first: "" is a substring of every string, so an
            # empty lookahead made every word-final e come out as [æ].
            if low == "e" and nxt and nxt in SONORANT and not is_vowel(after):
                out.append("æ")
            elif low in "âîû":
                out.append({"â": "ɑ", "î": "i", "û": "u"}[low] + "ː")
            else:
                out.append(VOW[low])
            if i in long_at and not out[-1].endswith("ː"):
                out.append("ː")
        elif low in ("k", "g", "l"):
            # Which vowel colours the consonant depends on where it sits in the
            # syllable: an onset takes the vowel it leads into, a coda the one it
            # closes. Scanning ahead for *any* vowel confuses the two — it made
            # herhalde's coda l clear (hal|de, dark after back a) and akrep's
            # coda k palatal (ak|rep, plain after back a).
            adjacent = letters[i + 1] if i + 1 < len(letters) else ""
            if is_vowel(adjacent):
                ref = adjacent                                     # onset
            else:
                ref = next((c for c in reversed(letters[:i])
                            if is_vowel(c)), "")                   # coda
            front = bool(ref) and ref in FRONT
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

    if not syllable_starts:
        return None
    # IPA marks the syllable, not the vowel: walk left past a single onset.
    idx = stress_at if stress_at is not None else len(syllable_starts) - 1
    onset = syllable_starts[idx]
    floor = syllable_starts[idx - 1] + 1 if idx > 0 else 0
    if onset > floor and out[onset - 1] != "ː":
        onset -= 1
    out.insert(onset, "ˈ")
    return "".join(out)


def load_cache() -> tuple[dict[str, str], set[str]]:
    """word -> first sense's telaffuz, plus the words whose senses disagree."""
    first: dict[str, str] = {}
    disputed: set[str] = set()
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["status"] != "found" or not rec["response"]:
            continue
        tels = [e["telaffuz"] for e in rec["response"] if e.get("telaffuz")]
        if len(set(tels)) > 1:
            disputed.add(rec["word"])
            continue
        head = rec["response"][0].get("telaffuz")
        if head:
            first[rec["word"]] = head
        elif tels:
            # Only a later sense carries it, so it may belong to a different
            # word altogether. Left alone rather than guessed at.
            disputed.add(rec["word"])
    return first, disputed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--conflicts", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not CACHE.exists():
        print("no TDK cache — run scripts/fetch_tdk.py first", file=sys.stderr)
        return 1
    telaffuz, disputed = load_cache()

    new: list[tuple[str, str, str]] = []       # word, TDK, IPA
    conflicts: list[tuple[str, str, str]] = []  # word, deck, TDK-derived
    skipped: list[tuple[str, str]] = []
    held: list[str] = []
    changed: dict[Path, dict] = {}

    for path in sorted(CANDIDATES.glob("*.candidates.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for item in data["items"]:
            word = item["turkish"].strip()
            if " " in word or "/" in word:
                continue
            if word in disputed:
                held.append(word)
                continue
            tel = telaffuz.get(word)
            if not tel:
                continue
            ipa = convert(word, tel)
            if not ipa:
                skipped.append((word, tel))
                continue
            if item.get("pron_tr"):
                if item["pron_tr"] != ipa:
                    conflicts.append((word, item["pron_tr"], ipa))
                continue
            new.append((word, tel, ipa))
            item["pron_tr"] = ipa
            # TDK lists a pronunciation only where the spelling does not give it
            # away, which is exactly what the tag is for.
            if "pronunciation" not in item["tags"]:
                item["tags"] = item["tags"] + ["pronunciation"]
            item["notes"] = (item.get("notes", "").rstrip() + " " + NOTE).strip()
            touched = True
        if touched:
            changed[path] = data

    if args.sample:
        print(f"{'word':18s} {'TDK':26s} IPA")
        for word, tel, ipa in sorted(new)[: args.sample]:
            print(f"  {word:18s} {tel:26s} {ipa}")
    if args.conflicts and conflicts:
        print(f"\ndeck already has a different transcription ({len(conflicts)}) "
              f"— hand-written, so left alone:")
        for word, mine, theirs in sorted(conflicts):
            print(f"  {word:18s} deck {mine:24s} TDK-derived {theirs}")

    print(f"\n{len(new)} new transcriptions, {len(conflicts)} conflicts left alone, "
          f"{len(skipped)} skipped (ğ or an inflected form), "
          f"{len(set(held))} held back as ambiguous: {', '.join(sorted(set(held)))}")
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
