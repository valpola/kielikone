#!/usr/bin/env python3
"""Turn cached the prior app lesson payloads into vocabulary and a readable course book.

Input is `resources/prior_app_cache/lessons_raw/sess_*.json`, written by opening a
lesson in a logged-in browser and reading IndexedDB (`learner-activity` →
`sessions`). Opening a lesson caches it; nothing has to be answered. See the
cache README for how the capture works.

A lesson is a list of trainers. Two carry content worth keeping:

  vocabulary / dictate / matching  — drill trainers; their `phrase` items are the
                                     word pairs, and they repeat across trainers
  card                             — the explanation screens. These are the part
                                     that never becomes a review card, and the
                                     reason for this script.

Item text uses three bits of markup:

  **bold**          emphasis, kept as-is (it is already Markdown)
  ((answer))        the bit the learner supplies — unwrapped
  ((wrong|*right))  multiple choice, `*` marks the correct option — resolved

Usage:
  python3 scripts/parse_prior_app_lessons.py            # write both outputs
  python3 scripts/parse_prior_app_lessons.py --coverage # also check review cards
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "resources" / "prior_app_cache" / "lessons_raw"
CACHE = ROOT / "resources" / "prior_app_cache"


def resolve(text):
    """Expand the app's ((…)) markup into plain prose."""
    if not text:
        return ""

    def one(m):
        body = m.group(1)
        if "|" in body:
            opts = body.split("|")
            for o in opts:
                if o.startswith("*"):
                    return o[1:]
            return opts[-1]
        return body.lstrip("*")

    return re.sub(r"\(\(([^()]*)\)\)", one, text).strip()


def plain(text):
    """resolve(), minus the bold markers — for matching against the deck."""
    # `_` joins a suffix to its stem in the drill trainers ("Büyük_mü?")
    return resolve(text).replace("**", "").replace("_", " ").strip()


def split_drill(tr, en):
    """A pronunciation drill packs several words per item: "sabun - masa - kas".

    Split only when both sides agree on the count, so a real phrase containing a
    dash is left alone.
    """
    if " - " not in tr:
        return [(tr, en)]
    left, right = tr.split(" - "), en.split(" - ")
    if len(left) != len(right) or len(left) < 2:
        return [(tr, en)]
    return [(a.strip(), b.strip()) for a, b in zip(left, right)]


def is_sentence(tr):
    """Dialogue lines are not vocabulary; they are practice material."""
    return len(tr.split()) > 3 or tr.count(".") > 1


def fold(s):
    """Letters only, Turkish-aware, for comparing forms."""
    s = unicodedata.normalize("NFKC", s or "").replace("İ", "i").lower()
    s = s.replace("̇", "")
    for a, b in (("â", "a"), ("î", "i"), ("û", "u"), ("ı", "i")):
        s = s.replace(a, b)
    return re.sub(r"[^0-9a-zçğöşü]+", "", s)


def load():
    """Lessons in curriculum order.

    The files are named by lesson id, so sorting by filename gives hash order —
    useless for a course book, where unit 1 must come before unit 2.
    """
    order = {}
    cat = CACHE / "lessons.json"
    if cat.exists():
        for i, l in enumerate(json.loads(cat.read_text(encoding="utf-8"))):
            order.setdefault(l["lessonId"], i)

    lessons = []
    for p in RAW.glob("sess_*.json"):
        blob = json.loads(p.read_text(encoding="utf-8"))
        meta = blob["lesson"]
        trainers = [t for s in blob["sessions"] for t in s["sessionData"]["trainers"]]
        lessons.append((meta, trainers))
    lessons.sort(key=lambda x: order.get(x[0]["lessonId"], 10**6))
    return lessons


def items_of(trainer):
    for g in trainer.get("item_groups") or []:
        for it in g.get("items") or []:
            yield it


def vocabulary(lessons):
    """Word pairs, deduplicated per lesson, in first-seen order."""
    out = []
    for meta, trainers in lessons:
        seen, rows = set(), []
        for t in trainers:
            for it in items_of(t):
                tr0, en0 = plain(it.get("learn_language_text")), plain(it.get("display_language_text"))
                if it.get("type") != "phrase" or not tr0 or not en0:
                    continue
                for tr, en in split_drill(tr0, en0):
                    if not tr or fold(tr) in seen:
                        continue
                    seen.add(fold(tr))
                    rows.append({
                        "tr": tr, "en": en,
                        "kind": "sentence" if is_sentence(tr) else "word",
                        # a split drill item loses its (single, joined) recording
                        "sound": (it.get("sound") or {}).get("id") if tr == tr0 else None,
                        "note": plain(it.get("info_text")) or None,
                    })
        out.append({**meta, "words": rows})
    return out


def emphasise(text):
    """Bold the example, unless it already carries its own emphasis.

    The drill lines highlight the letter under study ("**s**abun"), and wrapping
    those again yields "****s**abun**", which renders as literal asterisks.
    """
    return text if "**" in text else f"**{text}**"


def coursebook(lessons):
    """The explanation screens, as Markdown."""
    md = ["# Prior app — Turkish — the explanations\n",
          "\nScraped from the lesson payloads: the `card` trainers, which teach the "
          "grammar and never become review cards.\n"]
    kept = 0
    for meta, trainers in lessons:
        cards = [t for t in trainers if t.get("type") == "card"]
        all_notes = [plain(it["info_text"]) for t in trainers
                     for it in items_of(t) if it.get("info_text")]
        if not cards and not all_notes:
            continue
        kept += 1
        sub = meta.get("subtitle") or ""
        head = f"{meta['unit']} — {sub}" if sub.strip() else meta["unit"]
        md.append(f"\n## {meta['title']}\n\n*{head}*\n")

        shown = set()
        for c in cards:
            md.append(f"\n### {resolve(c.get('title'))}\n")
            for it in items_of(c):
                tr = resolve(it.get("learn_language_text"))
                en = resolve(it.get("display_language_text"))
                if it.get("type") == "task" or not tr:
                    if en:
                        md.append(f"\n{en}\n")
                elif en:
                    md.append(f"\n- {emphasise(tr)} — {en}")
                else:
                    md.append(f"\n- {emphasise(tr)}")
                if it.get("info_text"):
                    n = plain(it["info_text"])
                    if n not in shown:
                        shown.add(n)
                        md.append(f"\n\n  > {n}\n")
            md.append("\n")

        # whatever was attached to drill items rather than to an explanation card
        loose = [n for n in dict.fromkeys(all_notes) if n not in shown]
        if loose:
            md.append("\n### Notes\n")
            md.extend(f"\n> {n}\n" for n in loose)
    return "".join(md), kept


def coverage(vocab):
    cards = json.loads((CACHE / "vocabulary.json").read_text(encoding="utf-8"))
    known = {fold(c["tr"]) for c in cards}
    print(f"\nReview cards on file: {len(cards)}\n")
    tot = {"word": 0, "sentence": 0}
    gap = {"word": 0, "sentence": 0}
    uncarded = []
    for les in vocab:
        for w in les["words"]:
            tot[w["kind"]] += 1
            if fold(w["tr"]) not in known:
                gap[w["kind"]] += 1
                if w["kind"] == "word":
                    uncarded.append((les["title"], w))
        n_w = sum(1 for w in les["words"] if w["kind"] == "word")
        n_g = sum(1 for w in les["words"]
                  if w["kind"] == "word" and fold(w["tr"]) not in known)
        print(f"  {les['title'][:34]:36s} {n_w:3d} words   "
              f"{f'{n_g} with no card' if n_g else 'all covered'}")

    print(f"\n  Single words / short phrases : {tot['word']:3d}, "
          f"{gap['word']} with no review card ({gap['word']/max(tot['word'],1)*100:.0f}%)")
    print(f"  Dialogue sentences           : {tot['sentence']:3d}, "
          f"{gap['sentence']} with no review card "
          f"({gap['sentence']/max(tot['sentence'],1)*100:.0f}%)")

    print("\n  Vocabulary taught but never carded:")
    for title, w in uncarded:
        note = f"   [{title}]"
        print(f"    {w['tr']:26s} {w['en'][:44]:46s}{note}")


def main():
    lessons = load()
    if not lessons:
        print(f"no payloads in {RAW.relative_to(ROOT)}", file=sys.stderr)
        return 1
    vocab = vocabulary(lessons)
    (CACHE / "lesson_vocabulary.json").write_text(
        json.dumps(vocab, ensure_ascii=False, indent=1), encoding="utf-8")
    book, kept = coursebook(lessons)
    (CACHE / "coursebook.md").write_text(book, encoding="utf-8")
    print(f"{len(lessons)} lessons -> lesson_vocabulary.json "
          f"({sum(len(l['words']) for l in vocab)} words), "
          f"coursebook.md ({kept} lessons had explanations)")
    if "--coverage" in sys.argv:
        coverage(vocab)
    return 0


if __name__ == "__main__":
    sys.exit(main())
