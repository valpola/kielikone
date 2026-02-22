# Turkish Vocab Quiz (MVP)

Personal Turkish vocabulary study tool with:
- Canonical word list in JSON
- Python export script
- Static web quiz that runs on iPhone Safari

## Structure
- data/lexicon.json: canonical vocab list
- scripts/export_quiz.py: exports web/data/quiz.json
- web/: static quiz app
- resources/originals/: source PDFs (ignored by git)

## Default usage: GitHub Pages (recommended)
1. Export quiz data:
   python3 scripts/export_quiz.py
2. Commit and push the updated web/data/quiz.json.
3. GitHub Pages is already configured via Actions.
4. Open the Pages URL on your phone:
   https://valpola.github.io/kielikone/

## Quick start (desktop)
1. Export quiz data:
   python3 scripts/export_quiz.py
2. Serve the web app locally:
   cd web
   python3 -m http.server
3. Open in browser:
   http://localhost:8000

## Using on iPhone (local server)
1. Find your computer IP address on the same Wi-Fi.
2. Start the server:
   cd web
   python3 -m http.server
3. On your phone, open:
   http://<your-computer-ip>:8000

## Updating vocab
1. Edit data/lexicon.json
2. Run export:
   python3 scripts/export_quiz.py
3. Refresh the web app

## Publish checklist
1. python3 scripts/export_quiz.py
2. git add data/lexicon.json web/data/quiz.json
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

## Google Sheets results logging
See [docs/google_sheets.md](docs/google_sheets.md) to enable syncing quiz results.
