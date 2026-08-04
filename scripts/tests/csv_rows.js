"use strict";

// The app reads result rows from Supabase as JSON, so today_scoring.js no longer
// carries a CSV parser. The fixtures are still CSV — they are transcripts of the
// old Sheet, and remain the reference data for the scoring maths — so the parsing
// lives here, in the harness that needs it, rather than in shipped code.

const parseCsvLine = (line) => {
  const result = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (inQuotes) {
      if (char === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        current += char;
      }
    } else if (char === ",") {
      result.push(current);
      current = "";
    } else if (char === '"') {
      inQuotes = true;
    } else {
      current += char;
    }
  }

  result.push(current);
  return result;
};

// Returns the same shape the app hands to TodayScoring.eventStream: one object
// per row, keyed by the CSV header.
const parseCsvRows = (text) => {
  const lines = String(text || "")
    .split(/\r?\n/)
    .filter((line) => line.trim().length > 0);
  if (!lines.length) return [];

  const header = parseCsvLine(lines[0]).map((name) => name.trim());
  return lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    const row = {};
    header.forEach((name, index) => {
      row[name] = (cells[index] || "").trim();
    });
    return row;
  });
};

module.exports = { parseCsvRows, parseCsvLine };
