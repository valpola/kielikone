#!/usr/bin/env python3

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "candidates"


def extract_text_from_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "PDF extraction requires pypdf. Install with: pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def extract_text_from_image(path: Path) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Image extraction requires pytesseract and pillow. "
            "Install with: pip install pytesseract pillow"
        ) from exc

    return pytesseract.image_to_string(Image.open(path), lang="tur+eng")


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return extract_text_from_image(path)
    return path.read_text(encoding="utf-8", errors="replace")


def parse_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    lines = [line.strip() for line in text.splitlines()]

    def normalize_line(value: str) -> str:
        return (
            value.replace("\ufb01", "fi")
            .replace("\ufb02", "fl")
            .replace("\ufb00", "ff")
            .replace("\ufb03", "ffi")
            .replace("\ufb04", "ffl")
        )

    def normalize_header(value: str) -> str:
        mapping = str.maketrans({
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
        })
        lowered = value.translate(mapping).lower()
        return re.sub(r"[^a-z]", "", lowered)

    def is_header_line(value: str) -> bool:
        compact = normalize_header(value)
        if compact in {"kelimelistesi", "kelimeanlami", "kelimeanlam"}:
            return True
        if "alphabet" in compact or "alfabe" in compact:
            return True
        if compact in {"isim", "fiil"}:
            return True
        if re.match(r"^a\d+-\d+[a-z]?\b", compact):
            return True
        return False

    def split_blocks() -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []

        def flush() -> None:
            if current:
                blocks.append(current[:])
                current.clear()

        for idx, raw in enumerate(lines):
            line = normalize_line(raw)
            if not line:
                continue

            value = re.sub(r"\s+", " ", line).strip(" .;,")
            if not value:
                continue

            if value.lower().startswith("www."):
                flush()
                continue

            if is_header_line(value):
                flush()
                continue

            if value.startswith("(") and value.endswith(")"):
                flush()
                continue

            # Section headers followed by parenthetical translation.
            if idx + 1 < len(lines):
                next_line = normalize_line(lines[idx + 1]).strip()
                if next_line.startswith("(") and next_line.endswith(")"):
                    flush()
                    continue

            current.append(value)

        flush()
        return blocks

    separators = [" - ", " – ", " — ", ":", "\t", " = "]
    for line in lines:
        line = normalize_line(line)
        if not line or len(line) > 140:
            continue
        if re.search(r"\d{2,}", line):
            continue
        if is_header_line(line):
            continue

        for sep in separators:
            if sep in line:
                left, right = [part.strip(" .;,") for part in line.split(sep, 1)]
                if not left or not right:
                    continue
                if len(left.split()) > 6 or len(right.split()) > 8:
                    continue
                pairs.append((left, right))
                break

    deduped: list[tuple[str, str]] = []
    seen = set()
    for left, right in pairs:
        key = (left.lower(), right.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append((left, right))

    if deduped:
        return deduped

    turkish_candidates: list[str] = []
    english_candidates: list[str] = []
    english_mode = False

    for line in lines:
        if not line:
            continue

        cleaned = normalize_line(line)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;,")
        if not cleaned:
            continue
        if is_header_line(cleaned):
            continue

        if cleaned.lower().startswith("www."):
            continue
        if cleaned.lower() in {"kelime listesi", "kelime anlamı", "alfabe", "alphabet"}:
            continue

        if re.match(r"^[A-ZÇĞİIÖŞÜ]\s+", cleaned):
            value = re.sub(r"^[A-ZÇĞİIÖŞÜ]\s+", "", cleaned).strip()
            if value:
                turkish_candidates.append(value)
            continue

        ascii_line = bool(re.match(r"^[A-Za-z ,'-]+$", cleaned))
        has_turkish_chars = bool(re.search(r"[çğıöşüÇĞİÖŞÜ]", cleaned))

        if ascii_line and not has_turkish_chars:
            english_mode = True
            english_candidates.append(cleaned)
            continue

        if not english_mode and len(cleaned.split()) <= 4:
            turkish_candidates.append(cleaned)

    blocks = split_blocks()
    for block in blocks:
        if len(block) >= 4 and len(block) % 2 == 0:
            half = len(block) // 2
            left = block[:half]
            right = block[half:]
            pairs.extend(zip(left, right))

    if pairs:
        return pairs

    if turkish_candidates and english_candidates:
        size = min(len(turkish_candidates), len(english_candidates))
        return list(zip(turkish_candidates[:size], english_candidates[:size]))

    if deduped:
        return deduped

    return []


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_candidates(path: Path, pairs: list[tuple[str, str]]) -> dict:
    items = []
    base = slug(path.stem) or "source"

    for idx, (turkish, english) in enumerate(pairs, start=1):
        items.append(
            {
                "id": f"cand-{base}-{idx:04d}",
                "turkish": turkish,
                "english": english,
                "priority": 3,
                "tags": [],
                "source": path.name,
                "notes": "",
                "status": "needs_review",
            }
        )

    return {
        "source_file": path.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }


def process_file(path: Path, output_dir: Path) -> Path:
    text = read_text(path)
    pairs = parse_pairs(text)
    payload = build_candidates(path, pairs)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{path.stem}.candidates.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract vocab candidates from source files")
    parser.add_argument("inputs", nargs="+", help="PDF/image/text files to parse")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Where to write candidate JSON files",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    ok = 0

    for raw in args.inputs:
        path = Path(raw)
        if not path.exists():
            print(f"SKIP: {path} does not exist")
            continue
        try:
            out_path = process_file(path, output_dir)
            print(f"Wrote candidates: {out_path}")
            ok += 1
        except Exception as exc:
            print(f"FAILED: {path} -> {exc}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
