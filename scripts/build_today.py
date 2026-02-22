#!/usr/bin/env python3

import argparse
import csv
import io
import json
import math
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
VOCAB_DIR = ROOT / "data" / "vocab"
TAGS_PATH = ROOT / "data" / "tags.json"


@dataclass(frozen=True)
class ScoreConfig:
    tau_wrong_days: float = 21.0
    tau_right_default_days: float = 7.0
    tau_right_by_freq: dict[str, float] = None
    weight_wrong: float = 2.0
    weight_right: float = 1.0

    def __post_init__(self) -> None:
        if self.tau_right_by_freq is None:
            object.__setattr__(
                self,
                "tau_right_by_freq",
                {
                    "freq-100": 3.0,
                    "freq-500": 5.0,
                    "freq-1000": 8.0,
                },
            )


DEFAULT_CONFIG = ScoreConfig()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build 'today' tag selection from Google Sheets results."
    )
    parser.add_argument(
        "--results",
        default=os.environ.get("RESULTS_SOURCE", "").strip(),
        help="CSV/JSON source path or URL (or RESULTS_SOURCE env).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("TODAY_LIMIT", "30")),
        help="Number of items to tag as today (default: 30).",
    )
    parser.add_argument(
        "--today-tag",
        default=os.environ.get("TODAY_TAG", "today"),
        help="Tag id to apply for today's list (default: today).",
    )
    parser.add_argument(
        "--include-tag",
        action="append",
        default=[],
        help="Only consider items with this tag (repeatable).",
    )
    parser.add_argument(
        "--exclude-tag",
        action="append",
        default=[],
        help="Exclude items with this tag (repeatable).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print top items but do not modify vocab files.",
    )
    return parser.parse_args()


def load_text(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    return Path(source).read_text(encoding="utf-8")


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    for fmt in (
        None,
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
    ):
        try:
            if fmt:
                parsed = datetime.strptime(raw, fmt)
            else:
                parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    return None


def parse_correct(value: str) -> bool | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return True
    if raw in {"false", "0", "no", "n"}:
        return False
    return None


def load_results(source: str) -> list[dict[str, Any]]:
    text = load_text(source)
    stripped = text.lstrip()
    if not stripped:
        return []

    if stripped[0] in "[{":
        payload = json.loads(text)
        if isinstance(payload, dict):
            if "rows" in payload and isinstance(payload["rows"], list):
                return payload["rows"]
            if "items" in payload and isinstance(payload["items"], list):
                return payload["items"]
            return []
        if isinstance(payload, list):
            return payload
        return []

    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]


def event_stream(rows: Iterable[dict[str, Any]]) -> list[tuple[datetime, str, str, bool]]:
    events: list[tuple[datetime, str, str, bool]] = []
    for row in rows:
        ts = parse_timestamp(row.get("timestamp", ""))
        word_id = str(row.get("word_id", "")).strip()
        mode = str(row.get("mode", "")).strip()
        correct = parse_correct(row.get("correct", ""))
        if not ts or not word_id or not mode or correct is None:
            continue
        events.append((ts, word_id, mode, correct))
    events.sort(key=lambda item: item[0])
    return events


def decay(score: float, last_time: datetime, current: datetime, tau_days: float) -> float:
    if score <= 0:
        return 0.0
    if tau_days <= 0:
        return 0.0
    delta_days = (current - last_time).total_seconds() / 86400.0
    if delta_days <= 0:
        return score
    return score * math.exp(-delta_days / tau_days)


def compute_scores(
    events: list[tuple[datetime, bool]],
    now: datetime,
    config: ScoreConfig,
    tau_right_days: float,
) -> tuple[float, float, float]:
    wrong_score = 0.0
    right_score = 0.0
    last_wrong: datetime | None = None
    last_right: datetime | None = None

    for timestamp, correct in events:
        if correct:
            if last_right:
                right_score = decay(right_score, last_right, timestamp, tau_right_days)
            right_score += 1.0
            last_right = timestamp
        else:
            if last_wrong:
                wrong_score = decay(wrong_score, last_wrong, timestamp, config.tau_wrong_days)
            wrong_score += 1.0
            last_wrong = timestamp

    if last_wrong:
        wrong_score = decay(wrong_score, last_wrong, now, config.tau_wrong_days)
    if last_right:
        right_score = decay(right_score, last_right, now, tau_right_days)

    score = config.weight_wrong * wrong_score - config.weight_right * right_score
    return wrong_score, right_score, score


def load_vocab_files() -> list[tuple[Path, dict[str, Any]]]:
    files: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(VOCAB_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            files.append((path, data))
    return files


def iter_items(files: list[tuple[Path, dict[str, Any]]]) -> Iterable[dict[str, Any]]:
    for _, data in files:
        items = data.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    yield item


def filter_items(
    items: Iterable[dict[str, Any]],
    include_tags: set[str],
    exclude_tags: set[str],
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        tags = set(item.get("tags", []) or [])
        if include_tags and not include_tags.issubset(tags):
            continue
        if exclude_tags and tags.intersection(exclude_tags):
            continue
        filtered.append(item)
    return filtered


def main() -> int:
    args = parse_args()
    if not args.results:
        print("ERROR: --results or RESULTS_SOURCE is required")
        return 2

    try:
        rows = load_results(args.results)
    except Exception as exc:
        print(f"ERROR: Failed to load results: {exc}")
        return 2

    events = event_stream(rows)
    events_by_key: dict[tuple[str, str], list[tuple[datetime, bool]]] = {}
    for timestamp, word_id, mode, correct in events:
        events_by_key.setdefault((word_id, mode), []).append((timestamp, correct))

    vocab_files = load_vocab_files()
    items = filter_items(
        list(iter_items(vocab_files)),
        set(args.include_tag or []),
        set(args.exclude_tag or []),
    )

    now = datetime.now(tz=UTC)
    scored: list[tuple[str, float]] = []

    for item in items:
        word_id = str(item.get("id", "")).strip()
        if not word_id:
            continue
        tags = set(item.get("tags", []) or [])
        tau_right_days = min(
            (DEFAULT_CONFIG.tau_right_by_freq[tag] for tag in tags if tag in DEFAULT_CONFIG.tau_right_by_freq),
            default=DEFAULT_CONFIG.tau_right_default_days,
        )

        scores = []
        for mode in ("tr-en", "en-tr"):
            key = (word_id, mode)
            wrong, right, score = compute_scores(
                events_by_key.get(key, []),
                now,
                DEFAULT_CONFIG,
                tau_right_days,
            )
            scores.append(score)
        final_score = max(scores) if scores else 0.0
        scored.append((word_id, final_score))

    scored.sort(key=lambda entry: (-entry[1], entry[0]))
    top_items = scored[: max(0, args.limit)]
    today_ids = {word_id for word_id, _ in top_items}

    print(f"Loaded {len(rows)} results rows")
    print(f"Scored {len(scored)} items, selecting {len(today_ids)} for tag '{args.today_tag}'")

    if args.dry_run:
        for word_id, score in top_items[: min(20, len(top_items))]:
            print(f"{word_id}: {score:.3f}")
        return 0

    changed = 0
    for path, data in vocab_files:
        updated_items = []
        for item in data.get("items", []) or []:
            if not isinstance(item, dict):
                updated_items.append(item)
                continue
            tags = [tag for tag in (item.get("tags", []) or []) if tag != args.today_tag]
            if str(item.get("id", "")) in today_ids:
                tags.append(args.today_tag)
            item["tags"] = tags
            updated_items.append(item)
        data["items"] = updated_items
        path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
        changed += 1

    print(f"Updated {changed} vocab files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
