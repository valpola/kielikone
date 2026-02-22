# Language Learning App (Turkish) - MVP Spec

## Goals
- Build a personal Turkish vocab study tool with fast iteration on a computer and a simple quiz web app for iPhone.
- Use PDFs in resources/originals as the initial content source, with VLM-assisted extraction and manual cleanup.

## Non-goals (for MVP)
- Full mobile app
- Multi-user auth
- Hosted database and realtime sync
- Audio or speech recognition

## MVP Scope
- Vocabulary-only, TR <-> EN meaning quizzes.
- Desktop scripts for content extraction, cleanup, and export.
- Static web app that loads exported JSON and runs on iPhone Safari.
- Optional Google Sheets logging via Apps Script.

## Data Model (canonical)
Stored in data/lexicon.json.

```
{
  "version": 1,
  "metadata": {
    "language": "tr",
    "created": "2026-02-21"
  },
  "items": [
    {
      "id": "tr-0001",
      "turkish": "merhaba",
      "english": "hello",
      "priority": 3,
      "tags": ["greeting"],
      "source": "A1_-_1A.pdf",
      "notes": "",
      "last_seen": ""
    }
  ]
}
```

Fields:
- id: stable string ID
- turkish / english: strings
- priority: integer 1-5 (manual control)
- tags: string array for grouping
- source: filename or label
- notes: optional manual notes
- last_seen: optional ISO date string

## Study Scheduling
- Start with manual priority only.
- Quiz selection weights by priority and recency (tracked in localStorage on the web app).

## Content Pipeline
1. Extract vocab from PDFs with a VLM (manual prompt and review).
2. Save raw output (JSON/CSV) in a staging file.
3. Manual cleanup and merge into data/lexicon.json.
4. Run export script to generate web/data/quiz.json.

## Web App Behavior
- Loads web/data/quiz.json.
- Quiz direction toggle: TR -> EN or EN -> TR.
- Prompt + typed answer.
- Show answer button + self-grade correct/incorrect.
- Local stats stored in localStorage (no server).
- Optional results logging to Google Sheets (Apps Script Web App).
- API key prompt (stored in localStorage) for results logging.

## Hosting
- Static hosting only for MVP (GitHub Pages).
- Deployed via GitHub Actions from the web/ folder.
- Phone accesses the hosted static site at:
  https://valpola.github.io/kielikone/

## Risks / Open Questions
- VLM extraction quality for Turkish content.
- Curation effort for consistent IDs and translations.
- Decide export rules for tags and priority mapping.
- Apps Script access must remain public; keep API key private.
