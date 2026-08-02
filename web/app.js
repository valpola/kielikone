const PROMPT = document.getElementById("prompt");
const HINT = document.getElementById("hint");
const ANSWER = document.getElementById("answer");
const CORRECT_ANSWER = document.getElementById("correct-answer");
const REVEAL = document.getElementById("reveal");
const ACTIONS = document.getElementById("actions");
const GRADE = document.getElementById("grade");
const NEXT = document.getElementById("next");
const MARK_CORRECT = document.getElementById("mark-correct");
const MARK_WRONG = document.getElementById("mark-wrong");
const MODE_BTNS = document.querySelectorAll(".mode-btn");
const INCLUDE_TAGS = document.getElementById("include-tags");
const EXCLUDE_TAGS = document.getElementById("exclude-tags");
const SESSION_TARGET = document.getElementById("session-target");
const TODAY_LIMIT = document.getElementById("today-limit");
const LOGIN_BTN = document.getElementById("login-btn");
const QUEUE_STATUS = document.getElementById("queue-status");
const RECOMPUTE_TODAY = document.getElementById("recompute-today");
const OPTIONS_GRID = document.querySelector(".options-grid");
const TODAY_STATS = document.getElementById("today-stats");
const NOTE_DETAILS = document.getElementById("note");
const NOTE_INPUT = document.getElementById("note-input");
const NOTE_SAVE = document.getElementById("note-save");
const NOTE_STATUS = document.getElementById("note-status");

const MODE_STORAGE = "tr-quiz-mode";
const DEFAULT_MODE = "en-tr";
let mode = DEFAULT_MODE;
let items = [];
let tagRegistry = [];
let current = null;
let isRevealed = false;
const sessionCorrect = new Map();
let computedToday = new Set();
let aliases = {};

const storageKey = (id) => `tr-quiz-${id}`;
const INCLUDE_STORAGE = "tr-quiz-include-tags";
const EXCLUDE_STORAGE = "tr-quiz-exclude-tags";
const SESSION_TARGET_STORAGE = "tr-quiz-session-target";
const DEFAULT_SESSION_TARGET = 1;
const TODAY_LIMIT_STORAGE = "tr-quiz-today-limit";
const TODAY_LIST_STORAGE = "tr-quiz-today-list";
const RESULTS_QUEUE_STORAGE = "tr-quiz-results-queue";
const COMMENT_QUEUE_STORAGE = "tr-quiz-comments-queue";
const COMMENT_TOKEN_STORAGE = "tr-quiz-github-token";
const DEFAULT_TODAY_LIMIT = 10;
const DEBUG_MODE = new URLSearchParams(window.location.search).get("debug") === "1";
const DEBUG_SCORES_STORAGE = "tr-quiz-debug-scores";

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
const USER_NAME_STORAGE = "tr-quiz-user-name";
let loginState = {
  userName: "",
  valid: false,
  checking: false,
};
let resultQueueBusy = false;

const loadResultQueue = () => {
  const raw = localStorage.getItem(RESULTS_QUEUE_STORAGE);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (entry) =>
        entry &&
        typeof entry === "object" &&
        typeof entry.timestamp === "string" &&
        typeof entry.word_id === "string" &&
        typeof entry.mode === "string" &&
        typeof entry.correct === "boolean"
    );
  } catch {
    return [];
  }
};

const updateQueueStatusUi = () => {
  if (!QUEUE_STATUS) return;
  const pending = loadResultQueue().length;
  if (pending <= 0) {
    QUEUE_STATUS.textContent = "";
    QUEUE_STATUS.classList.add("hidden");
    return;
  }
  QUEUE_STATUS.textContent = `Pending sync: ${pending}`;
  QUEUE_STATUS.classList.remove("hidden");
};

const sameQueuedResult = (left, right) => {
  if (!left || !right) return false;
  if (left.client_event_id && right.client_event_id) {
    return left.client_event_id === right.client_event_id;
  }
  return (
    left.timestamp === right.timestamp &&
    left.word_id === right.word_id &&
    left.mode === right.mode &&
    left.correct === right.correct
  );
};

const saveResultQueue = (queue) => {
  localStorage.setItem(RESULTS_QUEUE_STORAGE, JSON.stringify(queue));
  updateQueueStatusUi();
};

const removeQueuedResult = (payload) => {
  const queue = loadResultQueue();
  const index = queue.findIndex((entry) => sameQueuedResult(entry, payload));
  if (index === -1) return;
  queue.splice(index, 1);
  saveResultQueue(queue);
};

const enqueueResult = (payload) => {
  const queue = loadResultQueue();
  queue.push({
    timestamp: payload.timestamp,
    word_id: payload.word_id,
    mode: payload.mode,
    correct: payload.correct,
    client_event_id:
      payload.client_event_id || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  });
  saveResultQueue(queue);
};

const sendQueuedResult = async (endpoint, apiKey, payload) => {
  const body = new URLSearchParams();
  Object.entries(payload).forEach(([key, value]) => {
    body.set(key, String(value));
  });
  body.set("api_key", apiKey);

  // Without a timeout a hung POST leaves resultQueueBusy set for as long as the
  // socket stays open, which silently blocks every later flush until a reload.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      mode: "cors",
      body,
      keepalive: true,
      signal: controller.signal,
    });

    if (!response.ok) return false;

    const text = (await response.text()).trim();
    return text === "OK";
  } finally {
    clearTimeout(timer);
  }
};

const flushResultQueue = async () => {
  if (resultQueueBusy) return;

  const endpoint = getResultsEndpoint();
  const apiKey = getApiKey();
  if (!endpoint || !apiKey || !loginState.valid) return;

  resultQueueBusy = true;
  try {
    while (true) {
      const next = loadResultQueue()[0];
      if (!next) return;

      try {
        const ok = await sendQueuedResult(endpoint, apiKey, next);
        if (!ok) return;
      } catch {
        return;
      }

      removeQueuedResult(next);
    }
  } finally {
    resultQueueBusy = false;
  }
};

// ---- Comments: filed as GitHub issues; write token kept in localStorage only ----
const setNoteStatus = (text) => {
  if (NOTE_STATUS) NOTE_STATUS.textContent = text || "";
};

const resetNoteUi = () => {
  if (NOTE_INPUT) NOTE_INPUT.value = "";
  setNoteStatus("");
  if (NOTE_DETAILS) NOTE_DETAILS.open = false;
};

const getCommentRepo = () =>
  (typeof APP_CONFIG !== "undefined" && APP_CONFIG.commentRepo) || "";
const getCommentLabel = () =>
  (typeof APP_CONFIG !== "undefined" && APP_CONFIG.commentLabel) || "vocab-comment";
const getCommentToken = () => localStorage.getItem(COMMENT_TOKEN_STORAGE) || "";
const setCommentToken = (token) => {
  if (token) localStorage.setItem(COMMENT_TOKEN_STORAGE, token);
  else localStorage.removeItem(COMMENT_TOKEN_STORAGE);
};

const loadCommentQueue = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(COMMENT_QUEUE_STORAGE) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};
const saveCommentQueue = (queue) => {
  localStorage.setItem(COMMENT_QUEUE_STORAGE, JSON.stringify(queue));
};
const enqueueComment = (payload) => {
  const queue = loadCommentQueue();
  queue.push(payload);
  saveCommentQueue(queue);
};

const buildIssue = (c) => ({
  title: ("[note] " + c.turkish).slice(0, 120),
  body:
    "**Word:** " + c.turkish + " = " + c.english + "\n" +
    "**id:** " + c.word_id + "\n" +
    "**mode:** " + c.mode + "\n" +
    "**when:** " + c.timestamp + "\n\n" +
    c.comment,
  labels: [getCommentLabel()],
});

const sendQueuedComment = async (token, payload) => {
  const repo = getCommentRepo();
  if (!repo) return { ok: false, auth: true };
  const res = await fetch("https://api.github.com/repos/" + repo + "/issues", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + token,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildIssue(payload)),
  });
  // 401/403 => token missing scope or invalid; anything else non-ok => transient.
  if (res.status === 401 || res.status === 403) return { ok: false, auth: false };
  return { ok: res.ok, auth: true };
};

let commentQueueBusy = false;
const flushCommentQueue = async ({ interactive = false } = {}) => {
  if (commentQueueBusy) return;
  if (!loadCommentQueue().length) return;

  let token = getCommentToken();
  if (!token) {
    if (!interactive) return; // never prompt during a background flush
    token = window.prompt(
      "Paste a GitHub token (fine-grained, Issues: write on " +
        getCommentRepo() +
        ").\nStored on this device only."
    );
    if (!token) {
      setNoteStatus("No token entered — note kept in queue.");
      return;
    }
    token = token.trim();
    setCommentToken(token);
  }

  commentQueueBusy = true;
  try {
    while (true) {
      const next = loadCommentQueue()[0];
      if (!next) return;

      let result;
      try {
        result = await sendQueuedComment(token, next);
      } catch {
        setNoteStatus("Offline — note queued, will retry.");
        return;
      }

      if (result.ok) {
        const queue = loadCommentQueue();
        queue.shift();
        saveCommentQueue(queue);
        const left = loadCommentQueue().length;
        setNoteStatus("Note saved ✓" + (left ? " (" + left + " queued)" : ""));
      } else if (!result.auth) {
        setCommentToken(""); // clear bad/expired token so the next save re-prompts
        setNoteStatus("Token rejected — cleared. Click Save again to re-enter.");
        return;
      } else {
        setNoteStatus("Save failed — note kept in queue.");
        return;
      }
    }
  } finally {
    commentQueueBusy = false;
  }
};

const saveNote = () => {
  if (!current) {
    setNoteStatus("No word is shown right now.");
    return;
  }
  const text = ((NOTE_INPUT && NOTE_INPUT.value) || "").trim();
  if (!text) {
    setNoteStatus("Write a note first.");
    return;
  }
  enqueueComment({
    word_id: current.id,
    turkish: current.turkish,
    english: current.english,
    mode,
    comment: text,
    timestamp: new Date().toISOString(),
  });
  if (NOTE_INPUT) NOTE_INPUT.value = "";
  setNoteStatus("Saving…");
  void flushCommentQueue({ interactive: true });
};

const getApiKey = () => {
  return localStorage.getItem(API_KEY_STORAGE) || "";
};

const getStoredUserName = () => {
  return localStorage.getItem(USER_NAME_STORAGE) || "";
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

const updateLoginUi = () => {
  if (!LOGIN_BTN) return;
  if (loginState.checking) {
    LOGIN_BTN.textContent = "Attempting to log in";
    return;
  }
  if (loginState.valid && loginState.userName) {
    LOGIN_BTN.textContent = loginState.userName;
  } else {
    LOGIN_BTN.textContent = "Login to record results";
  }
};

const fetchUserName = async (apiKey) => {
  const endpoint = getResultsEndpoint();
  if (!endpoint || !apiKey) return "";
  const url = new URL(endpoint);
  url.searchParams.set("api_key", apiKey);
  url.searchParams.set("action", "whoami");
  const response = await fetch(url.toString(), { cache: "no-store" });
  if (!response.ok) return "";
  const text = await response.text();
  return text.trim();
};

const validateApiKey = async (apiKey) => {
  if (!apiKey) {
    loginState.userName = "";
    loginState.valid = false;
    loginState.checking = false;
    localStorage.removeItem(USER_NAME_STORAGE);
    updateLoginUi();
    return;
  }

  loginState.checking = true;
  updateLoginUi();

  try {
    const userName = await fetchUserName(apiKey);
    loginState.checking = false;
    if (userName) {
      loginState.userName = userName;
      loginState.valid = true;
      localStorage.setItem(USER_NAME_STORAGE, userName);
      void flushResultQueue();
    } else {
      loginState.userName = "";
      loginState.valid = false;
      localStorage.removeItem(USER_NAME_STORAGE);
    }
  } catch (error) {
    loginState.checking = false;
    loginState.userName = "";
    loginState.valid = false;
  }
  updateLoginUi();
};

const handleLoginClick = async () => {
  const currentKey = getApiKey();
  const value = window.prompt("Enter API key for results logging:", currentKey);
  if (value === null) return;
  const nextKey = value.trim();
  if (!nextKey) {
    localStorage.removeItem(API_KEY_STORAGE);
    localStorage.removeItem(USER_NAME_STORAGE);
    loginState.userName = "";
    loginState.valid = false;
    updateLoginUi();
    return;
  }

  localStorage.setItem(API_KEY_STORAGE, nextKey);
  await validateApiKey(nextKey);
};

const initLoginState = async () => {
  loginState.userName = getStoredUserName();
  loginState.valid = false;
  loginState.checking = false;
  updateLoginUi();

  const apiKey = getApiKey();
  if (apiKey) {
    await validateApiKey(apiKey);
  }
};

const sendResult = async (payload) => {
  const endpoint = getResultsEndpoint();
  if (!endpoint) return;

  const apiKey = getApiKey();
  if (!apiKey) return;

  enqueueResult(payload);
  if (!loginState.valid) return;
  await flushResultQueue();
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

const storeDebugScores = (payload) => {
  if (!DEBUG_MODE) return;
  localStorage.setItem(DEBUG_SCORES_STORAGE, JSON.stringify(payload));
  window.__todayDebug = payload;
};

const downloadDebugScores = () => {
  const raw = localStorage.getItem(DEBUG_SCORES_STORAGE);
  if (!raw) {
    window.alert("No debug scores saved yet. Run recompute today first.");
    return;
  }
  const blob = new Blob([raw], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "today-scores.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const renderDebugControls = () => {
  if (!DEBUG_MODE || !OPTIONS_GRID) return;
  const button = document.createElement("button");
  button.className = "ghost";
  button.textContent = "Download scores (debug)";
  button.addEventListener("click", downloadDebugScores);
  OPTIONS_GRID.appendChild(button);
};

const getFilteredItems = () => {
  const include = selectedValues(INCLUDE_TAGS);
  const exclude = selectedValues(EXCLUDE_TAGS);
  const hasComputedToday = computedToday && computedToday.size > 0;

  return items.filter((item) => {
    const itemTags = new Set(item.tags || []);
    const isToday = hasComputedToday
      ? computedToday.has(item.id)
      : itemTags.has("today") || computedToday.has(item.id);

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
  if (!apiKey || !loginState.valid) {
    throw new Error("API key is required to fetch results");
  }
  if (apiKey) url.searchParams.set("api_key", apiKey);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url.toString(), {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error("Failed to fetch results");
    }
    return await response.text();
  } finally {
    clearTimeout(timer);
  }
};

const recomputeToday = async ({ silent = false } = {}) => {
  if (typeof TodayScoring === "undefined") {
    if (!silent) window.alert("Today scoring module is missing.");
    return;
  }

  const endpoint = getResultsEndpoint();
  if (!endpoint) {
    if (!silent) window.alert("Results endpoint is not configured.");
    return;
  }
  if (!getApiKey()) {
    if (!silent) window.alert("Login is required to fetch results.");
    return;
  }
  if (!loginState.valid) {
    if (!silent) window.alert("API key is invalid.");
    return;
  }

  RECOMPUTE_TODAY.disabled = true;
  const previousLabel = RECOMPUTE_TODAY.textContent;
  RECOMPUTE_TODAY.textContent = "Recomputing...";

  // Visible loading state so the user sees the app reacted (e.g. after an
  // empty-state Enter). current is nulled so a stray Enter stays inert until
  // the next word loads (instead of revealing/grading an empty answer).
  current = null;
  PROMPT.textContent = "Recomputing today's words…";
  if (HINT) HINT.classList.add("hidden");
  REVEAL.hidden = true;
  ACTIONS.classList.add("hidden");
  GRADE.classList.add("hidden");
  ANSWER.value = "";

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
      aliases,
    });

    // Summary stats over the filtered set (shown in the open Options section).
    if (TODAY_STATS) {
      if (scored.length) {
        const scoreValues = scored.map((entry) => entry.score);
        const avg = scoreValues.reduce((sum, v) => sum + v, 0) / scoreValues.length;
        const max = Math.max.apply(null, scoreValues);
        TODAY_STATS.textContent =
          scored.length + " words in filter · avg " + avg.toFixed(3) + " · max " + max.toFixed(3);
      } else {
        TODAY_STATS.textContent = "No words match the current filters.";
      }
    }

    storeDebugScores({
      generatedAt: new Date().toISOString(),
      mode,
      limit: getTodayLimit(),
      includeTags: Array.from(include),
      excludeTags: Array.from(exclude),
      scores: scored,
    });

    const topIds = TodayScoring.selectTopN(scored, getTodayLimit());
    computedToday = new Set(topIds);
    saveStoredToday(computedToday);
    sessionCorrect.clear();
    renderPrompt();
    return true;
  } catch (error) {
    if (!silent) {
      window.alert("Failed to recompute today list.");
      renderPrompt();
    }
  } finally {
    RECOMPUTE_TODAY.disabled = false;
    RECOMPUTE_TODAY.textContent = previousLabel;
  }
};

const loadMode = () => {
  const raw = localStorage.getItem(MODE_STORAGE);
  if (!raw) return;
  const value = String(raw).toLowerCase();
  const allowedModes = new Set(
    Array.from(MODE_BTNS).map((btn) => String(btn.dataset.mode || "").toLowerCase())
  );
  if (allowedModes.has(value)) {
    mode = value;
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
  resetNoteUi();
  current = pickNext();
  if (!current) {
    PROMPT.textContent = "No items match current filters";
    if (HINT) {
      HINT.textContent = "Press Enter to recompute today";
      HINT.classList.remove("hidden");
    }
    REVEAL.hidden = true;
    ACTIONS.classList.add("hidden");
    GRADE.classList.add("hidden");
    ANSWER.value = "";
    CORRECT_ANSWER.value = "";
    clearCorrectAnswerState();
    isRevealed = false;
    return;
  }

  const promptText = mode === "tr-en" ? current.turkish : current.english;
  PROMPT.textContent = promptText;
  if (HINT) {
    const hintText = mode === "tr-en" ? (current.hint_tr_en || "") : (current.hint_en_tr || "");
    HINT.textContent = hintText;
    HINT.classList.toggle("hidden", !hintText);
  }
  ANSWER.value = "";
  CORRECT_ANSWER.value = "";
  clearCorrectAnswerState();
  REVEAL.hidden = false;
  ACTIONS.classList.remove("hidden");
  GRADE.classList.add("hidden");
  ANSWER.focus();
  isRevealed = false;
};

const revealAnswer = () => {
  if (!current) return;
  const correctText = mode === "tr-en" ? current.english : current.turkish;
  CORRECT_ANSWER.value = correctText;
  setCorrectAnswerState(isAnswerCorrect());
  REVEAL.hidden = true;
  ACTIONS.classList.add("hidden");
  GRADE.classList.remove("hidden");
  ANSWER.focus();
  isRevealed = true;
};

const clearCorrectAnswerState = () => {
  CORRECT_ANSWER.classList.remove("is-correct", "is-incorrect");
};

const setCorrectAnswerState = (isCorrect) => {
  clearCorrectAnswerState();
  CORRECT_ANSWER.classList.add(isCorrect ? "is-correct" : "is-incorrect");
};

const normalizeAnswer = (value) =>
  String(value || "")
    .trim()
    .normalize("NFKC")
    .replace(/[().! ,]/g, "")
    .toLocaleLowerCase("tr-TR")
    // circumflex-insensitive: accept a/i/u for â/î/û so learners needn't type the ^
    .replace(/â/g, "a")
    .replace(/î/g, "i")
    .replace(/û/g, "u");

// Slash-separated alternatives (e.g. "enteresan / ilginç") match in any order.
const normalizeAnswerSet = (value) =>
  String(value || "")
    .split("/")
    .map((part) => normalizeAnswer(part))
    .filter((part) => part.length > 0)
    .sort()
    .join("/");

const isAnswerCorrect = () => {
  if (!current) return false;
  const correctText = mode === "tr-en" ? current.english : current.turkish;
  return normalizeAnswerSet(ANSWER.value) === normalizeAnswerSet(correctText);
};

const grade = (isCorrect) => {
  if (!current) return;
  setCorrectAnswerState(isCorrect);
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
    client_event_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  });

  renderPrompt();
};

MODE_BTNS.forEach((btn) => {
  btn.addEventListener("click", () => {
    mode = btn.dataset.mode;
    localStorage.setItem(MODE_STORAGE, mode);
    renderMode();
    renderPrompt();
  });
});

INCLUDE_TAGS.addEventListener("change", () => {
  saveSelection(INCLUDE_STORAGE, selectedValues(INCLUDE_TAGS));
  renderPrompt();
});

EXCLUDE_TAGS.addEventListener("change", () => {
  saveSelection(EXCLUDE_STORAGE, selectedValues(EXCLUDE_TAGS));
  renderPrompt();
});

SESSION_TARGET.addEventListener("change", () => {
  saveSessionTarget();
  renderPrompt();
});

TODAY_LIMIT.addEventListener("change", () => {
  saveTodayLimit();
});

RECOMPUTE_TODAY.addEventListener("click", () => recomputeToday());

if (NOTE_SAVE) {
  NOTE_SAVE.addEventListener("click", () => saveNote());
}
if (NOTE_INPUT) {
  // Keep global shortcuts (Enter/f/j/n/Tab) from firing while typing a note.
  NOTE_INPUT.addEventListener("keydown", (event) => event.stopPropagation());
}

REVEAL.addEventListener("click", revealAnswer);
NEXT.addEventListener("click", renderPrompt);
MARK_CORRECT.addEventListener("click", () => grade(true));
MARK_WRONG.addEventListener("click", () => grade(false));
LOGIN_BTN.addEventListener("click", handleLoginClick);

const handleEnterKey = (event) => {
  if (event.key !== "Enter") return false;
  event.preventDefault();
  if (!current) {
    // Empty state: an empty Enter triggers a recompute for the next batch.
    if (!ANSWER.value.trim() && !RECOMPUTE_TODAY.disabled) {
      recomputeToday();
    }
  } else if (isRevealed) {
    grade(isAnswerCorrect());
  } else {
    revealAnswer();
  }
  return true;
};

ANSWER.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  if (key === "tab") {
    event.preventDefault();
    renderPrompt();
    event.stopPropagation();
    return;
  }
  if (isRevealed && (key === "f" || key === "j")) {
    event.preventDefault();
    grade(key === "f");
    event.stopPropagation();
    return;
  }
  if (isRevealed && key === "n") {
    event.preventDefault();
    renderPrompt();
    event.stopPropagation();
    return;
  }
  if (handleEnterKey(event)) {
    event.stopPropagation();
  }
});

window.addEventListener("keydown", (event) => {
  const isAnswerFocused = document.activeElement === ANSWER;
  const key = event.key.toLowerCase();

  if (handleEnterKey(event)) return;

  if (isAnswerFocused) return;

  if (isRevealed) {
    if (key === "f") {
      event.preventDefault();
      grade(true);
      return;
    } else if (key === "j") {
      event.preventDefault();
      grade(false);
      return;
    } else if (key === "n") {
      event.preventDefault();
      renderPrompt();
      return;
    }
  }

  if (key === "tab") {
    event.preventDefault();
    renderPrompt();
  }
});

window.addEventListener("online", () => {
  void flushResultQueue();
  void flushCommentQueue();
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    void flushResultQueue();
    void flushCommentQueue();
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

  loadSessionTarget();
  loadTodayLimit();
  loadMode();
  updateQueueStatusUi();
  await initLoginState();
  const flushed = Promise.resolve(flushResultQueue()).catch(() => {});
  computedToday = loadStoredToday();
  renderDebugControls();
  renderTagOptions();
  renderMode();
  if (loginState.valid) {
    // Refresh today's list BEFORE showing any word, so a reload never flashes a
    // stale word and then swaps it. Wait for the result queue to flush first so
    // freshly-graded words are reflected. Fall back to the stored list if the
    // refresh fails or times out.
    PROMPT.textContent = "Loading today's words…";
    HINT.classList.add("hidden");
    REVEAL.hidden = true;
    ACTIONS.classList.add("hidden");
    GRADE.classList.add("hidden");
    const refreshed = await flushed.then(() => recomputeToday({ silent: true }));
    if (!refreshed) renderPrompt();
  } else {
    renderPrompt();
  }
};

loadData().catch(() => {
  PROMPT.textContent = "Failed to load data/quiz.json";
});

// Retry any comments queued from a previous (offline) session.
void flushCommentQueue();
