#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_DIR = ROOT / "data" / "candidates"
OUT_PATH = ROOT / "data" / "vocab" / "reviewed.json"


def load_candidates() -> list[dict]:
    items: list[dict] = []
    for path in sorted(CANDIDATES_DIR.glob("*.candidates.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            if item.get("status") != "approved":
                continue
            entry = dict(item)
            entry.pop("today_score", None)
            entry.pop("today_score_debug", None)
            tags = entry.get("tags") or []
            if tags:
                entry["tags"] = [tag for tag in tags if tag != "today"]
            items.append(entry)
    items.sort(key=lambda item: str(item.get("id", "")))
    return items


def main() -> int:
    items = load_candidates()
    payload = {"source": "reviewed", "items": items}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Rebuilt {OUT_PATH} with {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
