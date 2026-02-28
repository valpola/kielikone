#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const assert = require("assert");

const fixtureDir = path.resolve(__dirname, "fixtures");
const quiz = JSON.parse(fs.readFileSync(path.join(fixtureDir, "filters_quiz.json"), "utf8"));
const resultsCsv = fs.readFileSync(path.join(fixtureDir, "filters_results.csv"), "utf8");

const storage = new Map();
const localStorage = {
  getItem: (key) => (storage.has(key) ? storage.get(key) : null),
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: (key) => storage.delete(key),
};

const makeClassList = () => ({
  add: () => {},
  remove: () => {},
  toggle: () => {},
  contains: () => false,
});

const makeElement = (id) => ({
  id,
  value: "",
  textContent: "",
  hidden: false,
  classList: makeClassList(),
  closest: () => ({ classList: makeClassList() }),
  focus: () => {},
  blur: () => {},
  appendChild: () => {},
  remove: () => {},
  addEventListener: function (event, handler) {
    this._handlers = this._handlers || {};
    this._handlers[event] = handler;
  },
});

const makeCheckbox = (value, checked) => ({
  type: "checkbox",
  value,
  checked: Boolean(checked),
});

const makeContainer = () => ({
  inputs: [],
  innerHTML: "",
  addEventListener: function (event, handler) {
    this._handlers = this._handlers || {};
    this._handlers[event] = handler;
  },
  appendChild: function (label) {
    if (label && label.input) {
      this.inputs.push(label.input);
    }
  },
  querySelectorAll: function (selector) {
    if (selector === "input[type=checkbox]:checked") {
      return this.inputs.filter((input) => input.checked);
    }
    return [];
  },
});

const includeContainer = makeContainer();
const excludeContainer = makeContainer();
const recomputeButton = makeElement("recompute-today");
const prompt = makeElement("prompt");
const answer = makeElement("answer");
const reveal = makeElement("reveal");
const next = makeElement("next");
const result = makeElement("result");
const correct = makeElement("correct");
const userAnswer = makeElement("user-answer");
const markCorrect = makeElement("mark-correct");
const markWrong = makeElement("mark-wrong");
const sessionTarget = makeElement("session-target");
const todayLimit = makeElement("today-limit");
const loginBtn = makeElement("login-btn");

const modeButtons = [
  {
    dataset: { mode: "en-tr" },
    classList: makeClassList(),
    addEventListener: function (event, handler) {
      this._handlers = this._handlers || {};
      this._handlers[event] = handler;
    },
  },
  {
    dataset: { mode: "tr-en" },
    classList: makeClassList(),
    addEventListener: function (event, handler) {
      this._handlers = this._handlers || {};
      this._handlers[event] = handler;
    },
  },
];

const elementById = {
  prompt,
  answer,
  reveal,
  next,
  result,
  correct,
  "user-answer": userAnswer,
  "mark-correct": markCorrect,
  "mark-wrong": markWrong,
  "include-tags": includeContainer,
  "exclude-tags": excludeContainer,
  "session-target": sessionTarget,
  "today-limit": todayLimit,
  "login-btn": loginBtn,
  "recompute-today": recomputeButton,
};

const document = {
  getElementById: (id) => elementById[id] || makeElement(id),
  querySelectorAll: (selector) => (selector === ".mode-btn" ? modeButtons : []),
  querySelector: () => null,
  createElement: (tag) => {
    if (tag === "label") {
      return {
        className: "",
        input: null,
        appendChild: function (child) {
          if (child && child.type === "checkbox") this.input = child;
        },
      };
    }
    if (tag === "input") {
      return { type: "", value: "", checked: false };
    }
    if (tag === "span") {
      return { textContent: "" };
    }
    if (tag === "a") {
      return { href: "", download: "", click: () => {}, remove: () => {} };
    }
    return makeElement(tag);
  },
  body: { appendChild: () => {} },
};

const fetch = async (url) => {
  const target = String(url);
  if (target.includes("data/quiz.json")) {
    return { ok: true, json: async () => quiz };
  }
  if (target.includes("data/aliases.json")) {
    return { ok: true, json: async () => ({ aliases: {} }) };
  }
  if (target.includes("format=csv")) {
    return { ok: true, text: async () => resultsCsv };
  }
  if (target.includes("action=whoami")) {
    return { ok: true, text: async () => "test" };
  }
  return { ok: false, text: async () => "" };
};

const windowObj = {
  location: { search: "" },
  alert: () => {},
  prompt: () => "dummy-key",
  addEventListener: () => {},
};

global.document = document;
global.window = windowObj;
global.localStorage = localStorage;
global.fetch = fetch;
global.URL = URL;
global.Blob = function () {};
global.TodayScoring = require(path.resolve(__dirname, "..", "..", "web", "today_scoring.js"));

global.APP_CONFIG = {
  resultsEnabled: true,
  resultsEndpoint: "https://example.test/results",
  cacheBust: "",
};

localStorage.setItem("tr-quiz-api-key", "test");
localStorage.setItem("tr-quiz-include-tags", JSON.stringify(["verb"]));
localStorage.setItem("tr-quiz-exclude-tags", JSON.stringify([]));

require(path.resolve(__dirname, "..", "..", "web", "app.js"));

const waitForLoad = () =>
  new Promise((resolve, reject) => {
    const start = Date.now();
    const poll = () => {
      if (includeContainer.inputs.length > 0) {
        resolve();
        return;
      }
      if (Date.now() - start > 500) {
        reject(new Error("Timed out waiting for loadData"));
        return;
      }
      setTimeout(poll, 5);
    };
    poll();
  });

(async () => {
  await waitForLoad();

  todayLimit.value = "1";

  const trEnBtn = modeButtons.find((btn) => btn.dataset.mode === "tr-en");
  if (trEnBtn && trEnBtn._handlers && trEnBtn._handlers.click) {
    trEnBtn._handlers.click();
  }

  assert.ok(recomputeButton._handlers && recomputeButton._handlers.click, "missing click handler");
  await recomputeButton._handlers.click();

  const stored = JSON.parse(localStorage.getItem("tr-quiz-today-list"));
  assert.ok(stored && Array.isArray(stored.ids), "missing today list");

  const ids = stored.ids;
  assert.strictEqual(ids.length, 1, "expected exactly one today id");
  assert.strictEqual(ids[0], "verb-1", "expected verb-1 to be selected");

  ids.forEach((id) => {
    const item = quiz.items.find((entry) => entry.id === id);
    assert.ok(item, `missing item for ${id}`);
    assert.ok((item.tags || []).includes("verb"), `item ${id} is not tagged verb`);
  });

  console.log("App recompute today filter test passed.");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
