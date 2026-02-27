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
    filter_items,
    load_aliases,
    load_results,
    resolve_results_source,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS_SOURCE = resolve_results_source("")

# %%
# Filter settings for scoring subsets.
INCLUDE_TAGS = ["verb"]
EXCLUDE_TAGS: list[str] = []
MODE = "tr-en"

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
    canonical = canonicalize(word_id, aliases)
    key = (canonical, mode)
    now = datetime.now(tz=UTC)
    tags = set(id_to_tags.get(word_id, []))
    tau_right_days = min(
        (MY_CONFIG.tau_right_by_freq[tag] for tag in tags if tag in MY_CONFIG.tau_right_by_freq),
        default=MY_CONFIG.tau_right_default_days,
    )
    wrong, right, score = compute_scores(
        events_by_key.get(key, []),
        now,
        MY_CONFIG,
        tau_right_days,
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
# Unique words in reviewed.json (not all of these may have results,
# but this is the set of words we care about).
vocab_words = set()
reviewed_items: list[dict[str, object]] = []
reviewed_path = ROOT / "data" / "vocab" / "reviewed.json"
if reviewed_path.exists():
    reviewed_raw = reviewed_path.read_text(encoding="utf-8")
    reviewed_items = json.loads(reviewed_raw).get("items", []) or []
    for item in reviewed_items:
        item_id = str(item.get("id", "")).strip()
        if item_id:
            vocab_words.add(item_id)
print(f"Unique words in reviewed.json: {len(vocab_words)}")

# %%
# Create a mapping from word_id to Turkish for easy debugging.
id_to_tr: dict[str, str] = {}
id_to_en: dict[str, str] = {}
id_to_tags: dict[str, list[str]] = {}
for item in reviewed_items:
    item_id = str(item.get("id", "")).strip()
    turkish = str(item.get("turkish", "")).strip()
    english = str(item.get("english", "")).strip()
    tags = item.get("tags", []) or []
    if item_id and turkish:
        id_to_tr[item_id] = turkish
        id_to_en[item_id] = english
        id_to_tags[item_id] = tags

# %%
# Build canonical mapping to avoid duplicate alias rows in reports.
canonical_to_ids: dict[str, list[str]] = defaultdict(list)
for word_id in vocab_words:
    canonical = canonicalize(word_id, aliases)
    canonical_to_ids[canonical].append(word_id)
canonical_vocab_words = set(canonical_to_ids.keys())


def display_label(word_id: str) -> str:
    return id_to_en.get(word_id, "")


# Show words that have no results for MODE.
total_unscored = 0
for canonical in sorted(canonical_vocab_words):
    key = (canonical, MODE)
    if key not in events_by_key:
        label_id = canonical_to_ids.get(canonical, [canonical])[0]
        print(f"No {MODE} results for {canonical} = {display_label(label_id)}")
        total_unscored += 1
print(f"Total unscored words: {total_unscored}")

# %%
# Make a histogram of scores for all words (using MODE).
import matplotlib.pyplot as plt

scores = []
for canonical in canonical_vocab_words:
    scores.append(score_word(canonical, MODE))

plt.hist(scores, bins=50)
plt.xlabel("Score")
plt.ylabel("Frequency")
plt.title(f"Histogram of Scores ({MODE})")
plt.show()

# %%
# Show the top 10 lowest and top 30 highest scoring words (MODE).
scored_words = []
for canonical in canonical_vocab_words:
    score = score_word(canonical, MODE)
    scored_words.append((canonical, score))

scored_words.sort(key=lambda x: x[1])
print(f"Top 10 lowest scoring words ({MODE}):")
for word_id, score in scored_words[:10]:
    label_id = canonical_to_ids.get(word_id, [word_id])[0]
    print(f"{word_id} = {display_label(label_id)}: {score:.3f}")

print(f"Top 30 highest scoring words ({MODE}):")
for word_id, score in scored_words[-30:]:
    label_id = canonical_to_ids.get(word_id, [word_id])[0]
    print(f"{word_id} = {display_label(label_id)}: {score:.3f}")

# %%
# Filtered scoring summary using INCLUDE_TAGS/EXCLUDE_TAGS and MODE.
filtered_items = filter_items(
    reviewed_items,
    set(INCLUDE_TAGS),
    set(EXCLUDE_TAGS),
)

filtered_by_canonical: dict[str, list[dict[str, object]]] = defaultdict(list)
for item in filtered_items:
    word_id = str(item.get("id", "")).strip()
    if not word_id:
        continue
    canonical_id = canonicalize(word_id, aliases)
    filtered_by_canonical[canonical_id].append(item)

filtered_words = sorted(filtered_by_canonical.keys())
print(
    f"Filtered words: {len(filtered_words)} (include={INCLUDE_TAGS}, exclude={EXCLUDE_TAGS}, mode={MODE})"
)

filtered_scored = []
for canonical in filtered_words:
    grouped_items = filtered_by_canonical[canonical]
    representative = next(
        (entry for entry in grouped_items if str(entry.get("id", "")).strip() == canonical),
        grouped_items[0],
    )
    tags = set(representative.get("tags", []) or [])
    tau_right_days = min(
        (MY_CONFIG.tau_right_by_freq[tag] for tag in tags if tag in MY_CONFIG.tau_right_by_freq),
        default=MY_CONFIG.tau_right_default_days,
    )
    key = (canonical, MODE)
    wrong, right, score = compute_scores(
        events_by_key.get(key, []),
        datetime.now(tz=UTC),
        MY_CONFIG,
        tau_right_days,
    )
    filtered_scored.append((canonical, score, representative))

filtered_scored.sort(key=lambda x: x[1])
print(f"Top 10 lowest scoring words ({MODE}):")
for word_id, score, representative in filtered_scored[:10]:
    label_id = str(representative.get("id", "")).strip() or word_id
    print(f"{word_id} = {display_label(label_id)}: {score:.3f}")

print(f"Top 30 highest scoring words ({MODE}):")
filtered_top = sorted(filtered_scored, key=lambda x: (-x[1], x[0]))
for word_id, score, representative in filtered_top[:30]:
    label_id = str(representative.get("id", "")).strip() or word_id
    print(f"{word_id} = {display_label(label_id)}: {score:.3f}")

# %%
# Find the words tagged with "today" and show their scores (MODE).
print('Words tagged with "today":')
for item in reviewed_items:
    item_id = str(item.get("id", "")).strip()
    tags = item.get("tags", []) or []
    if "today" in tags:
        live_score = score_word(item_id, MODE)
        stored_score = item.get("today_score")
        stored_label = (
            f"{float(stored_score):.3f}"
            if isinstance(stored_score, (int, float))
            else "n/a"
        )
        print(
            f"{item_id} = {display_label(item_id)}: stored={stored_label} live={live_score:.3f}"
        )

# %%
# Show the last 10 events
print("Last 10 events:")
all_events = []
for (word_id, mode), entries in events_by_key.items():
    for timestamp, correct in entries:
        all_events.append((timestamp, word_id, mode, correct))

all_events.sort(key=lambda x: x[0], reverse=True)
for event in all_events[:10]:
    timestamp, word_id, mode, correct = event
    print(f"{timestamp}: {word_id} = {display_label(word_id)} ({mode}) - {'Correct' if correct else 'Incorrect'}")

# %%
# Load today-scores.json from resouces/debug
today_scores_path = ROOT / "resources" / "debug" / "today-scores.json"
today_scores_raw = today_scores_path.read_text(encoding="utf-8")
today_scores = json.loads(today_scores_raw)
score_items = today_scores.get("scores", {}) if isinstance(today_scores, dict) else {}
print(f"Loaded today-scores.json with {len(score_items)} entries")
# Show the scores for the words tagged with "today" from today-scores.json
print('Scores from today-scores.json for words tagged with "today":')
# The score items look like this:
# {'id': 'cand-a1-cases-0047', 'score': 1}
# We want to match the 'id' with the item_id in reviewed_items and show both scores.
for item in score_items:
    item_id = str(item.get("id", "")).strip()
    score = item.get("score")
    if not item_id:
        continue
    tags = id_to_tags.get(item_id, [])
    if "today" in tags:
        label = display_label(item_id)
        print(f"{item_id} = {label}: today-scores.json={score:.3f} live={score_word(item_id, MODE):.3f}")

# %%
