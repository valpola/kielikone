const PROMPT = document.getElementById("prompt");
const ANSWER = document.getElementById("answer");
const REVEAL = document.getElementById("reveal");
const NEXT = document.getElementById("next");
const RESULT = document.getElementById("result");
const CORRECT = document.getElementById("correct");
const USER_ANSWER = document.getElementById("user-answer");
const COUNT = document.getElementById("count");
const STATS = document.getElementById("stats");
const MARK_CORRECT = document.getElementById("mark-correct");
const MARK_WRONG = document.getElementById("mark-wrong");
const MODE_BTNS = document.querySelectorAll(".mode-btn");

let mode = "tr-en";
let items = [];
let current = null;
let seen = 0;
let correct = 0;

const storageKey = (id) => `tr-quiz-${id}`;

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

const getResultsEndpoint = () => {
  if (typeof APP_CONFIG === "undefined") return "";
  if (!APP_CONFIG.resultsEnabled) return "";
  return APP_CONFIG.resultsEndpoint || "";
};

const sendResult = async (payload) => {
  const endpoint = getResultsEndpoint();
  if (!endpoint) return;

  const body = new URLSearchParams();
  Object.entries(payload).forEach(([key, value]) => {
    body.set(key, String(value));
  });

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
  if (!items.length) return null;

  const weighted = items.map((item) => ({
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

const updateStats = () => {
  COUNT.textContent = `${items.length} items`;
  STATS.textContent = `${correct}/${seen} correct`;
};

const renderPrompt = () => {
  current = pickNext();
  if (!current) {
    PROMPT.textContent = "No items loaded";
    return;
  }

  const promptText = mode === "tr-en" ? current.turkish : current.english;
  PROMPT.textContent = promptText;
  ANSWER.value = "";
  RESULT.classList.add("hidden");
  ANSWER.focus();
};

const revealAnswer = () => {
  if (!current) return;
  const correctText = mode === "tr-en" ? current.english : current.turkish;
  CORRECT.textContent = correctText;
  USER_ANSWER.textContent = ANSWER.value || "(no answer)";
  RESULT.classList.remove("hidden");
};

const grade = (isCorrect) => {
  if (!current) return;
  const stats = getLocalStats(current.id);
  stats.lastSeen = todayStamp();
  if (isCorrect) stats.correct += 1;
  else stats.wrong += 1;
  setLocalStats(current.id, stats);

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

REVEAL.addEventListener("click", revealAnswer);
NEXT.addEventListener("click", renderPrompt);
MARK_CORRECT.addEventListener("click", () => grade(true));
MARK_WRONG.addEventListener("click", () => grade(false));

window.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    revealAnswer();
  }
});

const loadData = async () => {
  const response = await fetch("data/quiz.json");
  const data = await response.json();
  items = data.items || [];
  renderMode();
  updateStats();
  renderPrompt();
};

loadData().catch(() => {
  PROMPT.textContent = "Failed to load data/quiz.json";
});
