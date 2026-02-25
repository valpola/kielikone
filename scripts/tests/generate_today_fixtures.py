#!/usr/bin/env python3

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_today import (
    DEFAULT_CONFIG,
    canonicalize,
    compute_scores,
    event_stream,
    load_results,
)
FIXTURE_DIR = ROOT / "scripts" / "tests" / "fixtures"
RESULTS_PATH = FIXTURE_DIR / "results.csv"
QUIZ_PATH = FIXTURE_DIR / "quiz.json"
ALIASES_PATH = FIXTURE_DIR / "aliases.json"
EXPECTED_PATH = FIXTURE_DIR / "expected.json"

NOW = datetime(2026, 2, 25, 0, 0, 0, tzinfo=UTC)
MODE = "en-tr"
LIMIT = 2
TOLERANCE = 1e-4


def main() -> None:
    rows = load_results(str(RESULTS_PATH))
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8")).get("aliases", {})
    events = event_stream(rows, aliases)
    events_by_key: dict[tuple[str, str], list[tuple[datetime, bool]]] = {}
    for timestamp, word_id, mode, correct in events:
        events_by_key.setdefault((word_id, mode), []).append((timestamp, correct))

    quiz = json.loads(QUIZ_PATH.read_text(encoding="utf-8"))
    items = quiz.get("items", [])

    scored: list[tuple[str, float]] = []
    scores_by_id: dict[str, float] = {}
    for item in items:
        word_id = str(item.get("id", "")).strip()
        if not word_id:
            continue
        canonical_id = canonicalize(word_id, aliases)
        tags = set(item.get("tags", []) or [])
        tau_right_days = min(
            (
                DEFAULT_CONFIG.tau_right_by_freq[tag]
                for tag in tags
                if tag in DEFAULT_CONFIG.tau_right_by_freq
            ),
            default=DEFAULT_CONFIG.tau_right_default_days,
        )
        wrong, right, score = compute_scores(
            events_by_key.get((canonical_id, MODE), []),
            NOW,
            DEFAULT_CONFIG,
            tau_right_days,
        )
        scored.append((word_id, score))
        scores_by_id[word_id] = score

    scored.sort(key=lambda entry: (-entry[1], entry[0]))
    top_ids = [word_id for word_id, _ in scored[:LIMIT]]

    expected = {
        "now": NOW.isoformat(),
        "mode": MODE,
        "limit": LIMIT,
        "tolerance": TOLERANCE,
        "rows_count": len(rows),
        "events_count": len(events),
        "scores": scores_by_id,
        "top_ids": top_ids,
    }

    EXPECTED_PATH.write_text(
        json.dumps(expected, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {EXPECTED_PATH}")


if __name__ == "__main__":
    main()
