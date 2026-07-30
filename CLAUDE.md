# kielikone — project notes

Personal Turkish vocabulary quiz (static site on GitHub Pages: `valpola.github.io/kielikone`).
Deck source is `data/candidates/*.candidates.json`; the pipeline rebuilds `web/data/quiz.json`
(`rebuild_reviewed.py` → `dedupe_vocab.py --apply` → `build_today.py --limit 30` →
`validate_tags.py` → `export_quiz.py`). On each deploy bump `cacheBust` in `web/config.js`
and the `?v=` in `web/index.html`, then commit + push (GitHub Pages serves `main`).

## Targeted practice drills

The flashcard app can't grade translations, so *contrastive / grammar practice* runs
interactively here in Claude Code, on request — it complements the phone flashcards.

When asked to run a practice/drill session:
1. **Pick a target** — a confusable set from `docs/exercise_targets.md` and/or a
   construction from `docs/grammar_topics.md`.
2. **Generate** a handful of short **EN→TR** sentences using vocabulary the user already
   knows (from the deck), each engineered to *force* the target distinction/construction.
3. Present one at a time; the user translates; **grade** (right / close / off) with a
   **contrastive explanation** aimed at the distinction (e.g. case frames), not just the word.
4. Feed persistent misses back into `docs/exercise_targets.md`.

Worked example (real drill): "liking" splits by **case frame** — `beğenmek` takes an
accusative object (`X-i beğendim`), `hoşuna gitmek` makes X the subject (`X hoşuma gitti`),
`sevinmek` takes the dative (`X-e sevindim`).

## In-app notes

The quiz has a "+ Note on this word" box; notes are filed as GitHub issues (label
`vocab-comment`, title `[note] …`). To review: `python3 scripts/fetch_comments.py` (public,
no auth). Act on each, then close the issue with the token in `resources/github_token.txt`
(gitignored). Multi-form flags typically mean "add `hint_en_tr` `(X / Y)`".
