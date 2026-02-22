# Turkish Vocab Quiz (MVP)

Personal Turkish vocabulary study tool with:
- Canonical word list in JSON
- Python export script
- Static web quiz that runs on iPhone Safari

## Structure
- data/vocab/*.json: canonical vocab split into multiple files
- data/tags.json: finite editable tag registry
- data/candidates/*.candidates.json: extracted items pending review
- scripts/export_quiz.py: exports web/data/quiz.json
- web/: static quiz app
- resources/originals/: source PDFs (ignored by git)

## Default usage: GitHub Pages (recommended)
1. Export quiz data:
   python3 scripts/export_quiz.py
2. Commit and push the updated web/data/quiz.json.
3. GitHub Pages is already configured via Actions.
4. Open the Pages URL in Chrome (desktop or phone):
   https://valpola.github.io/kielikone/

## Setup (desktop)
1. Create and activate a virtualenv (required for make targets):
   python3 -m venv .venv
   source .venv/bin/activate

## Updating vocab
1. Edit data/vocab/*.json
2. Run export:
   python3 scripts/export_quiz.py
3. Refresh the web app

## Publish checklist
1. python3 scripts/export_quiz.py
2. git add data/vocab data/tags.json web/data/quiz.json
3. git commit -m "Update vocab" && git push

## Make publish
Run:
   make publish

## Test results endpoint
Run:
   make test-results

Optional overrides:
- TR_QUIZ_API_KEY=your_key
- RESULTS_ENDPOINT=https://script.google.com/.../exec

## Notes
- resources/originals is ignored to avoid committing copyrighted PDFs.
- Quiz stats are stored in localStorage on the device.
- If CSS/JS changes do not appear on the phone, bump the cache-busting query
   strings in web/index.html (style.css and config.js).

## Keyboard shortcuts
- Enter: show answer
- f: I was correct
- j: I was incorrect
- n: next

## Mobile UX
- After showing the answer, the input blurs so the keyboard hides.
- The "Show Answer" button hides after reveal to keep the layout clean.

## Tag filters (include/exclude)
- Add/edit allowed tags in data/tags.json.
- Assign tag IDs to each vocab item in data/vocab/*.json.
- In the quiz UI, use Include tags and Exclude tags to filter what is quizzed.

## Extraction review pipeline
1. Extract candidates from a source file:
   make extract-candidates INPUT="resources/originals/A1_-_1A.pdf"
2. Review the generated file in data/candidates/*.candidates.json.
3. Mark accepted items with status: approved.
4. Merge approved items:
   make merge-candidates CANDIDATE="data/candidates/A1_-_1A.candidates.json"
5. Validate tags and export:
   make validate-tags
   make publish

## Google Sheets results logging
See [docs/google_sheets.md](docs/google_sheets.md) to enable syncing quiz results.

## Handover
See [docs/handover.md](docs/handover.md) for full operational notes.

## Changelog
See [CHANGELOG.md](CHANGELOG.md) for recent changes.
