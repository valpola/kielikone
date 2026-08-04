#!/usr/bin/env node

// Covers web/answers.js — the code that decides whether an answer was right.
// A regression here misgrades every session afterwards and is invisible until
// the history is already wrong, so the rules are pinned explicitly.

const path = require("path");
const assert = require("assert");
const A = require(path.resolve(__dirname, "..", "..", "web", "answers.js"));

let checks = 0;
const ok = (given, expected, why) => {
  assert.ok(A.matches(given, expected), `expected a match (${why}): ${given} vs ${expected}`);
  checks += 1;
};
const no = (given, expected, why) => {
  assert.ok(!A.matches(given, expected), `expected NO match (${why}): ${given} vs ${expected}`);
  checks += 1;
};

// --- basics -------------------------------------------------------------
ok("kitap", "kitap", "identical");
ok("  kitap  ", "kitap", "surrounding whitespace");
no("kitap", "kalem", "different words");
no("", "kitap", "empty answer is never right");

// --- Turkish casing -----------------------------------------------------
// tr-TR lowercasing: I -> ı and İ -> i. Getting this wrong marks "İSTANBUL"
// against "istanbul" as incorrect.
ok("İSTANBUL", "İstanbul", "dotted capital I lowercases to i");
ok("ISPANAK", "ıspanak", "dotless capital I lowercases to ı");
ok("Kitap", "kitap", "ordinary capitalisation");

// --- circumflexes are optional -----------------------------------------
// The deck keeps them as a pronunciation cue, but nobody should have to type ^.
ok("kağıt", "kâğıt", "â accepted as a");
ok("kâğıt", "kağıt", "either side may carry the circumflex");
ok("tarihi", "tarihî", "î accepted as i");
ok("rüzgar", "rüzgâr", "â inside a word");
ok("usul", "usûl", "û accepted as u");
// Only the circumflexes fold. The Turkish letters themselves are distinct, so a
// learner typing g for ğ or i for ı is still wrong — that is the point of drilling.
no("kagıt", "kâğıt", "ğ does not fold to g");
no("kagit", "kagıt", "ı and i are different letters");

// --- punctuation and object frames --------------------------------------
// Brackets, spaces and terminal punctuation are dropped, so the frame can be
// typed with or without them — but the frame words are still required, which is
// what the sb./sth. in the gloss is telling you.
ok("(birine) teşekkür etmek", "birine teşekkür etmek", "brackets are noise");
ok("birineteşekküretmek", "(birine) teşekkür etmek", "spaces are noise");
no("teşekkür etmek", "(birine) teşekkür etmek", "the frame is part of the answer");
ok("Merhaba!", "merhaba", "trailing punctuation");
ok("evet, tabii", "evet tabii", "commas");

// --- slash alternatives -------------------------------------------------
// "(X / Y)" means both forms, in any order.
ok("hep birlikte / hep beraber", "hep beraber / hep birlikte", "order does not matter");
ok("hep birlikte/hep beraber", "hep birlikte / hep beraber", "spacing around the slash");
no("hep birlikte", "hep birlikte / hep beraber", "one of two is not enough");
no("hep birlikte / yanlış", "hep birlikte / hep beraber", "a wrong alternative fails");
ok("a / b / c", "c / a / b", "three alternatives, any order");
ok("kitap //  kalem", "kalem / kitap", "empty segments are ignored");

// --- normalize/normalizeSet directly ------------------------------------
assert.strictEqual(A.normalizeAnswer("(Bir Şeyi) Almak!"), "birşeyialmak");
assert.strictEqual(A.normalizeAnswerSet("b / a"), A.normalizeAnswerSet("a / b"));
assert.strictEqual(A.normalizeAnswer(null), "", "null is empty, not a crash");
assert.strictEqual(A.normalizeAnswer(undefined), "", "undefined is empty");
checks += 4;

console.log(`Answer matching test passed (${checks} checks).`);
