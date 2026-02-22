#!/usr/bin/env python3

import json
from pathlib import Path
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_DIR = ROOT / "data" / "candidates"
PDF_DIR = ROOT / "resources" / "originals"

UNIT_TAGS = {
    "A1_-_1A": "unit-a1-1a",
    "A1_-_1B": "unit-a1-1b",
    "A1_-_2A": "unit-a1-2a",
    "A1_-_2B": "unit-a1-2b",
    "A1_-_2C": "unit-a1-2c",
    "A1_-_3A": "unit-a1-3a",
}

SECTION_TAGS = {
    "isim": "noun",
    "fiil": "verb",
    "sifat": "adjective",
    "zarf": "adverb",
}

HEADER_KEYS = {"kelimelistesi", "kelimeanlami", "kelimeanlam"}
TRANSLATE = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "İ": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "Ç": "c",
        "Ğ": "g",
        "Ö": "o",
        "Ş": "s",
        "Ü": "u",
    }
)


def normalize(value: str) -> str:
    return value.replace("\ufb01", "fi").replace("\ufb02", "fl")


def compact(value: str) -> str:
    return "".join(ch for ch in value.translate(TRANSLATE).lower() if ch.isalpha())


def parse_sections(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    sections: list[tuple[str, list[str]]] = []
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if current and buffer:
            sections.append((current, buffer))
        buffer = []

    for raw in lines:
        value = normalize(raw)
        if not value:
            continue
        if value.lower().startswith("www."):
            continue
        if value.startswith("(") and value.endswith(")"):
            continue

        key = compact(value)
        if key in HEADER_KEYS or (key.startswith("a1") and "kelime" in key):
            continue
        if key in SECTION_TAGS:
            flush()
            current = key
            continue

        buffer.append(value)

    flush()

    pos_tags: list[str] = []
    for section, items in sections:
        if len(items) < 2 or len(items) % 2 != 0:
            continue
        half = len(items) // 2
        pos_tags.extend([SECTION_TAGS[section]] * half)

    return pos_tags


def apply_tags(candidate_path: Path, unit_tag: str, pos_tags: list[str] | None = None) -> None:
    raw = json.loads(candidate_path.read_text(encoding="utf-8"))
    items = raw.get("items", [])

    for idx, item in enumerate(items):
        tags = set(item.get("tags") or [])
        tags.add(unit_tag)
        if pos_tags and idx < len(pos_tags):
            tags.add(pos_tags[idx])
        item["tags"] = sorted(tags)
        item["status"] = "approved"

    raw["items"] = items
    candidate_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    for stem, unit_tag in UNIT_TAGS.items():
        candidate_path = CANDIDATES_DIR / f"{stem}.candidates.json"
        if not candidate_path.exists():
            print(f"Missing candidates: {candidate_path}")
            continue

        pos_tags = None
        if stem != "A1_-_1A":
            pdf_path = PDF_DIR / f"{stem}.pdf"
            if pdf_path.exists():
                pos_tags = parse_sections(pdf_path)

        apply_tags(candidate_path, unit_tag, pos_tags)
        print(f"Tagged: {candidate_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
