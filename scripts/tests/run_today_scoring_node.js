#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const TodayScoring = require(path.resolve(__dirname, "..", "..", "web", "today_scoring.js"));

const inputPath = process.argv[2];
if (!inputPath) {
  console.error("Usage: run_today_scoring_node.js <input.json>");
  process.exit(2);
}

const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const csvText = input.csvText || "";
const rows = TodayScoring.parseCsv(csvText);
const events = TodayScoring.eventStream(rows, input.aliases || {});
const eventsByKey = TodayScoring.buildEventsByKey(events);

const includeTags = new Set(input.includeTags || []);
const excludeTags = new Set(input.excludeTags || []);
const quizItems = input.quizItems || [];
const filtered = TodayScoring.filterItems(quizItems, includeTags, excludeTags);

const scored = TodayScoring.scoreItems(filtered, eventsByKey, {
  mode: input.mode || "en-tr",
  now: input.now ? new Date(input.now) : new Date(),
  config: input.config,
});

const topIds = TodayScoring.selectTopN(scored, input.limit || 30);
const scores = {};
scored.forEach((entry) => {
  scores[entry.id] = entry.score;
});

const output = {
  rowsCount: rows.length,
  eventsCount: events.length,
  filteredIds: filtered.map((item) => item.id),
  scores,
  topIds,
};

process.stdout.write(JSON.stringify(output));
