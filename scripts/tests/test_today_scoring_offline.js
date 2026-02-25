#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const assert = require("assert");
const TodayScoring = require(path.resolve(__dirname, "..", "..", "web", "today_scoring.js"));

const fixtureDir = path.resolve(__dirname, "fixtures");
const resultsCsv = fs.readFileSync(path.join(fixtureDir, "results.csv"), "utf8");
const quiz = JSON.parse(fs.readFileSync(path.join(fixtureDir, "quiz.json"), "utf8"));
const aliases = JSON.parse(fs.readFileSync(path.join(fixtureDir, "aliases.json"), "utf8"));
const expected = JSON.parse(fs.readFileSync(path.join(fixtureDir, "expected.json"), "utf8"));

const rows = TodayScoring.parseCsv(resultsCsv);
assert.strictEqual(rows.length, expected.rows_count, "rows count mismatch");

const events = TodayScoring.eventStream(rows, aliases.aliases || {});
assert.strictEqual(events.length, expected.events_count, "events count mismatch");

const eventsByKey = TodayScoring.buildEventsByKey(events);
const now = new Date(expected.now);

const scored = TodayScoring.scoreItems(quiz.items, eventsByKey, {
  mode: expected.mode,
  now,
  aliases: aliases.aliases || {},
});

const scores = {};
scored.forEach((entry) => {
  scores[entry.id] = entry.score;
});

const tolerance = expected.tolerance || 1e-4;
Object.keys(expected.scores).forEach((wordId) => {
  assert.ok(wordId in scores, `missing score for ${wordId}`);
  const delta = Math.abs(scores[wordId] - expected.scores[wordId]);
  assert.ok(delta <= tolerance, `score mismatch for ${wordId}: ${delta}`);
});

const topIds = TodayScoring.selectTopN(scored, expected.limit);
assert.deepStrictEqual(topIds, expected.top_ids, "top ids mismatch");

console.log("Offline today scoring tests passed.");
