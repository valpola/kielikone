# kielikone — project notes

Personal Turkish vocabulary quiz (static site on GitHub Pages: `valpola.github.io/kielikone`).
Deck source is `data/candidates/*.candidates.json`; the pipeline rebuilds `web/data/quiz.json`
(`rebuild_reviewed.py` → `dedupe_vocab.py --apply` → `build_today.py --limit 30` →
`validate_tags.py` → `export_quiz.py`). On each deploy bump `cacheBust` in `web/config.js`
and the `?v=` in `web/index.html`, then commit + push (GitHub Pages serves `main`).

## Vocabulary extraction (unit sweeps)

Two sources per unit; **check both**, and *all* page types — a coursebook-only or
reading-only pass misses a lot (see "page types" below).

**1. Coursebook PDFs** — `resources/originals/` (gitignored); extract to text in the
scratchpad once per session, then:
- Diff the unit's **`Kelime / Anlamı`** vocab tables against the deck.
- Also **token-diff the grammar sections / dialogues / listening transcripts**: keep only
  tokens containing `çğıöşü` (drops English), then filter out grammar jargon, H5P/UI
  boilerplate, **capitalized proper nouns**, and inflections (a token is "covered" if any
  deck word is a prefix of it or vice versa). What survives is a short reviewable list.
- Distinguish real dialogue vocab (worth adding, e.g. `emlak`, `emlakçı`) from mere
  **suffix-demo words** in a derivation section (usually skip, e.g. `görgüsüz`, `ömürlük`).

**2. Turkishle web course** (login-gated Kajabi + public-by-URL H5P widgets):
- Lesson map: in a logged-in in-app browser tab **on `courses.turkishle.com`**, same-origin
  `fetch(productUrl, {credentials:'include'})` → any `/categories/N/posts/M` URL → fetch that
  post and parse the **curriculum sidebar** (`a[href*="/posts/"]`) for every lesson title+URL.
  The product page itself is a JS shell (no links in raw HTML) and may refuse to render.
- Per lesson page, harvest widget ids with `/h5p\.com\/content\/(\d+)/`.
- Then **curl the embeds** (no auth): `https://turkishle.h5p.com/content/<id>/embed`.
  Parse: find `H5PIntegration = `, `json.JSONDecoder().raw_decode(...)`, take
  `contents[firstKey].jsonContent` (a JSON *string* → parse again), then walk it:
  - `H5P.AdvancedText` `params.text` → prose; the **`SÖZLÜK`** block is the curated glossary.
  - `H5P.Dialogcards` `dialogs[].{text,answer}` → vocab flashcard pairs (front often
    "Headword Example sentence").
- **Page types per subunit:** `📝 Kelime Listesi` (flashcards — main vocab), `📰 Okuma`
  (reading — has `SÖZLÜK`; often the richest gap source), `🎧 Dinleme` (no `SÖZLÜK`;
  transcripts are in the coursebook), `📹 Gerçek Hayat` (video dialogue), grammar videos.
  Other exercise widgets are UI boilerplate (`doğru`, `çözümü`, `alıştırma`, `başlat`…).
- zsh: build curl loops with an **array** (`IDS=(a b c); for id in $IDS`) — unquoted `$IDS`
  does not word-split.

**Curation rules**
- Dedup by **stem against `data/candidates/*.candidates.json`**, never against
  `web/data/quiz.json` (which hides aliased-away entries). Be morphology-aware: object
  frames `(bir şeye) binmek`, softening `ayak→ayağa`, vowel drop `ağız→ağzı`.
- Skip **transparent** compounds (`çay bahçesi`, `saat kulesi`); keep **non-transparent**
  ones (`hamur işi` = pastries, not "dough work").
- `source` must be **per item** and truthful: `Turkishle coursebook (A1/A2/B1)`,
  `A1-6 reading exercise SÖZLÜK (Turkishle web)`, or `gap-fill: standard vocabulary…`.
- Off-syllabus adds get the coarse level + an extra tag (`unit-a1` + `unit-a1-extra`),
  never a definite subunit. New tags must be added to `data/tags.json` or the export aborts.
- Glosses carry no parentheticals; disambiguators/format cues go in `hint_tr_en` (TR→EN) or
  `hint_en_tr` (EN→TR). Multi-form answers get `(X / Y)`. Keep circumflexes (`kâğıt`,
  `tarihî`) — matching folds `â/î/û`.

**Status:** A1 (0A + units 1–6) and A2 units 1–2 fully swept. A2-3 onward not yet.

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
