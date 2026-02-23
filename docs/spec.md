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
- Include/exclude tag filtering in quiz selection.

## Data Model (canonical)
Stored in data/vocab/*.json with tag registry in data/tags.json.

Aliases for dedupe live in data/aliases.json as alias -> canonical ID.

```
{
  "source": "reviewed",
  "items": [
    {
      "id": "cand-a1-1a-0001",
      "turkish": "Merhaba!",
      "english": "Hello!",
      "priority": 3,
      "tags": ["unit-a1-1a"],
      "source": "A1_-_1A.pdf",
      "notes": "",
      "status": "approved"
    }
  ]
}
```

Fields:
- id: stable string ID
- turkish / english: strings
- priority: integer 1-5 (manual control)
- tags: string array of tag IDs (must exist in data/tags.json)
- source: filename or label
- notes: optional manual notes
- last_seen: optional ISO date string

Tag registry fields:
- id: stable tag ID
- label: human-readable name
- group: optional group (unit, frequency, part_of_speech, theme)

## Study Scheduling
- Start with manual priority only.
- Add a daily prioritization script that tags a fixed-size "today" list based on
  decaying correct/incorrect scores from Google Sheets results.
- If aliases exist, canonicalize IDs for scoring so historical results do not
  need to be rewritten.

## Content Pipeline
1. Extract vocab from PDFs/images with scripts.
2. Save extracted candidates to data/candidates/*.candidates.json.
3. Manual review (approve/reject, add tags).
4. Merge approved items into data/vocab/*.json.
5. Run export script to generate web/data/quiz.json.

## Web App Behavior
- Loads web/data/quiz.json.
- Quiz direction toggle: TR -> EN or EN -> TR.
- Prompt + typed answer.
- Show answer button + self-grade correct/incorrect.
- Default include tag: today.
- Stop asking a word after N correct answers in-session (configurable in Options).
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
