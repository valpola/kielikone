#!/usr/bin/env python3

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEXICON_PATH = ROOT / "data" / "lexicon.json"
VOCAB_DIR = ROOT / "data" / "vocab"
TAGS_PATH = ROOT / "data" / "tags.json"
ALIASES_PATH = ROOT / "data" / "aliases.json"
OUT_PATH = ROOT / "web" / "data" / "quiz.json"
OUT_ALIASES_PATH = ROOT / "web" / "data" / "aliases.json"


def load_tags() -> list[dict[str, Any]]:
    if not TAGS_PATH.exists():
        return []
    raw = json.loads(TAGS_PATH.read_text(encoding="utf-8"))
    tags = raw.get("tags", [])
    return [
        {
            "id": str(tag.get("id", "")).strip(),
            "label": str(tag.get("label", "")).strip(),
            "group": str(tag.get("group", "")).strip(),
        }
        for tag in tags
        if str(tag.get("id", "")).strip()
    ]


def load_items() -> list[dict[str, Any]]:
    if VOCAB_DIR.exists():
        items: list[dict[str, Any]] = []
        for path in sorted(VOCAB_DIR.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                file_items = raw.get("items", [])
            elif isinstance(raw, list):
                file_items = raw
            else:
                file_items = []
            items.extend(file_items)
        if items:
            return items

    data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    return data.get("items", [])


def load_aliases() -> dict[str, str]:
    if not ALIASES_PATH.exists():
        return {}
    raw = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    aliases = raw.get("aliases", {})
    if not isinstance(aliases, dict):
        return {}
    return {
        str(alias).strip(): str(canonical).strip()
        for alias, canonical in aliases.items()
        if str(alias).strip() and str(canonical).strip()
    }


def validate_item_tags(items: list[dict[str, Any]], tags: list[dict[str, Any]]) -> None:
    known = {tag["id"] for tag in tags}
    if not known:
        return

    unknown: list[tuple[str, str]] = []
    for item in items:
        item_id = str(item.get("id", ""))
        for tag_id in item.get("tags", []) or []:
            if tag_id not in known:
                unknown.append((item_id, str(tag_id)))

    if unknown:
        lines = [f"{item_id}: {tag_id}" for item_id, tag_id in unknown]
        message = "Unknown tags found in vocabulary items:\n" + "\n".join(lines)
        raise ValueError(message)


def main() -> None:
    tags = load_tags()
    items = load_items()
    aliases = load_aliases()
    validate_item_tags(items, tags)

    # Keep only fields the web app needs.
    quiz_items = [
        {
            "id": item.get("id", ""),
            "turkish": item.get("turkish", ""),
            "english": item.get("english", ""),
            "priority": int(item.get("priority", 1)),
            "tags": item.get("tags", []),
        }
        for item in items
        if item.get("turkish") and item.get("english")
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"items": quiz_items, "tags": tags}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    OUT_ALIASES_PATH.write_text(
        json.dumps({"aliases": aliases}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(quiz_items)} items to {OUT_PATH}")
    print(f"Wrote {len(aliases)} aliases to {OUT_ALIASES_PATH}")


if __name__ == "__main__":
    main()
