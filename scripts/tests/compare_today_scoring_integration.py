#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_today import (  # noqa: E402
    DEFAULT_CONFIG,
    canonicalize,
    compute_scores,
    event_stream,
    load_results,
    load_text,
)


TOLERANCE = float(os.environ.get("TODAY_SCORE_TOLERANCE", "1e-4"))
DEFAULT_LIMIT = int(os.environ.get("TODAY_LIMIT", "30"))
DEFAULT_MODE = os.environ.get("TODAY_MODE", "en-tr")
RESULTS_API_KEY = os.environ.get("RESULTS_API_KEY", "").strip() or os.environ.get(
    "TR_QUIZ_API_KEY", ""
).strip()


def read_endpoint_from_config() -> str:
    config_path = ROOT / "web" / "config.js"
    if not config_path.exists():
        return ""
    text = config_path.read_text(encoding="utf-8")
    match = re.search(r"resultsEndpoint\s*:\s*\"([^\"]+)\"", text)
    return match.group(1) if match else ""


def build_csv_url(endpoint: str) -> str:
    if "?" in endpoint:
        url = f"{endpoint}&format=csv"
    else:
        url = f"{endpoint}?format=csv"
    if not RESULTS_API_KEY:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "api_key" not in query:
        query["api_key"] = RESULTS_API_KEY
    updated = parsed._replace(query=urlencode(query))
    return urlunparse(updated)


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


def compute_python_scores(items, events_by_key, mode, now, aliases):
    scored = []
    scores_by_id = {}
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
            events_by_key.get((canonical_id, mode), []),
            now,
            DEFAULT_CONFIG,
            tau_right_days,
        )
        scored.append((word_id, score))
        scores_by_id[word_id] = score

    scored.sort(key=lambda entry: (-entry[1], entry[0]))
    return scored, scores_by_id


def filter_items_by_tags(items, include_tags, exclude_tags):
    include = set(include_tags or [])
    exclude = set(exclude_tags or [])
    filtered = []
    for item in items:
        tags = set(item.get("tags", []) or [])
        if any(tag not in tags for tag in include):
            continue
        if any(tag in tags for tag in exclude):
            continue
        filtered.append(item)
    return filtered


def select_filter_tags(items):
    counts: dict[str, int] = {}
    for item in items:
        for tag in item.get("tags", []) or []:
            if tag == "today":
                continue
            counts[tag] = counts.get(tag, 0) + 1
    if not counts:
        return [], []
    sorted_tags = sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))
    include_tag = sorted_tags[0][0]
    exclude_tag = sorted_tags[1][0] if len(sorted_tags) > 1 else None
    return [include_tag], ([exclude_tag] if exclude_tag else [])


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

    include_tags, exclude_tags = select_filter_tags(items)
    alt_mode = "tr-en" if DEFAULT_MODE != "tr-en" else "en-tr"

    cases = [
        {
            "name": "default",
            "mode": DEFAULT_MODE,
            "include_tags": [],
            "exclude_tags": [],
            "limit": DEFAULT_LIMIT,
        },
        {
            "name": "filtered-mode",
            "mode": alt_mode,
            "include_tags": include_tags,
            "exclude_tags": exclude_tags,
            "limit": None,
        },
    ]

    node_script = ROOT / "scripts" / "tests" / "run_today_scoring_node.js"

    for case in cases:
        filtered_items = filter_items_by_tags(
            items, case["include_tags"], case["exclude_tags"]
        )
        limit = case["limit"]
        if limit is None:
            limit = min(DEFAULT_LIMIT, len(filtered_items)) if filtered_items else 0

        python_scored, python_scores = compute_python_scores(
            filtered_items, events_by_key, case["mode"], now, aliases
        )
        python_top_ids = [word_id for word_id, _ in python_scored[:limit]]

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.json"
            input_path.write_text(
                json.dumps(
                    {
                        "csvText": csv_text,
                        "quizItems": items,
                        "aliases": aliases,
                        "mode": case["mode"],
                        "limit": limit,
                        "now": now.isoformat(),
                        "includeTags": case["include_tags"],
                        "excludeTags": case["exclude_tags"],
                    },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["node", str(node_script), str(input_path)],
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"ERROR: Node scoring failed ({case['name']}).")
                print(result.stderr.strip())
                return 2

            payload = json.loads(result.stdout)

        if payload.get("rowsCount") != len(rows):
            print(f"ERROR: Row count mismatch ({case['name']}).")
            print("Python:", len(rows), "Node:", payload.get("rowsCount"))
            return 1

        if payload.get("eventsCount") != len(events):
            print(f"ERROR: Event count mismatch ({case['name']}).")
            print("Python:", len(events), "Node:", payload.get("eventsCount"))
            return 1

        node_filtered_ids = payload.get("filteredIds", [])
        python_filtered_ids = [item.get("id") for item in filtered_items]
        if node_filtered_ids != python_filtered_ids:
            print(f"ERROR: Filtered IDs mismatch ({case['name']}).")
            print("Python:", python_filtered_ids[:10])
            print("Node:", node_filtered_ids[:10])
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
            print(f"ERROR: Score mismatches beyond tolerance ({case['name']}).")
            for entry in mismatches:
                print(entry)
            return 1

        node_top_ids = payload.get("topIds", [])
        if node_top_ids != python_top_ids:
            print(f"ERROR: Top-N mismatch ({case['name']}).")
            print("Python:", python_top_ids)
            print("Node:", node_top_ids)
            return 1

    print("Live today scoring integration tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
