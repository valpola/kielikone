#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_today import (  # noqa: E402
    DEFAULT_CONFIG,
    compute_scores,
    event_stream,
    load_results,
    load_text,
)


TOLERANCE = float(os.environ.get("TODAY_SCORE_TOLERANCE", "1e-4"))
DEFAULT_LIMIT = int(os.environ.get("TODAY_LIMIT", "30"))
DEFAULT_MODE = os.environ.get("TODAY_MODE", "en-tr")


def read_endpoint_from_config() -> str:
    config_path = ROOT / "web" / "config.js"
    if not config_path.exists():
        return ""
    text = config_path.read_text(encoding="utf-8")
    match = re.search(r"resultsEndpoint\s*:\s*\"([^\"]+)\"", text)
    return match.group(1) if match else ""


def build_csv_url(endpoint: str) -> str:
    if "?" in endpoint:
        return f"{endpoint}&format=csv"
    return f"{endpoint}?format=csv"


def load_quiz_items() -> list[dict[str, object]]:
    quiz_path = ROOT / "web" / "data" / "quiz.json"
    if not quiz_path.exists():
        raise RuntimeError("web/data/quiz.json is missing")
    data = json.loads(quiz_path.read_text(encoding="utf-8"))
    return data.get("items", [])


def load_aliases() -> dict[str, str]:
    aliases_path = ROOT / "data" / "aliases.json"
    if not aliases_path.exists():
        return {}
    raw = json.loads(aliases_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    aliases = raw.get("aliases", {})
    if not isinstance(aliases, dict):
        return {}
    return {
        str(alias).strip(): str(canonical).strip()
        for alias, canonical in aliases.items()
        if str(alias).strip() and str(canonical).strip()
    }


def compute_python_scores(items, events_by_key, mode, now):
    scored = []
    scores_by_id = {}
    for item in items:
        word_id = str(item.get("id", "")).strip()
        if not word_id:
            continue
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
            events_by_key.get((word_id, mode), []),
            now,
            DEFAULT_CONFIG,
            tau_right_days,
        )
        scored.append((word_id, score))
        scores_by_id[word_id] = score

    scored.sort(key=lambda entry: (-entry[1], entry[0]))
    return scored, scores_by_id


def main() -> int:
    endpoint = os.environ.get("RESULTS_ENDPOINT", "").strip() or read_endpoint_from_config()
    if not endpoint:
        print("ERROR: No results endpoint configured.")
        return 2

    csv_url = build_csv_url(endpoint)
    csv_text = load_text(csv_url)
    rows = load_results(csv_url)
    if not rows:
        print("ERROR: No rows returned from results endpoint.")
        return 2

    aliases = load_aliases()
    events = event_stream(rows, aliases)

    alias_keys = set(aliases.keys())
    bad_aliases = [word_id for _ts, word_id, _mode, _correct in events if word_id in alias_keys]
    if bad_aliases:
        print("ERROR: Alias IDs still present after canonicalization.")
        print("Examples:", bad_aliases[:5])
        return 1

    events_by_key = {}
    for timestamp, word_id, mode, correct in events:
        events_by_key.setdefault((word_id, mode), []).append((timestamp, correct))

    items = load_quiz_items()
    now = datetime.now(tz=UTC)

    python_scored, python_scores = compute_python_scores(
        items, events_by_key, DEFAULT_MODE, now
    )
    python_top_ids = [word_id for word_id, _ in python_scored[:DEFAULT_LIMIT]]

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / "input.json"
        input_path.write_text(
            json.dumps(
                {
                    "csvText": csv_text,
                    "quizItems": items,
                    "aliases": aliases,
                    "mode": DEFAULT_MODE,
                    "limit": DEFAULT_LIMIT,
                    "now": now.isoformat(),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

        node_script = ROOT / "scripts" / "tests" / "run_today_scoring_node.js"
        result = subprocess.run(
            ["node", str(node_script), str(input_path)],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("ERROR: Node scoring failed.")
            print(result.stderr.strip())
            return 2

        payload = json.loads(result.stdout)

    if payload.get("rowsCount") != len(rows):
        print("ERROR: Row count mismatch.")
        print("Python:", len(rows), "Node:", payload.get("rowsCount"))
        return 1

    if payload.get("eventsCount") != len(events):
        print("ERROR: Event count mismatch.")
        print("Python:", len(events), "Node:", payload.get("eventsCount"))
        return 1

    node_scores = payload.get("scores", {})
    mismatches = []
    for word_id, score in python_scores.items():
        if word_id not in node_scores:
            mismatches.append((word_id, "missing", None))
            continue
        delta = abs(score - float(node_scores[word_id]))
        if delta > TOLERANCE:
            mismatches.append((word_id, score, node_scores[word_id]))
            if len(mismatches) >= 5:
                break

    if mismatches:
        print("ERROR: Score mismatches beyond tolerance.")
        for entry in mismatches:
            print(entry)
        return 1

    node_top_ids = payload.get("topIds", [])
    if node_top_ids != python_top_ids:
        print("ERROR: Top-N mismatch.")
        print("Python:", python_top_ids)
        print("Node:", node_top_ids)
        return 1

    print("Live today scoring integration tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
