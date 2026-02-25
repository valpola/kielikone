(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.TodayScoring = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var DEFAULT_CONFIG = {
    tau_wrong_days: 21.0,
    tau_right_default_days: 7.0,
    tau_right_by_freq: {
      "freq-100": 3.0,
      "freq-500": 5.0,
      "freq-1000": 8.0,
    },
    weight_wrong: 1.5,
    weight_right: 1.0,
    novelty_bonus: 1.0,
  };

  var parseCsvLine = function (line) {
    var result = [];
    var current = "";
    var inQuotes = false;

    for (var i = 0; i < line.length; i += 1) {
      var char = line[i];
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
      } else if (char === ',') {
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

  var parseCsv = function (text) {
    if (!text) return [];
    var lines = String(text).replace(/\r\n?/g, "\n").split("\n");
    var filtered = lines.filter(function (line) {
      return line.trim().length > 0;
    });
    if (!filtered.length) return [];

    var headers = parseCsvLine(filtered[0]).map(function (header) {
      return header.trim();
    });
    var rows = [];
    for (var i = 1; i < filtered.length; i += 1) {
      var values = parseCsvLine(filtered[i]);
      var row = {};
      for (var j = 0; j < headers.length; j += 1) {
        row[headers[j]] = values[j] !== undefined ? values[j] : "";
      }
      rows.push(row);
    }
    return rows;
  };

  var parseTimestamp = function (value) {
    if (!value) return null;
    var raw = String(value).trim();
    if (!raw) return null;

    if (/Z$/i.test(raw)) {
      var zDate = new Date(raw);
      return Number.isNaN(zDate.getTime()) ? null : zDate;
    }

    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$/.test(raw)) {
      var iso = raw.replace(" ", "T") + "Z";
      var isoDate = new Date(iso);
      return Number.isNaN(isoDate.getTime()) ? null : isoDate;
    }

    var mdMatch = raw.match(/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})(?::(\d{2}))?$/);
    if (mdMatch) {
      var month = Number(mdMatch[1]);
      var day = Number(mdMatch[2]);
      var year = Number(mdMatch[3]);
      var hour = Number(mdMatch[4]);
      var minute = Number(mdMatch[5]);
      var second = Number(mdMatch[6] || "0");
      var utcDate = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
      return Number.isNaN(utcDate.getTime()) ? null : utcDate;
    }

    var fallback = new Date(raw);
    return Number.isNaN(fallback.getTime()) ? null : fallback;
  };

  var parseCorrect = function (value) {
    if (value === null || value === undefined) return null;
    var raw = String(value).trim().toLowerCase();
    if (raw === "true" || raw === "1" || raw === "yes" || raw === "y") return true;
    if (raw === "false" || raw === "0" || raw === "no" || raw === "n") return false;
    return null;
  };

  var canonicalize = function (wordId, aliases) {
    var current = wordId;
    var seen = {};
    while (aliases && Object.prototype.hasOwnProperty.call(aliases, current) && !seen[current]) {
      seen[current] = true;
      current = aliases[current];
    }
    return current;
  };

  var eventStream = function (rows, aliases) {
    var events = [];
    if (!Array.isArray(rows)) return events;

    rows.forEach(function (row) {
      var timestamp = parseTimestamp(row.timestamp);
      var wordId = String(row.word_id || "").trim();
      var mode = String(row.mode || "").trim();
      var correct = parseCorrect(row.correct);
      if (!timestamp || !wordId || !mode || correct === null) return;
      var canonicalId = canonicalize(wordId, aliases || {});
      events.push([timestamp, canonicalId, mode, correct]);
    });

    events.sort(function (a, b) {
      return a[0].getTime() - b[0].getTime();
    });
    return events;
  };

  var buildEventsByKey = function (events) {
    var byKey = {};
    events.forEach(function (event) {
      var key = event[1] + "|" + event[2];
      if (!byKey[key]) byKey[key] = [];
      byKey[key].push([event[0], event[3]]);
    });
    return byKey;
  };

  var decay = function (score, lastTime, current, tauDays) {
    if (score <= 0) return 0.0;
    if (tauDays <= 0) return 0.0;
    var deltaDays = (current.getTime() - lastTime.getTime()) / 86400000.0;
    if (deltaDays <= 0) return score;
    return score * Math.exp(-deltaDays / tauDays);
  };

  var getTauRightDays = function (tags, config) {
    var tauRightDays = config.tau_right_default_days;
    if (!tags) return tauRightDays;

    Object.keys(config.tau_right_by_freq || {}).forEach(function (tag) {
      if (tags.indexOf(tag) !== -1) {
        tauRightDays = Math.min(tauRightDays, config.tau_right_by_freq[tag]);
      }
    });
    return tauRightDays;
  };

  var computeScores = function (events, now, config, tauRightDays) {
    var totalEvents = events.length;
    var wrongScore = 0.0;
    var rightScore = 0.0;
    var lastWrong = null;
    var lastRight = null;

    events.forEach(function (entry) {
      var timestamp = entry[0];
      var correct = entry[1];
      if (correct) {
        if (lastRight) {
          rightScore = decay(rightScore, lastRight, timestamp, tauRightDays);
        }
        rightScore += 1.0;
        lastRight = timestamp;
      } else {
        if (lastWrong) {
          wrongScore = decay(wrongScore, lastWrong, timestamp, config.tau_wrong_days);
        }
        wrongScore += 1.0;
        lastWrong = timestamp;
      }
    });

    if (lastWrong) {
      wrongScore = decay(wrongScore, lastWrong, now, config.tau_wrong_days);
    }
    if (lastRight) {
      rightScore = decay(rightScore, lastRight, now, tauRightDays);
    }

    var noveltyBonus = config.novelty_bonus / (1.0 + totalEvents);
    var score =
      config.weight_wrong * wrongScore -
      config.weight_right * rightScore +
      noveltyBonus;

    return {
      wrong: wrongScore,
      right: rightScore,
      score: score,
      totalEvents: totalEvents,
    };
  };

  var filterItems = function (items, includeTags, excludeTags) {
    var include = includeTags || new Set();
    var exclude = excludeTags || new Set();
    return items.filter(function (item) {
      var tags = new Set(item.tags || []);
      var ok = true;
      include.forEach(function (tag) {
        if (!tags.has(tag)) ok = false;
      });
      exclude.forEach(function (tag) {
        if (tags.has(tag)) ok = false;
      });
      return ok;
    });
  };

  var scoreItems = function (items, eventsByKey, options) {
    var opts = options || {};
    var config = opts.config || DEFAULT_CONFIG;
    var aliases = opts.aliases || null;
    var modes = [];
    var modeValue = String(opts.mode || "en-tr").toLowerCase();
    if (modeValue === "both") {
      modes = ["tr-en", "en-tr"];
    } else if (modeValue === "tr-en" || modeValue === "en-tr") {
      modes = [modeValue];
    } else {
      modes = ["en-tr"];
    }

    var now = opts.now || new Date();
    var scored = [];

    items.forEach(function (item) {
      var wordId = String(item.id || "").trim();
      if (!wordId) return;
      var canonicalId = aliases ? canonicalize(wordId, aliases) : wordId;
      var tags = item.tags || [];
      var tauRightDays = getTauRightDays(tags, config);
      var scores = modes.map(function (mode) {
        var key = canonicalId + "|" + mode;
        var modeEvents = eventsByKey[key] || [];
        return computeScores(modeEvents, now, config, tauRightDays).score;
      });
      var finalScore = scores.length ? Math.max.apply(null, scores) : 0.0;
      scored.push({ id: wordId, score: finalScore });
    });

    return scored;
  };

  var selectTopN = function (scoredItems, limit) {
    var sorted = scoredItems.slice().sort(function (a, b) {
      if (b.score === a.score) {
        return a.id.localeCompare(b.id);
      }
      return b.score - a.score;
    });
    var count = Math.max(0, Number(limit) || 0);
    return sorted.slice(0, count).map(function (entry) {
      return entry.id;
    });
  };

  return {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    parseCsv: parseCsv,
    parseTimestamp: parseTimestamp,
    parseCorrect: parseCorrect,
    canonicalize: canonicalize,
    eventStream: eventStream,
    buildEventsByKey: buildEventsByKey,
    decay: decay,
    computeScores: computeScores,
    filterItems: filterItems,
    scoreItems: scoreItems,
    selectTopN: selectTopN,
  };
});
