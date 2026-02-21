#!/usr/bin/env python3

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEXICON_PATH = ROOT / "data" / "lexicon.json"
OUT_PATH = ROOT / "web" / "data" / "quiz.json"


def main() -> None:
    data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    items = data.get("items", [])

    # Keep only fields the web app needs.
    quiz_items = [
        {
            "id": item.get("id", ""),
            "turkish": item.get("turkish", ""),
            "english": item.get("english", ""),
            "priority": int(item.get("priority", 1)),
        }
        for item in items
        if item.get("turkish") and item.get("english")
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"items": quiz_items}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(quiz_items)} items to {OUT_PATH}")


if __name__ == "__main__":
    main()
