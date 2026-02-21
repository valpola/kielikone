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

## Quick start (desktop)
1. Export quiz data:
   python3 scripts/export_quiz.py

2. Serve the web app locally:
   cd web
   python3 -m http.server

3. Open in browser:
   http://localhost:8000

## Using on iPhone
Option A: Run a local server and open it on your phone
1. Find your computer IP address on the same Wi-Fi.
2. Start the server:
   cd web
   python3 -m http.server
3. On your phone, open:
   http://<your-computer-ip>:8000

Option B: Host on GitHub Pages (recommended)
1. Run export:
   python3 scripts/export_quiz.py
2. Push to GitHub.
3. Enable GitHub Pages in repo settings (source: main branch / web folder).
4. Open the Pages URL on your phone.

## Updating vocab
1. Edit data/lexicon.json
2. Run export:
   python3 scripts/export_quiz.py
3. Refresh the web app

## Notes
- resources/originals is ignored to avoid committing copyrighted PDFs.
- Quiz stats are stored in localStorage on the device.
