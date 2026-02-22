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

    separators = [" - ", " – ", " — ", ":", "\t", " = "]
    for line in lines:
        if not line or len(line) > 140:
            continue
        if re.search(r"\d{2,}", line):
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
    return deduped


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
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
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
