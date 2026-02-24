#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "data" / "vocab" / "reviewed.json"


def load_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw.get("items", [])
    if isinstance(raw, list):
        return raw
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge reviewed candidate vocab items")
    parser.add_argument("candidate_file", help="Path to *.candidates.json")
    parser.add_argument(
        "--target",
        default=str(DEFAULT_TARGET),
        help="Target vocab JSON file (data/vocab/*.json)",
    )
    args = parser.parse_args()

    candidate_path = Path(args.candidate_file)
    if not candidate_path.exists():
        print(f"Candidate file not found: {candidate_path}")
        return 1

    target_path = Path(args.target)

    candidate_raw = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_items = candidate_raw.get("items", [])

    approved = [item for item in candidate_items if item.get("status") == "approved"]
    if not approved:
        print("No approved items to merge (status must be 'approved').")
        return 0

    target_items = load_items(target_path)
    existing_ids = {str(item.get("id", "")) for item in target_items}

    merged = 0
    for item in approved:
        item_id = str(item.get("id", ""))
        if not item_id or item_id in existing_ids:
            continue
        target_items.append(item)
        existing_ids.add(item_id)
        merged += 1

    payload = {"source": target_path.stem, "items": target_items}
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Merged {merged} items into {target_path}")
    print("Reminder: run scripts/dedupe_vocab.py --apply to remove duplicates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
