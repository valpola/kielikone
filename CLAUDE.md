# kielikone — project notes

Personal Turkish vocabulary quiz (static site on GitHub Pages: `valpola.github.io/kielikone`).
Deck source is `data/candidates/*.candidates.json`; the pipeline rebuilds `web/data/quiz.json`
(`rebuild_reviewed.py` → `dedupe_vocab.py --apply` → `validate_tags.py` → `export_quiz.py`,
i.e. `make build`; then `make test`, whose `test_deck_invariants.py` enforces the content
rules below — unit-level tags, no colliding prompts, hints that do not leak the answer).
The study batch is **not** part of that pipeline: each device computes it locally from the
live history, and `export_quiz.py` strips the tag (`SESSION_TAG`) from every exported item,
so a shipped batch can never override what the device worked out. `build_today.py` remains
for offline scoring analysis. On each deploy bump `cacheBust` in `web/config.js`
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

**The course is cached locally — do not re-download it.** `resources/turkishle_cache/`
(gitignored) holds every widget and what has been parsed out of it:
`lessons.json` (416 lessons across A1/A2/B1, with unit codes and widget ids),
`embeds/<id>.html` (all 590 raw embeds, 30 MB), `cards.json`, `prose.json`.
`python3 scripts/fetch_turkishle.py` fetches only what is missing; `--parse` re-parses
without fetching. Only the *lesson map* needs the login; embeds are public by id.
- **A card is a bilingual pair, not just a headword.** `<strong>` is the headword, each
  `<em>` an example line, and the two sides run in parallel — so `cards.json` carries
  `{headword, meaning, sentences:[{tr,en}]}`. 1120 cards, **1062 sentence pairs**. Earlier
  sweeps took the headword and discarded the sentence, which is where the usage lives.
- Match Dialogcards **on shape, not on `library`**: for these widgets `jsonContent` *is* the
  dialogcards object, and the library name sits in `H5PIntegration.contents[key]`. Keying on
  `library` finds four cards out of 1120.
- B1 lesson titles carry no `1A`-style code; its modules are positional, each opening with a
  `📕 Kelime Listesi & Kartları` page, so number them in curriculum order (`B1-M1`…`B1-M5`).

- **`🎧 Dinleme` carries no vocabulary list** (verified across all A1+A2 listening lessons):
  - A1 1A–3B are **`turkishle.github.io/turkishle-lessons/lessons/<unit>-listening/lesson.html`**
    (public, inline `application/json`) — comprehension primitives only
    (`minimal-pair`, `fill-blank-transcript`, `true-false`, `attribution-table`…).
    `options[].gloss` are whole-sentence translations; vignette `words[]` are audio timings.
    Only `rows[].{label,gloss}` are real word pairs (2C's adjectives — already in the deck).
  - A1-3C onward and all A2 listening are H5P `InteractiveBook`s whose
    "kelimeleri anlamlarıyla eşleştir" exercises **reuse the unit's own vocab list**.
  So the web gap source is the **`📰 Okuma` SÖZLÜK**, not Dinleme.

**3. The prior app (reference only)** — the subscription course the user studied before
switching to Turkishle. `resources/prior_app_cache/` (gitignored) holds its material: 2193
learned items dumped 2026-08-05, plus the subsets absent from the deck. **Nothing from it has
been added**; it is a coverage reference to review by hand. Its glosses contain errors
(`sempatik` = "sympathetic", a false friend) and much of it is off-syllabus thematic vocabulary,
so treat every item as a candidate. See the README there for how the extraction works — and note
that one pass silently dropped 10 items while a second at a different page size recovered them,
so **scan twice and merge**. Never change the learning language in its UI: that has erased this
history before.

`lessons.json` there is the **whole course catalogue, 580 rows / 565 distinct lessons** (not the
271 of the learning plan), read from `localStorage[…:curriculum]`. Take the lesson id from
`component.data.contentId` — `component.id` is the *component* id and every URL built from it
404s. Rows exceed distinct lessons because a lesson can be listed in two paths, and ten
Words-and-Sentences lessons appear both in the intro unit and in their thematic unit. For those
271 rows `data.topics` *is* the vocabulary in English, so the catalogue is a coverage check by
itself: **89 of those lessons are wholly untouched** (339 glosses never offered for review),
worst in Society, Feelings and Attitudes, Life.

**Harvest by opening lessons, not by playing them.** Merely loading a lesson caches its whole
payload in IndexedDB (`learner-activity` → `sessions` → `sessionData.trainers[].item_groups[]
.items[]`), each item carrying `learn_language_text` (Turkish, focus word in `((…))`),
`display_language_text` and a `sound.id`. So harvesting is *navigate, wait, read* — no answering
and **no change to account state**. Two things that do *not* work: the one-request-per-lesson
content API is AWS SigV4-signed, and the UI's `To next trainer` button exists *only* in lessons
already completed, so clicking through an unseen lesson is impossible without answering every
exercise. Audio: the CDN path `/v1.0.0/sounds/<id>/normal.mp3` is public, but the id is the
item's `sound.id`, never the vocabulary row id (that 403s). macOS also ships a Turkish TTS
voice, `say -v Yelda`, which covers the whole deck rather than just that app's words.

`completion.json` is the pre-change snapshot (2026-08-05): **452/580 lessons completed**, all of
A1/A2/Grammar/Specials plus 143 of the 271 Words-and-Sentences rows, each named with its id.
Nothing is partially complete — the plan renders only `Redo lesson` / `Start lesson`. Opening
lessons does not alter this; verified after the sweep, the reported percentage was unchanged to
twelve decimals.

**The whole course is extracted** (all 565 distinct lessons, 2026-08-05). Raw payloads in
`lessons_raw/`, and `scripts/parse_prior_app_lessons.py` renders `coursebook.md` (every
explanation, 9790 lines), `grammar_index.md` (583 explanation cards), `lesson_vocabulary.json`
(10964 items with sound ids) and `uncarded_words.json` (1795 headwords). **60% of the words and
94% of the dialogue sentences never become review cards**, which is the concrete reason that app
was hard to study from. All the grammar sits in A1/A2/Grammar/Specials — the 261 distinct
Words-and-Sentences lessons added no explanation cards at all. When capturing, batch the
navigations but **attribute records by their `createdAt`, never by `getAll()` order** — the store
is keyed on a random uuid, and position-based attribution put 166 of 175 lessons on the wrong
record, undetectably.

**Its material is reference only and must stay out of the repo.** `resources/` is gitignored;
keep the corpus there and keep the vendor's name out of tracked files and commit messages.

## Pronunciation (`pron_tr`)

Turkish spelling hides three things, none of them derivable, so they are stored per word in
`pron_tr` and the word is tagged **`pronunciation`** so the set can be quizzed on its own.
`export_quiz.py` carries the field; the app shows it **only after reveal**, so it can never hand
over a Turkish spelling in EN→TR.

- **Vowel length** in Arabic/Persian loans (`merkezî` → `meɾceˈziː`), which is also what the few
  circumflexes in the deck record.
- **Palatalised `k`/`g`** before front vowels — `[c]`/`[ɟ]`, not `[k]`/`[ɡ]`: `kedi` → `ceˈdi`,
  `rüzgâr` → `ɾyzˈɟɑɾ`.
- **Stress**, where it is not final: `birçok` → `ˈbiɾtʃok`.
- **The two `e` qualities** (the learner's observation, and it matches the standard rule): a
  closed syllable gives the open `[æ]`, an open syllable the close `[e]` — `ben` → `bæn`,
  `ders` → `dæɾs` against `kedi` → `ceˈdi`. `merkezî` has both, `mæɾceˈziː`.
- Also **`[l]` vs `[ɫ]`**, clear next to front vowels and dark next to back ones.

**Coverage:** every A2-5 entry carries `pron_tr`; earlier units have it only on a handful of
worked examples. The **`pronunciation` tag is not on everything** — it marks the words that defy
their spelling (irregular stress, phonemic length, a `ğ` that lengthens rather than sounds), so
the tag stays a useful filter rather than a synonym for "has a transcription".

**Leave the field empty rather than guess.** A wrong transcription teaches something false with
the same confidence as a right one, so an absent `pron_tr` is strictly better than an inferred
one. In particular **`ğ` is not transcribed unless it has been checked by ear**: its effect
varies word by word — lengthening the preceding vowel, reducing to a glide, or disappearing —
and the context (intervocalic vs before a consonant) does not settle it. Applying one rule across
those contexts produced `boˈɑː` for `boğa`, which the learner heard as `boːˈɑ`; five other `ğ`
words were then dropped rather than kept on the same reasoning. `scripts/make_pron_audio.py`
generates audio per word, which is how a transcription gets verified before it goes in.

**This is hand work, word by word — do not try to generate it.** TDK
(`sozluk.gov.tr/gts?ara=<word>`, needs a browser User-Agent or `curl`) is useful only as
*triage*: it returns a `telaffuz` field for irregular words and nothing for regular ones (~29% of
single-word entries), giving length and stress plus a prose note on `l`. It does **not** give the
vowel allophony or the k/g palatalisation, which is most of the value. Its notation is also not
IPA — the apostrophe follows the stressed *vowel* (`sine'ma`, `a'nkara`) where IPA's `ˈ` precedes
the *syllable* — so it must be converted, not copied. That reading of the convention is inferred
from examples, not documentation; native audio in `resources/pron_samples/` was sent to the
learner to confirm it.

**Curation rules**
- **Compare on letters only.** Strip case, circumflexes, parentheses, spaces *and
  punctuation* before matching. Three duplicates got in this way, each defeated by one
  character the fold did not remove: `yıl dönümü` (a space), `… sayesinde` (an ellipsis),
  `Lütfen!` (an exclamation mark). Also split slash forms and check each side: `yüksek
  lisans yapmak` was hidden inside a combined entry.
- **A form already in the deck does not mean the *sense* is.** Presence tests match spellings, so a homograph reads as covered: `aslan` (lion → Leo), `balık` (fish → Pisces) and `madde` (item → substance) were all filtered out as "already present" until the A2-5 candidates were re-checked gloss by gloss. After any diff, list the forms it called present and compare the two glosses.
- **Dedup by individual word, then review by hand** (the user's explicit preference —
  automated verdicts have been wrong twice). For each candidate, search every
  `data/candidates/*.candidates.json` entry containing *any* word of the candidate
  (stem-folded) and eyeball the matches. Never trust a bare exact/boundary regex: a
  stem + right-word-boundary test wrongly reported `karar vermek` absent when the deck had
  `(bir şeye) karar vermek`. Never dedup against `web/data/quiz.json` (hides aliased-away
  entries). Be morphology-aware: object frames `(bir şeye) binmek`, softening `ayak→ayağa`,
  vowel drop `ağız→ağzı`.
- **Grammar words belong in the deck.** This is for learning Turkish, not only its nouns, so
  pronouns, particles, postpositions and case forms are content, not noise to filter out.
  Two mistakes came from forgetting this: `yoksa` was deleted as a duplicate of `veya / ya da`
  when the pair is exactly Finnish `vai` / `tai`, and a whole sweep of pronoun forms was
  discarded as "grammar", which is how the deck came to hold `ben` and `sen` but not `o`,
  `biz`, `siz` or `onlar`. When a shared English gloss makes two entries look redundant, first
  ask whether Turkish is drawing a distinction English has lost.
- **Store a grammar feature as a use case, not a bare gloss.** An isolated `beri` teaches
  nothing; `sabahtan beri` = "since this morning" shows the suffix working. The deck already
  did this for `-DIr` (`günlerdir`, `yıllardır`) and `-(y)ken` (`küçükken`) — follow that.
  `docs/grammar_topics.md` lists the constructions per unit; check each has at least one
  entry showing it in use. Pure conjugation patterns (`-Iyordu`, `-mAlIydI`) stay out — those
  belong in the interactive drills.
  - Where the construction has a **trap**, the card should be a full sentence that springs it,
    not the pattern: `Ne kahve ne de çay istiyorum.` teaches that Turkish keeps the verb
    affirmative, which `ne … ne de` = "neither … nor" cannot. A drill can come later; a card
    is the start.
  - Keep the **vocabulary in such a sentence deliberately plain** — words long since learned —
    so the attention falls on the grammar and not on decoding the example.
- **Level cap: up to B1, not beyond.** Reading glossaries sometimes gloss words needed only
  to understand that particular text (literary collocations, specialist terms). Skip those
  and say so, rather than padding the deck (e.g. skipped `aşkla dolmak`).
- Don't add words from **unswept units** just because a listening page mentions them —
  defer them with the unit (e.g. `minibüs`, `yönetmen` belong to A2-4).
- **Do not skip "transparent" or cognate words** — this was an early mistake. What looks
  obvious to a reader is not obvious to the learner until practised, so include cognates
  (`pop`, `mikrofon`, `klasik müzik`) and compositional compounds (`çay bahçesi`,
  `saat kulesi`) alike. If a set should be *deprioritised* rather than omitted, that is what
  the **`similar`** tag is for (the user filters it out; ~118 country names use it) — but
  apply it only when asked, since an excluded tag hides the word from their practice set.
- **Record the decision in `notes`**, not just the source: which sources were consulted, why
  this gloss, why a candidate was dropped. `source` says where a word came from; `notes` says
  why the entry looks the way it does, so the call can be audited later instead of re-derived.
- **Check both sources before deciding.** The coursebook list and the web card can differ —
  one may carry two forms where the other carries one, or gloss the same word differently.
  A card's subunit loses to a coursebook list's when they disagree.
- **A second English word in a gloss is not free**: a slash gloss requires typing *every*
  part for TR→EN. If a word has a secondary translation, put it in a hint or leave it out —
  do not silently widen what the learner must produce (this was my error on `süresince`).
- `source` must be **per item** and truthful: `Turkishle coursebook (A1/A2/B1)`,
  `A1-6 reading exercise SÖZLÜK (Turkishle web)`, or `gap-fill: standard vocabulary…`.
- Off-syllabus adds get the coarse level + an extra tag (`unit-a1` + `unit-a1-extra`),
  never a definite subunit. New tags must be added to `data/tags.json` or the export aborts.
- **Every item wants a unit-*level* marker**, so the deck can be filtered by where a word
  came from. A bare `unit-a1`/`unit-a2` is never the finished state — it means the source
  wasn't traced. In order of preference: a **subunit** (`unit-a2-4b`); a **source-set tag**
  when the source is a real list with no subunit (`unit-a1-cases` = the A1 Cases & Verbs
  cross-unit supplement); or the **`-extra`** marker for genuinely off-syllabus words.
  - **Base words of compounds are not off-syllabus.** Take the subunit of the earliest
    compound they occur in and say so in `source`: `base word of “gitar teli” (A2-4B)`.
    Match morphology-aware — plurals (`ürünler`) and possessives (`teli`) both hide the stem.
  - **`-extra` is not a subunit** and must never stand in for one — the two are orthogonal:
    the subunit says *where it belongs in the syllabus*, `-extra` says *it isn't from the
    book*. Every item gets a subunit; gap-fills get a subunit **and** `-extra`.
    - In the books, in the **taught sense** → subunit of first occurrence, no `-extra`;
      `source` says whether it was a vocabulary list or a dialogue (`birkaç` → `unit-a2-6a`,
      "A2-6A coursebook dialogue (not in any unit vocabulary list)").
    - Absent, or present only **in another sense** → the subunit whose list owns that topic,
      plus `-extra`, with `source` naming the group and the reason: `fırtına` → `unit-a2-5a`
      ("filed with the A2-5A weather list"); `kapalı` → `unit-a1-6a`, since only the place
      name *Kapalı Çarşı* occurs; `sağ` → `unit-a2-1a`, since only *sağ ol* (thanks) occurs.
    - Find the owning subunit by looking up **peer words**, not the word itself: clothing →
      A2-1B, professions → A2-3B, weather → A2-5A, family → A1-4A, animals → A2-2B,
      countries/languages → A1-4B, relative directions → A2-1A (`yol tarifi`), numbers and
      arithmetic → A1-2B, greetings/politeness → A1-1A.

**Locating a word's subunit** — build the 36 vocabulary lists, then match against them:
- The **per-subunit PDFs are pure vocabulary lists** (title, `KELİME LİSTESİ`, POS-grouped
  rows — no prose), covering A1-0A…6C and A2-1A…2B. A hit there *is* attestation.
- A2-2C…6C exist only in the master coursebook, whose body holds exactly **18
  `KELİME LİSTESİ` blocks in unit order** (1A…6C) — zip them to that order rather than
  trusting `^[1-6][ABC]` section marks, which are off by one in several places. Take rows
  forward from each heading while lines stay row-like (≤46 chars, no `: ; ? !`, no trailing
  `.`/`)`), stopping after 3 consecutive prose lines.
- Match **morphology-aware**, or attested words read as missing: final-consonant softening
  (`kâğıt`→`kağıdı`, so search `kağı[td]`), plurals (`ürünler`), possessives (`teli`). Bound
  the match on **both** sides — an open right edge makes `göre` match `görev` and `kar` match
  `kardeş`. A base word often has no row of its own while its derivative does (`yağmur` vs
  `yağmurlu` in A2-5A) — that still fixes the subunit.
- `pdftotext` renders **`İ` as a dotless `ı` plus a combining dot, sometimes with a space**,
  so `İŞÇİ` arrives as `ı̇ şçi` and never matches `işçi`. Strip `U+0307`, close the gap, and
  fold `ı→i` before comparing. Note `.lower()` *expands* `İ` into `i`+dot, so repair after
  lowercasing, not before.
- **A list row offering two forms (`süresinde / süresince`, `tecrübe / deneyim`) must keep
  both**, as `X / Y` with `hint_en_tr: (X / Y)`. Recording only one silently drops a word the
  book teaches. To audit: split every list row on ` / ` and check both sides against the deck.
- Glosses carry no parentheticals; disambiguators/format cues go in `hint_tr_en` (TR→EN) or
  `hint_en_tr` (EN→TR). Multi-form answers get `(X / Y)`. Keep circumflexes (`kâğıt`,
  `tarihî`) — matching folds `â/î/û`.
- **If the English verb reads either way, the tip must say which** — `(transitive)` or
  `(intransitive)`. A Turkish verb is nearly always one or the other, and knowing which is
  what lets the counterpart be derived: the `-Il-`/`-In-` form for the intransitive of a
  transitive verb, the causative for the transitive of an intransitive one. So `yaymak` =
  "to spread `(transitive)`" also teaches `yayılmak`, without a second entry. Skip phrases
  that already carry their object (`hamur açmak`, `okula başlamak`) — those are unambiguous.
- **Never pack two unrelated meanings into one gloss.** The user mostly drills EN→TR, so a
  gloss listing a second sense does not teach it — make it a **separate entry** and give the
  TR→EN hint to say which sense is meant (e.g. `madde` = "item" `(e.g. an entry in a
  document)`; "substance" would be its own entry). Slash forms are only for genuine
  **synonyms** (`hep birlikte / hep beraber`), never for distinct senses.
- **`hint_en_tr` must not contain Turkish words** — the answer is Turkish, so that leaks.
  (`hint_tr_en` may be Turkish: there the answer is English.)

**Status:** A1 (0A + units 1–6) and A2 units 1–5 fully swept (coursebook + web, incl. the
listening re-check). A2-6 onward not yet. B1.1 not yet.

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
