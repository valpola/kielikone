# Handover Guide

This document explains how the repo works, how to update content, and how to keep the phone quiz and Google Sheets logging running.

## What this repo does
- Stores a canonical Turkish vocab list in JSON.
- Exports a compact JSON file used by a static web quiz.
- Publishes the web app to GitHub Pages via GitHub Actions.
- Optionally logs quiz results to Google Sheets via Apps Script.

## Repository layout
- data/vocab/*.json: Canonical vocabulary data (split files).
- data/tags.json: Finite editable tag registry.
- data/aliases.json: Alias -> canonical ID mapping for dedupe.
- data/candidates/*.candidates.json: Extracted candidates pending review.
- scripts/export_quiz.py: Builds web/data/quiz.json from data/vocab/*.json.
- scripts/dedupe_vocab.py: Scans and applies duplicate merges.
- web/: Static web app (HTML/CSS/JS).
- web/config.js: Results logging config (Apps Script URL + enable flag).
- docs/google_sheets.md: Apps Script setup instructions.
- resources/originals/: Source PDFs (ignored by git).
- resources/access_keys/: Apps Script URLs or notes (ignored by git).

## Local setup
- Python 3 is required (no external packages).
- Create a virtualenv with python3 -m venv .venv (make targets expect it).

## Update vocabulary
1. Edit data/vocab/*.json (add/update entries).
2. (Optional) Scan and merge duplicates:
  python3 scripts/dedupe_vocab.py --scan
  python3 scripts/dedupe_vocab.py --apply
3. Run export:
   python3 scripts/export_quiz.py
4. Commit and push the updated web/data/quiz.json.

Shortcut:
- make publish

## Tag system
- Allowed tags are defined in data/tags.json.
- Vocab items reference tag IDs in their tags field.
- The web app supports include/exclude tag filtering.
- Run make validate-tags to catch unknown tags.

## Daily prioritization (today tag)
1. Export the Google Sheet as CSV (or use a CSV URL).
2. Run:
  python3 scripts/build_today.py --results "<csv-or-url>" --limit 30
3. Run make publish.

Notes:
- The script overwrites the today tag each run.
- Use RESULTS_SOURCE and TODAY_LIMIT env vars to avoid flags.
- If resources/access_keys/google_sheets.txt contains the Apps Script URL,
  build_today will use it automatically (expects a CSV response).
- If data/aliases.json exists, build_today uses it to merge results across
  duplicate IDs.

## Duplicate handling
- Alias mappings live in data/aliases.json (alias -> canonical ID).
- scripts/dedupe_vocab.py can scan for duplicates and apply merges.
- Build_today canonicalizes IDs using the alias map so historical results can
  stay unchanged.

## Extraction review pipeline
1. Run extraction:
  make extract-candidates INPUT="resources/originals/A1_-_1A.pdf"
2. Review and edit candidates in data/candidates/*.candidates.json.
3. Mark accepted items with status = approved.
4. Merge:
  make merge-candidates CANDIDATE="data/candidates/A1_-_1A.candidates.json"
5. Run make validate-tags and make publish.

Optional helper:
- scripts/tag_candidates.py applies unit and POS tags from PDFs.

## How publishing works
- GitHub Pages is deployed from the web/ folder using GitHub Actions.
- The live site is:
  https://valpola.github.io/kielikone/

## Keyboard shortcuts
- Enter: show answer
- f: I was correct
- j: I was incorrect
- n: next

## Mobile UX
- Answer input blurs after reveal to dismiss the keyboard.
- Show Answer button hides after reveal.
- "Correct to finish" controls how many correct answers are needed before a word
  is skipped for the rest of the session.

## Google Sheets logging
Logging works via an Apps Script Web App. The static site posts results to the script.

Key files:
- web/config.js: resultsEndpoint and resultsEnabled
- docs/google_sheets.md: Script code and deployment steps

Notes:
- The Apps Script must be deployed with access = Anyone.
- The API key is typed into the web app on first use and stored in localStorage.

## Changing the Apps Script URL
1. Deploy a new Web App version in Apps Script.
2. Update web/config.js with the new URL.
3. Commit and push.

## Testing results logging
Run:
- make test-results

This sends a sample POST to the Apps Script endpoint and prints the response.

Optional overrides:
- TR_QUIZ_API_KEY=your_key
- RESULTS_ENDPOINT=https://script.google.com/.../exec

## Common issues
- 401 Unauthorized: Apps Script access must be Anyone and API key must match.
- CORS/preflight errors: The app sends form-encoded data; do not switch to JSON.
- Old assets used: Hard refresh, or update cache-busting in web/index.html
  (style.css, config.js, app.js, today_scoring.js query strings) and update
  APP_CONFIG.cacheBust in web/config.js (used for quiz.json and aliases.json).

## Developer notes
- Web recompute uses the Apps Script endpoint in web/config.js and appends
  api_key for CSV reads; the API key is stored in localStorage after first prompt.
- Today scoring parity tests require Node for JS and Python for the live run.
  For live tests, provide RESULTS_ENDPOINT and RESULTS_API_KEY/TR_QUIZ_API_KEY.
- Add ?debug=1 to the web app URL to show a debug-only button that downloads
  the latest recompute scores as today-scores.json.

## Security notes
- The static site is public. Do not store secrets in the repo.
- resources/access_keys/ is ignored by git for local notes only.

## Ownership checklist
- Confirm GitHub Pages is enabled and Actions deploys successfully.
- Verify the live site loads and logs results.
- Keep a copy of the Apps Script project and deployment URL.
