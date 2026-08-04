# Turkish Vocab Quiz

A personal Turkish vocabulary quiz. Open it in any browser, on the phone or the desktop:

**https://valpola.github.io/kielikone/**

Everything below is about *using* the quiz. If you want to know how it is built, or you
intend to change it, see [docs/developer.md](docs/developer.md).

## Answering a question

The card shows a word — Turkish or English, depending on the direction — and you type the
translation. Press Enter to reveal the answer, then Enter again to grade yourself, or use
the "I was correct" / "I was incorrect" buttons.

Typing an answer is optional: you can reveal it and grade honestly from memory.

Some answers accept more than one form. A tip like `(X / Y)` means both forms are wanted,
in either order — `hep birlikte / hep beraber`. Where a Turkish verb is shown with an object
frame, such as `(birine) teşekkür etmek`, the frame is part of the answer: the `sb.` or
`sth.` in the English gloss is the signal that you are expected to know the case too.

### Shortcuts

| Key | Action |
| --- | --- |
| Enter | Reveal the answer, or grade it once revealed |
| f | I was correct (after reveal) |
| j | I was incorrect (after reveal) |
| n | Next word (after reveal) |
| Tab | Next word (any time) |

## Logging in

Results are only recorded once you log in. The button in the corner shows who you are; if it
says "Login to record results", press it and enter your app secret. It is stored on the
device, so you do this once per browser.

Without logging in the quiz still works — it just does not save anything.

## The practice set

"Recompute practice set" picks the words most worth practising next, based on how you have
answered them before: words you get wrong come back sooner, words you get right recede, and
words you have never seen get a nudge so they surface at all.

The set is worked out **on this device**, from your full history, and stored here. It does
not travel with the vocabulary and does not affect your other devices. "Words per practice
set" controls how many are picked — around ten works well, so you can take a break between
batches.

Recomputing also resets the "correct to finish" counters for the session.

## Filtering what you are asked

Two lists in Options control which words can come up:

- **Include tags** — a word must have **all** of them.
- **Exclude tags** — a word must have **none** of them.

Because Include is an "all", ticking two units asks for words belonging to *both*, which is
usually nothing at all. If the quiz says nothing matches, that is almost always why.

Ticked tags are listed first under **Selected**, so you can see at a glance what is filtering
your practice, and the number beside each tag is how many words carry it. A tag showing `0`
can never match.

Most words are tagged with the coursebook unit they come from, so you can revise a single
unit — `Unit A2-5A` for the weather words, say. Tags marked *(extra / off-syllabus)* are
words added to fill a gap rather than taken from the books.

## Session target

"Correct to finish" sets how many times you must get a word right before it stops coming up
for the rest of the session. It resets when you reload or recompute the practice set.

## Notes on a word

If a gloss looks wrong, a tip is misleading, or two words seem to collide, open
"+ Note on this word" and write it down. The note is filed against that exact word and can
be acted on later. This is the best way to flag a problem — it captures which word you were
looking at and in which direction.

## Syncing, and being offline

Answers are saved to the server as you go. If the connection is poor they queue up on the
device and go out later; "Pending sync: n" in the corner tells you how many are waiting.
Nothing is lost — you can keep quizzing offline and the queue drains when you are back.

Under Options, below the quiz controls:

- **Undo last answer** — removes the most recent answer, for when you fat-finger a grade.
- **Retry sync now** — pushes the queue immediately instead of waiting.
- **Discard pending** — throws the queue away. Only if it is stuck and you do not care.
- **Purge cached history** — drops the local copy of your history and re-reads it.

Recomputing works offline too, from the cached history; it will say so when it does.

## If something looks stale

The app caches its files. A reload usually fixes it. If the vocabulary looks out of date
after an update, reload once more — the deck is fetched fresh on each load, but the browser
can hold on to the page itself.
