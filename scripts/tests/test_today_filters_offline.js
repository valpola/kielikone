#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const assert = require("assert");
const TodayScoring = require(path.resolve(__dirname, "..", "..", "web", "today_scoring.js"));

const fixtureDir = path.resolve(__dirname, "fixtures");
const resultsCsv = fs.readFileSync(path.join(fixtureDir, "filters_results.csv"), "utf8");
const quiz = JSON.parse(fs.readFileSync(path.join(fixtureDir, "filters_quiz.json"), "utf8"));
const expected = JSON.parse(fs.readFileSync(path.join(fixtureDir, "filters_expected.json"), "utf8"));

const rows = TodayScoring.parseCsv(resultsCsv);
const events = TodayScoring.eventStream(rows, {});
const eventsByKey = TodayScoring.buildEventsByKey(events);
const now = new Date(expected.now);

expected.cases.forEach((testCase) => {
  const include = new Set(testCase.include_tags || []);
  const exclude = new Set(testCase.exclude_tags || []);

  const filtered = TodayScoring.filterItems(quiz.items, include, exclude);
  const scored = TodayScoring.scoreItems(filtered, eventsByKey, {
    mode: testCase.mode,
    now,
    aliases: {},
  });

  const topIds = TodayScoring.selectTopN(scored, testCase.limit);
  assert.deepStrictEqual(topIds, testCase.top_ids, `${testCase.name}: top ids mismatch`);

  topIds.forEach((id) => {
    assert.ok(
      filtered.some((item) => item.id === id),
      `${testCase.name}: top id ${id} is not in filtered items`
    );
  });
});

console.log("Today filter recompute tests passed.");
