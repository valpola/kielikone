#!/usr/bin/env python3
"""Invariants the exported deck must satisfy.

These are the rules from CLAUDE.md, checked mechanically. Each one exists because
breaking it produced a real defect: a prompt with no determinable answer, a word
that could not be found by unit, a tip that gave the answer away.

Run against web/data/quiz.json, i.e. what the app actually loads:

    .venv/bin/python scripts/tests/test_deck_invariants.py
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUIZ = ROOT / "web" / "data" / "quiz.json"

SUBUNIT = re.compile(r"^unit-a[12]-\d[abc]$")
# Tags that stand in for a subunit: the alphabet unit and the cross-unit
# Cases & Verbs supplement, which has no subunit to assign.
SUBUNIT_EQUIVALENT = {"unit-a1-0a", "unit-a1-cases"}
SESSION_TAG = "practice"
TURKISH_ONLY = set("çğışöü")

failures: list[str] = []


def check(name: str, bad: list[str], hint: str = "") -> None:
    if not bad:
        print(f"  ok    {name}")
        return
    shown = "\n".join(f"          {line}" for line in bad[:12])
    more = f"\n          … and {len(bad) - 12} more" if len(bad) > 12 else ""
    failures.append(f"  FAIL  {name} ({len(bad)})\n{shown}{more}" + (f"\n        {hint}" if hint else ""))


def norm_gloss(text: str) -> str:
    return " ".join(re.sub(r"\([^)]*\)", "", text).lower().split())


def norm_hint(text: str) -> str:
    return " ".join((text or "").lower().split())


def main() -> int:
    data = json.loads(QUIZ.read_text(encoding="utf-8"))
    items = data["items"]
    registry = {tag["id"] for tag in data.get("tags", [])}
    print(f"Checking {len(items)} items from {QUIZ.relative_to(ROOT)}\n")

    # Every tag on an item must be declared, or the filter UI cannot show it.
    check(
        "every tag is in the registry",
        sorted({f"{it['id']}: {t}" for it in items for t in it.get("tags", []) if t not in registry}),
    )

    # The practice set is per-device; shipping one would override what the device computed.
    check(
        "no practice-set tag is shipped",
        [it["id"] for it in items if SESSION_TAG in it.get("tags", [])],
    )

    # Every word must be findable by where it came from.
    check(
        "every item has a unit-level marker",
        [
            f"{it['turkish']} ({it['id']}) tags={[t for t in it.get('tags', []) if t.startswith('unit')]}"
            for it in items
            if not any(SUBUNIT.match(t) or t in SUBUNIT_EQUIVALENT for t in it.get("tags", []))
        ],
        "give it a subunit, or the -extra marker plus the subunit whose list owns the topic",
    )

    # Two items showing the identical EN->TR prompt cannot both be answered.
    by_prompt: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for it in items:
        by_prompt[(norm_gloss(it["english"]), norm_hint(it.get("hint_en_tr")))].append(it)
    check(
        "no two items share an EN->TR prompt",
        [
            f'"{gloss}" -> ' + ", ".join(x["turkish"] for x in group)
            for (gloss, _hint), group in sorted(by_prompt.items())
            if len(group) > 1
        ],
        "give the marked sense a hint_en_tr; leave the default sense unmarked",
    )

    # Same Turkish, different meanings: TR->EN needs something to tell them apart.
    by_turkish: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_turkish[it["turkish"].lower()].append(it)
    check(
        "every homograph has a TR->EN hint",
        [
            f"{word}: " + ", ".join(f'{x["english"]}' for x in group if not x.get("hint_tr_en"))
            for word, group in sorted(by_turkish.items())
            if len(group) > 1 and any(not x.get("hint_tr_en") for x in group)
        ],
    )

    # An EN->TR tip containing Turkish letters is giving away the answer.
    check(
        "no hint_en_tr leaks Turkish",
        [
            f'{it["turkish"]} ({it["id"]}): {it["hint_en_tr"]}'
            for it in items
            if it.get("hint_en_tr") and (set(it["hint_en_tr"].lower()) & TURKISH_ONLY)
        ],
    )

    # A gloss is shown verbatim as the TR->EN answer to type, and the matcher strips
    # brackets but keeps what is inside them — so "in the middle (of)" silently
    # requires the "of". Symbols carried on both sides, like kilometre (km), are the
    # intended exception: the bracket is part of the term in either language.
    check(
        "no gloss carries a one-sided parenthetical",
        [
            f'{it["turkish"]} ({it["id"]}): {it["english"]}'
            for it in items
            if "(" in it["english"] and "(" not in it["turkish"]
        ],
        "move the qualifier into hint_tr_en / hint_en_tr, or make it part of the gloss",
    )

    # A gap-fill is my addition, not the course's, and must say so both ways: the
    # source field and the -extra marker have to agree. gelişmek carried a source
    # copied from its batch, claiming an attestation it did not have.
    #
    # Read from the candidate files, not the deck: export_quiz.py drops `source`,
    # so checking the exported items would call everything attested.
    sourced = []
    for path in sorted((ROOT / "data" / "candidates").glob("*.candidates.json")):
        sourced.extend(json.loads(path.read_text(encoding="utf-8"))["items"])
    check(
        "the -extra marker agrees with the source",
        [
            f'{it["turkish"]} ({it["id"]}): '
            + ("source says gap-fill, no -extra tag" if it.get("source", "").lower().startswith("gap-fill")
               else "carries -extra, but the source claims an attestation")
            for it in sourced
            if it.get("source", "").lower().startswith("gap-fill")
            != any(t.endswith("-extra") for t in it.get("tags", []))
        ],
        "a gap-fill needs the -extra marker; an attested word must not carry it",
    )

    # ids are the key the answer history hangs on.
    dupe_ids = [i for i, n in Counter(it["id"] for it in items).items() if n > 1]
    check("ids are unique", sorted(dupe_ids))

    check(
        "no item is missing a field",
        [
            f'{it.get("id", "?")}: missing {field}'
            for it in items
            for field in ("id", "turkish", "english")
            if not it.get(field)
        ],
    )

    print()
    if failures:
        print("\n".join(failures))
        print(f"\n{len(failures)} invariant(s) violated.")
        return 1
    print("All deck invariants hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
