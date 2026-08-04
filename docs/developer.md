# Developer guide

How the repo is put together and how to change it. For using the quiz, see the
[README](../README.md). For the conventions governing vocabulary content — how words are
sourced, glossed, tagged and deduplicated — see [CLAUDE.md](../CLAUDE.md), which is the
authority on that and is kept current.

## What it is

A static site plus a Postgres database. No backend of our own:

- `web/` is plain HTML/CSS/JS, served by GitHub Pages, with no build step.
- The vocabulary is a JSON file, `web/data/quiz.json`, generated from source data in `data/`.
- Answers go straight from the browser to **Supabase** (Postgres + PostgREST), with row-level
  security doing the access control.
- Scoring and the practice set are computed **in the browser**, from the answer history.

## Repository layout

| Path | What it holds |
| --- | --- |
| `data/candidates/*.candidates.json` | Source of truth for vocabulary, one file per sweep |
| `data/vocab/reviewed.json` | Generated: all candidates merged, aliases applied |
| `data/tags.json` | The tag registry. A tag not listed here fails the export |
| `data/aliases.json` | `alias id -> canonical id`, for merging duplicate entries |
| `web/` | The app. `app.js`, `today_scoring.js`, `config.js`, `style.css` |
| `web/data/quiz.json` | Generated: what the app actually loads |
| `scripts/` | The pipeline and one-off tools |
| `resources/originals/` | Coursebook PDFs — gitignored, do not commit |

Edit candidate files, never `reviewed.json` or `quiz.json`; both are regenerated.

## Content pipeline

```bash
.venv/bin/python scripts/rebuild_reviewed.py     # candidates -> data/vocab/reviewed.json
.venv/bin/python scripts/dedupe_vocab.py --apply # apply data/aliases.json
.venv/bin/python scripts/validate_tags.py        # every tag must be in data/tags.json
.venv/bin/python scripts/export_quiz.py          # -> web/data/quiz.json, web/data/aliases.json
```

Then bump `cacheBust` in `web/config.js` **and** the `?v=` query strings in
`web/index.html`, commit, and push. GitHub Actions (`.github/workflows/static.yml`) publishes
`web/` on every push to `main`.

The cache-bust bump is not optional: without it browsers keep serving the old `app.js`
against the new deck.

### Item shape

```json
{
  "id": "cand-a1-5b-0035",
  "turkish": "geçirmek",
  "english": "to put in",
  "priority": 3,
  "tags": ["unit-a1-5b", "unit-a1", "verb"],
  "source": "A1_-_5B.pdf (the list glosses geçirmek as “put in”)",
  "hint_tr_en": "(bir şeyi bir yere)",
  "hint_en_tr": "(sth. to sb.)",
  "notes": "",
  "status": "approved"
}
```

`id` is permanent — the answer history is keyed on it. Renaming a word's *meaning* under an
existing id silently transfers its score history to the new sense; add a new entry instead.

`hint_tr_en` shows when quizzing TR→EN, `hint_en_tr` when quizzing EN→TR. The latter must
contain no Turkish, or it leaks the answer.

### Aliases

`data/aliases.json` maps a duplicate id onto the canonical one. `dedupe_vocab.py --apply`
merges the entry and its tags; `build_today.py` and `today_scoring.js` canonicalise event
ids, so history recorded against the alias still counts. Nothing has to be rewritten in the
database.

## The practice set

Computed client-side and **never shipped in the deck**. `export_quiz.py` strips `SESSION_TAG`
(`practice`) from every exported item; the pipeline above does not run `build_today.py` at
all. A batch baked in at build time would be stale on arrival and would override whatever the
device had worked out for itself.

`build_today.py` still exists for offline analysis, and writes the tag into the vocab files
when you run it by hand. That is fine — the export strips it.

### Scoring

`web/today_scoring.js` is the reference implementation, mirrored by `scripts/build_today.py`
for offline runs. Per (word, mode):

```
score = 1.5 * wrongScore - 1.0 * rightScore + 1 / (1 + totalEvents)
```

`wrongScore` and `rightScore` are counts decayed exponentially toward the present — τ = 21
days for wrong answers, 7 for right, so a mistake keeps a word in circulation far longer than
a success removes it. The trailing term is a novelty bonus, which is what floats never-seen
words to the top.

Decay composes exactly, so a word's whole history reduces to five numbers: `wrongScore`,
`lastWrong`, `rightScore`, `lastRight`, `totalEvents`. Compaction would be lossless if the
event log ever needs it.

Anything time-dependent must pin `now` when tested — see the clock freeze in
`test_recompute_today_app.js` for why.

## Storage

Supabase, configured in `web/config.js` (`supabaseUrl`, `supabaseKey` — the publishable key
is public by design). Access is granted by RLS policies that require the app secret the user
enters once and which lives in `localStorage`. Schema, policies, the delete window and the
multi-user setup are in [supabase.md](supabase.md).

Three things worth knowing before touching the sync path:

- **Writes are idempotent.** `results` has `unique(client_event_id)`, and the app posts to
  `?on_conflict=client_event_id` with `Prefer: resolution=ignore-duplicates`. A retry whose
  response was lost is a no-op. Omitting `on_conflict` silently reverts this to a 409.
- **Reads are incremental and paged.** PostgREST caps a response at 1000 rows, so
  `fetchResultRows` pages with `Range` headers, asking only for `answered_at=gt.<last seen>`
  and merging into a local snapshot.
- **A DELETE that matches nothing returns 204**, including when no policy permits it. Always
  send `Prefer: return=representation` and count the returned rows, or you will believe a
  delete worked when the row is still there.

The device keeps a history snapshot and a queue of unsent answers in `localStorage`, which is
what makes offline work. Local events are pruned only after a successful read, so they can
overlap the snapshot — the dedupe inside `eventStream` is load-bearing, not belt-and-braces.

## Notes from the app

"+ Note on this word" files a GitHub issue on this repo, labelled `vocab-comment`, titled
`[note] <word>`, carrying the word id and quiz direction. Read them with:

```bash
python3 scripts/fetch_comments.py     # public API, no auth needed
```

Act on each, then close it. The write token lives in `resources/github_token.txt`
(gitignored).

## Testing

```bash
node scripts/tests/test_today_scoring_offline.js   # scoring maths against fixtures
node scripts/tests/test_today_filters_offline.js   # tag filtering
node scripts/tests/test_recompute_today_app.js     # app.js recompute, stubbed DOM and fetch
```

All three pass. The fixtures are CSV transcripts of the old Google Sheet; since the app no
longer parses CSV, `scripts/tests/csv_rows.js` does that for the harness.

**Retired and not runnable:** `scripts/test_results_endpoint.py`,
`scripts/test_results_whoami.py` and `scripts/tests/compare_today_scoring_integration.py` all
target the Apps Script endpoint, so `make test-all` and `make test-results` fail. They need
porting to Supabase or deleting.

The `Makefile` predates the current pipeline too: `make publish` does not run
`rebuild_reviewed`/`dedupe`, and `make rebuild-reviewed-today` still bakes in a practice set.
Prefer the explicit commands above.

## History

- [google_sheets.md](google_sheets.md) — the previous backend. Still accurate for the archive
  and for `scripts/migrate_results_to_supabase.py`, which re-imports it. The 13,941-row
  import is idempotent, keyed on a deterministic `sheet-<sha1>` event id.
- [spec.md](spec.md) — the original MVP spec, February 2026. Kept for history; several of its
  non-goals (multi-user, hosted database) are now goals.
