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

- **`🎧 Dinleme` carries no vocabulary list** (verified across all A1+A2 listening lessons):
  - A1 1A–3B are **`turkishle.github.io/turkishle-lessons/lessons/<unit>-listening/lesson.html`**
    (public, inline `application/json`) — comprehension primitives only
    (`minimal-pair`, `fill-blank-transcript`, `true-false`, `attribution-table`…).
    `options[].gloss` are whole-sentence translations; vignette `words[]` are audio timings.
    Only `rows[].{label,gloss}` are real word pairs (2C's adjectives — already in the deck).
  - A1-3C onward and all A2 listening are H5P `InteractiveBook`s whose
    "kelimeleri anlamlarıyla eşleştir" exercises **reuse the unit's own vocab list**.
  So the web gap source is the **`📰 Okuma` SÖZLÜK**, not Dinleme.

**Curation rules**
- **Dedup by individual word, then review by hand** (the user's explicit preference —
  automated verdicts have been wrong twice). For each candidate, search every
  `data/candidates/*.candidates.json` entry containing *any* word of the candidate
  (stem-folded) and eyeball the matches. Never trust a bare exact/boundary regex: a
  stem + right-word-boundary test wrongly reported `karar vermek` absent when the deck had
  `(bir şeye) karar vermek`. Never dedup against `web/data/quiz.json` (hides aliased-away
  entries). Be morphology-aware: object frames `(bir şeye) binmek`, softening `ayak→ayağa`,
  vowel drop `ağız→ağzı`.
- **Level cap: up to B1, not beyond.** Reading glossaries sometimes gloss words needed only
  to understand that particular text (literary collocations, specialist terms). Skip those
  and say so, rather than padding the deck (e.g. skipped `aşkla dolmak`).
- Don't add words from **unswept units** just because a listening page mentions them —
  defer them with the unit (e.g. `minibüs`, `yönetmen` belong to A2-4).
- Skip **transparent** compounds (`çay bahçesi`, `saat kulesi`); keep **non-transparent**
  ones (`hamur işi` = pastries, not "dough work").
- `source` must be **per item** and truthful: `Turkishle coursebook (A1/A2/B1)`,
  `A1-6 reading exercise SÖZLÜK (Turkishle web)`, or `gap-fill: standard vocabulary…`.
- Off-syllabus adds get the coarse level + an extra tag (`unit-a1` + `unit-a1-extra`),
  never a definite subunit. New tags must be added to `data/tags.json` or the export aborts.
- Glosses carry no parentheticals; disambiguators/format cues go in `hint_tr_en` (TR→EN) or
  `hint_en_tr` (EN→TR). Multi-form answers get `(X / Y)`. Keep circumflexes (`kâğıt`,
  `tarihî`) — matching folds `â/î/û`.
- **Never pack two unrelated meanings into one gloss.** The user mostly drills EN→TR, so a
  gloss listing a second sense does not teach it — make it a **separate entry** and give the
  TR→EN hint to say which sense is meant (e.g. `madde` = "item" `(e.g. an entry in a
  document)`; "substance" would be its own entry). Slash forms are only for genuine
  **synonyms** (`hep birlikte / hep beraber`), never for distinct senses.
- **`hint_en_tr` must not contain Turkish words** — the answer is Turkish, so that leaks.
  (`hint_tr_en` may be Turkish: there the answer is English.)

**Status:** A1 (0A + units 1–6) and A2 units 1–4 fully swept (coursebook + web, incl. the
listening re-check). A2-5 onward not yet. B1.1 not yet.

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
