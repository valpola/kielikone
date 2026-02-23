#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOCAB = ROOT / "data" / "vocab" / "reviewed.json"
DEFAULT_ALIASES = ROOT / "data" / "aliases.json"


def load_vocab(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw, list(raw.get("items", []))
    if isinstance(raw, list):
        return {"source": path.stem, "items": raw}, list(raw)
    return {"source": path.stem, "items": []}, []


def load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    aliases = raw.get("aliases", {}) or {}
    cleaned: dict[str, str] = {}
    for alias_id, canonical_id in aliases.items():
        alias = str(alias_id).strip()
        canonical = str(canonical_id).strip()
        if alias and canonical:
            cleaned[alias] = canonical
    return cleaned


def save_aliases(path: Path, aliases: dict[str, str]) -> None:
    payload = {"version": 1, "aliases": aliases}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def normalize(text: str) -> str:
    squashed = re.sub(r"\s+", " ", text.strip().lower())
    return squashed


def find_duplicates(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        tr = normalize(str(item.get("turkish", "")))
        en = normalize(str(item.get("english", "")))
        if not tr or not en:
            continue
        groups.setdefault((tr, en), []).append(item)
    return [group for group in groups.values() if len(group) > 1]


def canonicalize(item_id: str, aliases: dict[str, str]) -> str:
    current = item_id
    seen: set[str] = set()
    while current in aliases and current not in seen:
        seen.add(current)
        current = aliases[current]
    return current


def merge_tags(primary: list[str], incoming: list[str]) -> list[str]:
    seen = set(primary)
    merged = list(primary)
    for tag in incoming:
        if tag not in seen:
            merged.append(tag)
            seen.add(tag)
    return merged


def apply_aliases(items: list[dict[str, Any]], aliases: dict[str, str]) -> int:
    by_id = {str(item.get("id", "")): item for item in items}
    removed = set()
    merged = 0

    for alias_id, canonical_id in aliases.items():
        alias_key = str(alias_id).strip()
        canonical_key = canonicalize(str(canonical_id).strip(), aliases)
        if not alias_key or not canonical_key or alias_key == canonical_key:
            continue

        alias_item = by_id.get(alias_key)
        canonical_item = by_id.get(canonical_key)
        if not alias_item or not canonical_item:
            continue

        canonical_item["tags"] = merge_tags(
            canonical_item.get("tags", []) or [],
            alias_item.get("tags", []) or [],
        )
        if not canonical_item.get("notes") and alias_item.get("notes"):
            canonical_item["notes"] = alias_item.get("notes")
        if not canonical_item.get("source") and alias_item.get("source"):
            canonical_item["source"] = alias_item.get("source")

        removed.add(alias_key)
        merged += 1

    if not removed:
        return 0

    items[:] = [item for item in items if str(item.get("id", "")) not in removed]
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deduplicate vocab items and manage aliases.")
    parser.add_argument("--vocab", default=str(DEFAULT_VOCAB), help="Path to vocab JSON.")
    parser.add_argument(
        "--aliases",
        default=str(DEFAULT_ALIASES),
        help="Path to aliases JSON.",
    )
    parser.add_argument(
        "--add",
        nargs=2,
        action="append",
        metavar=("ALIAS_ID", "CANONICAL_ID"),
        help="Add an alias mapping.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply aliases by merging and removing duplicate items.",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan for duplicate Turkish/English pairs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vocab_path = Path(args.vocab)
    aliases_path = Path(args.aliases)

    if not vocab_path.exists():
        print(f"Vocab file not found: {vocab_path}")
        return 1

    raw, items = load_vocab(vocab_path)
    aliases = load_aliases(aliases_path)

    if args.add:
        for alias_id, canonical_id in args.add:
            aliases[str(alias_id).strip()] = str(canonical_id).strip()
        save_aliases(aliases_path, aliases)
        print(f"Saved aliases to {aliases_path}")

    did_apply = False
    if args.apply:
        merged = apply_aliases(items, aliases)
        raw["items"] = items
        vocab_path.write_text(json.dumps(raw, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"Merged {merged} alias pairs into {vocab_path}")
        did_apply = True

    if args.scan or (not args.apply and not args.add):
        dupes = find_duplicates(items)
        if not dupes:
            print("No duplicates found.")
            return 0

        print("Duplicate groups:")
        for group in dupes:
            label = f"{group[0].get('turkish', '')} / {group[0].get('english', '')}"
            print(f"- {label}")
            for item in group:
                item_id = item.get("id", "")
                source = item.get("source", "")
                tags = ", ".join(item.get("tags", []) or [])
                print(f"  - {item_id} | {source} | {tags}")
        if did_apply:
            print("Note: scan output reflects the updated items list.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
