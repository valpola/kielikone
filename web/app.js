const PROMPT = document.getElementById("prompt");
const ANSWER = document.getElementById("answer");
const REVEAL = document.getElementById("reveal");
const NEXT = document.getElementById("next");
const RESULT = document.getElementById("result");
const CORRECT = document.getElementById("correct");
const USER_ANSWER = document.getElementById("user-answer");
const MARK_CORRECT = document.getElementById("mark-correct");
const MARK_WRONG = document.getElementById("mark-wrong");
const MODE_BTNS = document.querySelectorAll(".mode-btn");
const INCLUDE_TAGS = document.getElementById("include-tags");
const EXCLUDE_TAGS = document.getElementById("exclude-tags");
const SESSION_TARGET = document.getElementById("session-target");
const TODAY_LIMIT = document.getElementById("today-limit");
const RECOMPUTE_TODAY = document.getElementById("recompute-today");

let mode = "en-tr";
let items = [];
let tagRegistry = [];
let current = null;
let seen = 0;
let correct = 0;
const sessionCorrect = new Map();
let computedToday = new Set();
let aliases = {};

const storageKey = (id) => `tr-quiz-${id}`;
const INCLUDE_STORAGE = "tr-quiz-include-tags";
const EXCLUDE_STORAGE = "tr-quiz-exclude-tags";
const SESSION_TARGET_STORAGE = "tr-quiz-session-target";
const DEFAULT_SESSION_TARGET = 2;
const TODAY_LIMIT_STORAGE = "tr-quiz-today-limit";
const TODAY_LIST_STORAGE = "tr-quiz-today-list";
const DEFAULT_TODAY_LIMIT = 30;

const todayStamp = () => new Date().toISOString().slice(0, 10);

const getLocalStats = (id) => {
  const raw = localStorage.getItem(storageKey(id));
  if (!raw) return { lastSeen: "", correct: 0, wrong: 0 };
  try {
    return JSON.parse(raw);
  } catch {
    return { lastSeen: "", correct: 0, wrong: 0 };
  }
};

const setLocalStats = (id, stats) => {
  localStorage.setItem(storageKey(id), JSON.stringify(stats));
};

const API_KEY_STORAGE = "tr-quiz-api-key";

const getApiKey = () => {
  return localStorage.getItem(API_KEY_STORAGE) || "";
};

const ensureApiKey = () => {
  if (getApiKey()) return;
  const value = window.prompt("Enter API key for results logging:");
  if (value) localStorage.setItem(API_KEY_STORAGE, value.trim());
};

const getResultsEndpoint = () => {
  if (typeof APP_CONFIG === "undefined") return "";
  if (!APP_CONFIG.resultsEnabled) return "";
  return APP_CONFIG.resultsEndpoint || "";
};

const getCacheBust = () => {
  if (typeof APP_CONFIG === "undefined") return "";
  return APP_CONFIG.cacheBust || "";
};

const withCacheBust = (url) => {
  const version = getCacheBust();
  if (!version) return url;
  const parsed = new URL(url, window.location.href);
  parsed.searchParams.set("v", version);
  return parsed.toString();
};

const sendResult = async (payload) => {
  const endpoint = getResultsEndpoint();
  if (!endpoint) return;

  const apiKey = getApiKey();
  if (!apiKey) return;

  const body = new URLSearchParams();
  Object.entries(payload).forEach(([key, value]) => {
    body.set(key, String(value));
  });
  body.set("api_key", apiKey);

  try {
    await fetch(endpoint, {
      method: "POST",
      mode: "cors",
      body,
    });
  } catch (error) {
    // Silent failure to keep quiz flow smooth.
  }
};

const selectedValues = (container) => {
  return new Set(
    Array.from(container.querySelectorAll("input[type=checkbox]:checked")).map(
      (input) => input.value
    )
  );
};

const loadSelection = (key) => {
  const raw = localStorage.getItem(key);
  if (!raw) return new Set();
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return new Set(parsed);
  } catch {
    return new Set();
  }
  return new Set();
};

const saveSelection = (key, values) => {
  localStorage.setItem(key, JSON.stringify(Array.from(values)));
};

const loadSessionTarget = () => {
  const raw = Number(localStorage.getItem(SESSION_TARGET_STORAGE));
  const value = Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : DEFAULT_SESSION_TARGET;
  SESSION_TARGET.value = String(value);
};

const getSessionTarget = () => {
  const raw = Number(SESSION_TARGET.value);
  if (!Number.isFinite(raw) || raw < 1) return DEFAULT_SESSION_TARGET;
  return Math.floor(raw);
};

const saveSessionTarget = () => {
  localStorage.setItem(SESSION_TARGET_STORAGE, String(getSessionTarget()));
};

const loadTodayLimit = () => {
  const raw = Number(localStorage.getItem(TODAY_LIMIT_STORAGE));
  const value = Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : DEFAULT_TODAY_LIMIT;
  TODAY_LIMIT.value = String(value);
};

const getTodayLimit = () => {
  const raw = Number(TODAY_LIMIT.value);
  if (!Number.isFinite(raw) || raw < 1) return DEFAULT_TODAY_LIMIT;
  return Math.floor(raw);
};

const saveTodayLimit = () => {
  localStorage.setItem(TODAY_LIMIT_STORAGE, String(getTodayLimit()));
};

const loadStoredToday = () => {
  const raw = localStorage.getItem(TODAY_LIST_STORAGE);
  if (!raw) return new Set();
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.date === todayStamp() && Array.isArray(parsed.ids)) {
      return new Set(parsed.ids);
    }
  } catch {
    return new Set();
  }
  return new Set();
};

const saveStoredToday = (ids) => {
  localStorage.setItem(
    TODAY_LIST_STORAGE,
    JSON.stringify({ date: todayStamp(), ids: Array.from(ids) })
  );
};

const getFilteredItems = () => {
  const include = selectedValues(INCLUDE_TAGS);
  const exclude = selectedValues(EXCLUDE_TAGS);

  return items.filter((item) => {
    const itemTags = new Set(item.tags || []);
    const isToday = itemTags.has("today") || computedToday.has(item.id);

    for (const tagId of include) {
      if (tagId === "today") {
        if (!isToday) return false;
        continue;
      }
      if (!itemTags.has(tagId)) return false;
    }

    for (const tagId of exclude) {
      if (tagId === "today") {
        if (isToday) return false;
        continue;
      }
      if (itemTags.has(tagId)) return false;
    }

    return true;
  });
};

const filterItemsByTags = (allItems, include, exclude) => {
  return allItems.filter((item) => {
    const itemTags = new Set(item.tags || []);

    for (const tagId of include) {
      if (!itemTags.has(tagId)) return false;
    }

    for (const tagId of exclude) {
      if (itemTags.has(tagId)) return false;
    }

    return true;
  });
};

const getResultsCsvEndpoint = () => {
  const endpoint = getResultsEndpoint();
  if (!endpoint) return "";
  if (endpoint.includes("?")) return `${endpoint}&format=csv`;
  return `${endpoint}?format=csv`;
};

const fetchResultsCsv = async () => {
  const endpoint = getResultsCsvEndpoint();
  if (!endpoint) return "";
  const url = new URL(endpoint);
  const apiKey = getApiKey();
  if (apiKey) url.searchParams.set("api_key", apiKey);
  const response = await fetch(url.toString(), { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch results");
  }
  return response.text();
};

const recomputeToday = async () => {
  if (typeof TodayScoring === "undefined") {
    window.alert("Today scoring module is missing.");
    return;
  }

  const endpoint = getResultsEndpoint();
  if (!endpoint) {
    window.alert("Results endpoint is not configured.");
    return;
  }

  ensureApiKey();
  if (!getApiKey()) {
    window.alert("API key is required to fetch results.");
    return;
  }

  RECOMPUTE_TODAY.disabled = true;
  const previousLabel = RECOMPUTE_TODAY.textContent;
  RECOMPUTE_TODAY.textContent = "Recomputing...";

  try {
    const csvText = await fetchResultsCsv();
    if (!csvText) {
      throw new Error("No results data received");
    }

    const rows = TodayScoring.parseCsv(csvText);
    const events = TodayScoring.eventStream(rows, aliases);
    const eventsByKey = TodayScoring.buildEventsByKey(events);

    const include = selectedValues(INCLUDE_TAGS);
    const exclude = selectedValues(EXCLUDE_TAGS);
    include.delete("today");
    exclude.delete("today");

    const filtered = filterItemsByTags(items, include, exclude);
    const scored = TodayScoring.scoreItems(filtered, eventsByKey, {
      mode,
      now: new Date(),
    });

    const topIds = TodayScoring.selectTopN(scored, getTodayLimit());
    computedToday = new Set(topIds);
    saveStoredToday(computedToday);
    renderPrompt();
  } catch (error) {
    window.alert("Failed to recompute today list.");
  } finally {
    RECOMPUTE_TODAY.disabled = false;
    RECOMPUTE_TODAY.textContent = previousLabel;
  }
};

const weightForItem = (item) => {
  const stats = getLocalStats(item.id);
  const priority = Math.max(1, Math.min(5, Number(item.priority || 1)));
  if (!stats.lastSeen) return priority * 2;

  const days = Math.floor(
    (Date.now() - new Date(stats.lastSeen).getTime()) / (1000 * 60 * 60 * 24)
  );
  const dueBoost = Math.min(3, Math.max(0, days / 4));
  return priority + dueBoost;
};

const pickNext = () => {
  const filtered = getFilteredItems();
  const target = getSessionTarget();
  const eligible = filtered.filter(
    (item) => (sessionCorrect.get(item.id) || 0) < target
  );
  if (!eligible.length) return null;

  const weighted = eligible.map((item) => ({
    item,
    weight: weightForItem(item),
  }));

  const total = weighted.reduce((sum, entry) => sum + entry.weight, 0);
  let roll = Math.random() * total;
  for (const entry of weighted) {
    roll -= entry.weight;
    if (roll <= 0) return entry.item;
  }
  return weighted[weighted.length - 1].item;
};

const renderMode = () => {
  MODE_BTNS.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
};

const updateStats = () => {};

const renderTagOptions = () => {
  const existing = new Map(
    tagRegistry.map((tag) => [tag.id, tag.label || tag.id])
  );

  const usedTags = new Set();
  items.forEach((item) => {
    (item.tags || []).forEach((tagId) => usedTags.add(tagId));
  });

  const tagIds = Array.from(new Set([...existing.keys(), ...usedTags])).sort();
  const includeSelection = loadSelection(INCLUDE_STORAGE);
  const excludeSelection = loadSelection(EXCLUDE_STORAGE);

  if (!includeSelection.size && tagIds.includes("today")) {
    includeSelection.add("today");
    saveSelection(INCLUDE_STORAGE, includeSelection);
  }

  const buildTag = (tagId, selected) => {
    const label = document.createElement("label");
    label.className = "tag-item";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = tagId;
    input.checked = selected.has(tagId);

    const text = document.createElement("span");
    text.textContent = existing.get(tagId) || tagId;

    label.appendChild(input);
    label.appendChild(text);
    return label;
  };

  INCLUDE_TAGS.innerHTML = "";
  EXCLUDE_TAGS.innerHTML = "";
  tagIds.forEach((tagId) => {
    INCLUDE_TAGS.appendChild(buildTag(tagId, includeSelection));
    EXCLUDE_TAGS.appendChild(buildTag(tagId, excludeSelection));
  });
};

const renderPrompt = () => {
  current = pickNext();
  if (!current) {
    PROMPT.textContent = "No items match current filters";
    REVEAL.hidden = true;
    RESULT.classList.add("hidden");
    MARK_CORRECT.closest(".grade").classList.add("hidden");
    return;
  }

  const promptText = mode === "tr-en" ? current.turkish : current.english;
  PROMPT.textContent = promptText;
  ANSWER.value = "";
  REVEAL.hidden = false;
  RESULT.classList.add("hidden");
  MARK_CORRECT.closest(".grade").classList.add("hidden");
  ANSWER.focus();
};

const revealAnswer = () => {
  if (!current) return;
  const correctText = mode === "tr-en" ? current.english : current.turkish;
  CORRECT.textContent = correctText;
  USER_ANSWER.textContent = ANSWER.value || "(no answer)";
  REVEAL.hidden = true;
  RESULT.classList.remove("hidden");
  MARK_CORRECT.closest(".grade").classList.remove("hidden");
  ANSWER.blur();
};

const grade = (isCorrect) => {
  if (!current) return;
  const stats = getLocalStats(current.id);
  stats.lastSeen = todayStamp();
  if (isCorrect) stats.correct += 1;
  else stats.wrong += 1;
  setLocalStats(current.id, stats);

  if (isCorrect) {
    const count = (sessionCorrect.get(current.id) || 0) + 1;
    sessionCorrect.set(current.id, count);
  }

  sendResult({
    timestamp: new Date().toISOString(),
    word_id: current.id,
    mode,
    correct: isCorrect,
  });

  seen += 1;
  if (isCorrect) correct += 1;
  updateStats();
  renderPrompt();
};

MODE_BTNS.forEach((btn) => {
  btn.addEventListener("click", () => {
    mode = btn.dataset.mode;
    renderMode();
    renderPrompt();
  });
});

INCLUDE_TAGS.addEventListener("change", () => {
  saveSelection(INCLUDE_STORAGE, selectedValues(INCLUDE_TAGS));
  updateStats();
  renderPrompt();
});

EXCLUDE_TAGS.addEventListener("change", () => {
  saveSelection(EXCLUDE_STORAGE, selectedValues(EXCLUDE_TAGS));
  updateStats();
  renderPrompt();
});

SESSION_TARGET.addEventListener("change", () => {
  saveSessionTarget();
  renderPrompt();
});

TODAY_LIMIT.addEventListener("change", () => {
  saveTodayLimit();
});

RECOMPUTE_TODAY.addEventListener("click", recomputeToday);

REVEAL.addEventListener("click", revealAnswer);
NEXT.addEventListener("click", renderPrompt);
MARK_CORRECT.addEventListener("click", () => grade(true));
MARK_WRONG.addEventListener("click", () => grade(false));

window.addEventListener("keydown", (event) => {
  const isAnswerFocused = document.activeElement === ANSWER;
  const isResultVisible = !RESULT.classList.contains("hidden");
  const key = event.key.toLowerCase();

  if (event.key === "Enter") {
    event.preventDefault();
    revealAnswer();
    return;
  }

  if (isAnswerFocused) return;

  if (isResultVisible) {
    if (key === "f") {
      event.preventDefault();
      grade(true);
      return;
    } else if (key === "j") {
      event.preventDefault();
      grade(false);
      return;
    }
  }

  if (key === "n") {
    event.preventDefault();
    renderPrompt();
  }
});

const loadData = async () => {
  const response = await fetch(withCacheBust("data/quiz.json"), { cache: "no-store" });
  const data = await response.json();
  items = data.items || [];
  tagRegistry = data.tags || [];

  try {
    const aliasResponse = await fetch(withCacheBust("data/aliases.json"), {
      cache: "no-store",
    });
    if (aliasResponse.ok) {
      const aliasData = await aliasResponse.json();
      aliases = aliasData.aliases || {};
    }
  } catch {
    aliases = {};
  }

  ensureApiKey();
  loadSessionTarget();
  loadTodayLimit();
  computedToday = loadStoredToday();
  renderTagOptions();
  renderMode();
  updateStats();
  renderPrompt();
};

loadData().catch(() => {
  PROMPT.textContent = "Failed to load data/quiz.json";
});
