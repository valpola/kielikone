# %%
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
import json

from build_today import (
    DEFAULT_CONFIG,
    ScoreConfig,
    canonicalize,
    compute_scores,
    event_stream,
    load_aliases,
    load_results,
    resolve_results_source,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS_SOURCE = resolve_results_source("")

# %%
# Load aliases and results.
aliases = load_aliases()
results_source = RESULTS_SOURCE

if not results_source:
    raise ValueError(
        "No results source found. Set RESULTS_SOURCE env var or add a URL to "
        "resources/access_keys/google_sheets.txt."
    )

rows = load_results(results_source)
print(f"Loaded {len(rows)} result rows")

# %%
# Build canonicalized event stream.
events = event_stream(rows, aliases)
print(f"Parsed {len(events)} events")

# %%
# Group events by (word_id, mode).
events_by_key: dict[tuple[str, str], list[tuple[datetime, bool]]] = defaultdict(list)
for timestamp, word_id, mode, correct in events:
    events_by_key[(word_id, mode)].append((timestamp, correct))

print(f"Unique word+mode keys: {len(events_by_key)}")

# %%
# Show the most active words (combined across modes).
activity: dict[str, int] = defaultdict(int)
for (word_id, _mode), items in events_by_key.items():
    activity[word_id] += len(items)

for word_id, count in sorted(activity.items(), key=lambda item: -item[1])[:10]:
    print(word_id, count)

# %%
# Score a specific word with build_today logic.
MY_CONFIG = DEFAULT_CONFIG
# MY_CONFIG = ScoreConfig(weight_wrong=1.0)

def score_word(word_id: str, mode: str) -> float:
    key = (word_id, mode)
    now = datetime.now(tz=UTC)
    wrong, right, score = compute_scores(
        events_by_key.get(key, []),
        now,
        MY_CONFIG,
        MY_CONFIG.tau_right_default_days,
    )
    # print(
    #     f"{word_id} {mode}: wrong={wrong:.2f} right={right:.2f} score={score:.3f}"
    # )
    return score

# Example:
# score_word("cand-a1-0a-0001", "en-tr")

# %%
# Compare scores for a word across modes (en-tr, tr-en).
def score_both(word_id: str) -> None:
    for mode in ("en-tr", "tr-en"):
        score_word(word_id, mode)

# Example:
# score_both("cand-a1-0a-0001")

# %%
# List events for a word (shows canonicalization in action).
def show_events(word_id: str) -> None:
    canonical = canonicalize(word_id, aliases)
    for mode in ("en-tr", "tr-en"):
        key = (canonical, mode)
        entries = events_by_key.get(key, [])
        print(f"{canonical} {mode}: {len(entries)} events")
        for timestamp, correct in entries[:10]:
            print(" ", timestamp.isoformat(), correct)

# Example:
# show_events("cand-a1-2a-0002")

# %%
# Uniques words in quiz.json (not all of these may have results,
# but this is the set of words we care about).
vocab_words = set()
quiz_paths = [ROOT / "web" / "data" / "quiz.json", ROOT / "data" / "quiz.json"]
for quiz_path in quiz_paths:
    if not quiz_path.exists():
        continue
    quiz_raw = quiz_path.read_text(encoding="utf-8")
    quiz_data = json.loads(quiz_raw)
    for item in quiz_data.get("items", []):
        item_id = str(item.get("id", "")).strip()
        if item_id:
            vocab_words.add(item_id)
    break
print(f"Unique words in quiz.json: {len(vocab_words)}")

# %%
# Create a mapping from word_id to Turkish for easy debugging.
id_to_tr: dict[str, str] = {}
for quiz_path in quiz_paths:
    if not quiz_path.exists():
        continue
    quiz_raw = quiz_path.read_text(encoding="utf-8")
    quiz_data = json.loads(quiz_raw)
    for item in quiz_data.get("items", []):
        item_id = str(item.get("id", "")).strip()
        turkish = str(item.get("turkish", "")).strip()
        if item_id and turkish:
            id_to_tr[item_id] = turkish
    break

# %%
# Show words that have no "en-tr" results.
total_unscored = 0
for word_id in sorted(vocab_words):
    key = (canonicalize(word_id, aliases), "en-tr")
    if key not in events_by_key:
        print(f"No en-tr results for {word_id} = {id_to_tr.get(word_id, '')}")
        total_unscored += 1
print(f"Total unscored words: {total_unscored}")

# %%
# Make a histrogram of scores for all words (using "en-tr" mode).
import matplotlib.pyplot as plt

scores = []
for word_id in vocab_words:
    key = (canonicalize(word_id, aliases), "en-tr")
    scores.append(score_word(word_id, "en-tr"))

plt.hist(scores, bins=50)
plt.xlabel("Score")
plt.ylabel("Frequency")
plt.title("Histogram of Scores (en-tr)")
plt.show()

# %%
# Show the top 10 lowest and top 30 highest scoring words (en-tr).
scored_words = []
for word_id in vocab_words:
    key = (canonicalize(word_id, aliases), "en-tr")
    score = score_word(word_id, "en-tr")
    scored_words.append((word_id, score))

scored_words.sort(key=lambda x: x[1])
print("Top 10 lowest scoring words (en-tr):")
for word_id, score in scored_words[:10]:
    print(f"{word_id} = {id_to_tr.get(word_id, '')}: {score:.3f}")

print("Top 30 highest scoring words (en-tr):")
for word_id, score in scored_words[-30:]:
    print(f"{word_id} = {id_to_tr.get(word_id, '')}: {score:.3f}")

# %%
