#!/usr/bin/env python3
"""Cache the Turkishle web course locally, then parse it.

The embeds are public by URL, so only the *lesson map* needs a logged-in session:
collect that in the browser (see CLAUDE.md) and save it as
resources/turkishle_cache/lessons.json in the shape

    [{"unit": "A2-2C", "title": "📝 Kelime Listesi", "url": "...", "widgets": ["123", ...]}]

Everything else runs from here, and every fetch is written to disk before being
parsed, so the material is only ever downloaded once.

    python3 scripts/fetch_turkishle.py            # fetch what is missing, then parse
    python3 scripts/fetch_turkishle.py --parse    # re-parse the cache, fetch nothing
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "resources" / "turkishle_cache"
EMBEDS = CACHE / "embeds"
LESSONS = CACHE / "lessons.json"
EMBED_URL = "https://turkishle.h5p.com/content/{}/embed"


def fetch_embed(widget_id: str) -> str | None:
    """Return the raw embed page, from disk if we already have it."""
    path = EMBEDS / f"{widget_id}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    request = urllib.request.Request(
        EMBED_URL.format(widget_id),
        headers={"User-Agent": "Mozilla/5.0 (kielikone vocabulary sweep)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        print(f"  !! {widget_id}: {error}")
        return None
    EMBEDS.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    time.sleep(0.4)  # the course is one person's livelihood; do not hammer it
    return body


def h5p_content(page: str):
    """Pull the widget's jsonContent out of an embed page."""
    marker = "H5PIntegration = "
    at = page.find(marker)
    if at == -1:
        return None
    try:
        integration, _ = json.JSONDecoder().raw_decode(page[at + len(marker):])
    except ValueError:
        return None
    contents = integration.get("contents") or {}
    if not contents:
        return None
    first = next(iter(contents.values()))
    raw = first.get("jsonContent")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def walk(node, found):
    """Collect Dialogcards dialogs and prose, wherever they sit.

    jsonContent for a Dialogcards widget *is* the dialogcards object — the library
    name lives in H5PIntegration.contents[key], not in the content — so match on
    shape ("dialogs" holding text/answer pairs) rather than on a library field.
    Keying on the library found nothing at all.
    """
    if isinstance(node, dict):
        dialogs = node.get("dialogs")
        if isinstance(dialogs, list) and any(
            isinstance(d, dict) and "answer" in d for d in dialogs
        ):
            for dialog in dialogs:
                if isinstance(dialog, dict):
                    found["cards"].append(
                        {"front": dialog.get("text", ""), "back": dialog.get("answer", "")}
                    )
        text = node.get("text")
        if isinstance(text, str) and len(text) > 40:
            found["prose"].append(text)
        for value in node.values():
            walk(value, found)
    elif isinstance(node, list):
        for value in node:
            walk(value, found)


TAGS = re.compile(r"<[^>]+>")
STRONG = re.compile(r"<strong>(.*?)</strong>", re.S | re.I)
EM = re.compile(r"<em>(.*?)</em>", re.S | re.I)
NBSP = "\u00a0"


def clean(html: str) -> str:
    text = TAGS.sub(" ", html or "").replace(NBSP, " ").replace("&nbsp;", " ")
    for entity, char in (
        ("&amp;", "&"), ("&quot;", '"'), ("&#039;", "'"),
        ("&lt;", "<"), ("&gt;", ">"), ("&rsquo;", "\u2019"), ("&hellip;", "\u2026"),
    ):
        text = text.replace(entity, char)
    return " ".join(text.split())


def parse_side(html: str):
    """A card side is <strong>headword</strong> then one <em> per example line.

    Returns (headword, [lines]). Falling back to the whole text keeps cards that
    do not follow the pattern rather than dropping them silently.
    """
    head = " / ".join(clean(m) for m in STRONG.findall(html or "") if clean(m))
    lines = [clean(m) for m in EM.findall(html or "") if clean(m)]
    if not head and not lines:
        whole = clean(html)
        return whole, []
    if not head:
        head, lines = lines[0], lines[1:]
    return head, lines

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parse", action="store_true", help="re-parse the cache only")
    args = parser.parse_args()

    if not LESSONS.exists():
        print(f"No lesson map at {LESSONS.relative_to(ROOT)}.")
        print("Collect it from a logged-in browser first — see CLAUDE.md.")
        return 1

    lessons = json.loads(LESSONS.read_text(encoding="utf-8"))
    cards, prose, missing = [], [], 0
    for lesson in lessons:
        for widget_id in lesson.get("widgets") or []:
            path = EMBEDS / f"{widget_id}.html"
            page = path.read_text(encoding="utf-8") if path.exists() else (
                None if args.parse else fetch_embed(widget_id)
            )
            if page is None:
                missing += 1
                continue
            content = h5p_content(page)
            if content is None:
                continue
            found = {"cards": [], "prose": []}
            walk(content, found)
            for card in found["cards"]:
                turkish, tr_lines = parse_side(card["front"])
                english, en_lines = parse_side(card["back"])
                # The two sides run in parallel, one <em> per line; zip only as far
                # as they agree so a mismatched card yields fewer pairs, not wrong ones.
                pairs = [
                    {"tr": tr, "en": en} for tr, en in zip(tr_lines, en_lines)
                ]
                cards.append(
                    {
                        "unit": lesson.get("unit", ""),
                        "lesson": lesson.get("title", ""),
                        "widget": widget_id,
                        "headword": turkish,
                        "meaning": english,
                        "sentences": pairs,
                        "unpaired": max(len(tr_lines), len(en_lines)) - len(pairs),
                    }
                )
            for text in found["prose"]:
                prose.append(
                    {
                        "unit": lesson.get("unit", ""),
                        "lesson": lesson.get("title", ""),
                        "widget": widget_id,
                        "text": clean(text),
                    }
                )

    (CACHE / "cards.json").write_text(
        json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (CACHE / "prose.json").write_text(
        json.dumps(prose, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sentences = sum(len(card["sentences"]) for card in cards)
    unpaired = sum(card["unpaired"] for card in cards)
    print(f"lessons {len(lessons)} · widgets cached {len(list(EMBEDS.glob('*.html')))}")
    print(f"cards {len(cards)} · sentence pairs {sentences} · prose blocks {len(prose)}")
    if unpaired:
        print(f"{unpaired} card line(s) had no counterpart and were left out")
    if missing:
        print(f"{missing} widget(s) could not be fetched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
