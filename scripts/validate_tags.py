#!/usr/bin/env python3

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TAGS_PATH = ROOT / "data" / "tags.json"
VOCAB_DIR = ROOT / "data" / "vocab"


def main() -> int:
    tags_raw = json.loads(TAGS_PATH.read_text(encoding="utf-8"))
    known = {tag.get("id") for tag in tags_raw.get("tags", [])}

    errors: list[str] = []
    for path in sorted(VOCAB_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("items", []) if isinstance(raw, dict) else raw

        for item in items:
            item_id = item.get("id", "")
            for tag_id in item.get("tags", []) or []:
                if tag_id not in known:
                    errors.append(f"{path.name} -> {item_id}: unknown tag '{tag_id}'")

    if errors:
        print("Tag validation failed:")
        for line in errors:
            print(line)
        return 1

    print("Tag validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
