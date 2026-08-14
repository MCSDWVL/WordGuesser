const DATA_URL = "data/game-data.json";
const ROUNDS = 5;

export function utcDateSeed(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

export function resolveSeed(search = window.location.search, date = new Date()) {
  const supplied = new URLSearchParams(search).get("seed")?.trim();
  return supplied || utcDateSeed(date);
}

// xmur3 + mulberry32: compact, deterministic non-cryptographic randomness.
export function seededRandom(seed) {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i += 1) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  h = (h ^ (h >>> 16)) >>> 0;
  return () => {
    h = (h + 0x6D2B79F5) >>> 0;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function takeUnique(items, count, random) {
  if (items.length < count) throw new Error(`Need ${count} entries, received ${items.length}.`);
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, count);
}

export function buildRounds(data, seed) {
  const random = seededRandom(seed);
  const realCount = random() < 0.5 ? 2 : 3;
  const rounds = [
    ...takeUnique(data.words, realCount, random).map((entry) => ({ ...entry, kind: "real" })),
    ...takeUnique(data.fakes, ROUNDS - realCount, random).map((word) => ({ word, kind: "fake" })),
  ];
  return takeUnique(rounds, rounds.length, random);
}

const elements = typeof document === "undefined" ? {} : {
  seedLabel: document.querySelector("#seed-label"), status: document.querySelector("#status"),
  content: document.querySelector("#round-content"), progress: document.querySelector("#progress"),
  word: document.querySelector("#word"), choices: document.querySelector("#choices"),
  feedback: document.querySelector("#feedback"), next: document.querySelector("#next"),
  result: document.querySelector("#result"), score: document.querySelector("#score"),
  resultCopy: document.querySelector("#result-copy"), replay: document.querySelector("#replay"),
};

let state;

function renderRound() {
  const round = state.rounds[state.index];
  elements.progress.textContent = `Word ${state.index + 1} of ${ROUNDS}`;
  elements.word.textContent = round.word;
  elements.feedback.textContent = "";
  elements.feedback.className = "feedback";
  elements.next.hidden = true;
  elements.choices.querySelectorAll("button").forEach((button) => { button.disabled = false; });
}

function answer(choice) {
  if (state.answered) return;
  state.answered = true;
  const round = state.rounds[state.index];
  const correct = choice === round.kind;
  if (correct) state.score += 1;
  elements.choices.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  elements.feedback.className = `feedback ${correct ? "correct" : "incorrect"}`;
  const verdict = document.createElement("strong");
  verdict.textContent = correct ? "Correct." : "Not quite.";
  elements.feedback.replaceChildren(verdict, document.createTextNode(" "));
  if (round.kind === "real") {
    const definition = document.createElement("span");
    definition.className = "definition";
    const word = document.createElement("strong");
    word.textContent = round.word;
    definition.append(word, document.createTextNode(`: ${round.definition}`));
    elements.feedback.append(definition);
  } else {
    elements.feedback.append("It was an invented word.");
  }
  elements.next.textContent = state.index === ROUNDS - 1 ? "See score" : "Next word";
  elements.next.hidden = false;
  elements.next.focus();
}

function advance() {
  if (!state.answered) return;
  state.index += 1;
  state.answered = false;
  if (state.index < ROUNDS) return renderRound();
  elements.content.hidden = true;
  elements.result.hidden = false;
  elements.score.textContent = `${state.score} / ${ROUNDS}`;
  elements.resultCopy.textContent = `Seed: ${state.seed}`;
  elements.replay.focus();
}

function start(data, seed) {
  state = { seed, rounds: buildRounds(data, seed), index: 0, score: 0, answered: false };
  elements.status.hidden = true;
  elements.result.hidden = true;
  elements.content.hidden = false;
  elements.seedLabel.textContent = `Puzzle seed: ${seed}`;
  renderRound();
}

async function boot() {
  const seed = resolveSeed();
  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) throw new Error("Game data is not available.");
    const data = await response.json();
    if (!Array.isArray(data.words) || !Array.isArray(data.fakes)) throw new Error("Game data has an invalid format.");
    start(data, seed);
    elements.choices.addEventListener("click", (event) => {
      const choice = event.target.closest("button")?.dataset.answer;
      if (choice) answer(choice);
    });
    elements.next.addEventListener("click", advance);
    elements.replay.addEventListener("click", () => start(data, seed));
  } catch (error) {
    elements.status.textContent = `${error.message} Run the offline builder described in README.md, then serve this folder over HTTP.`;
  }
}

if (typeof document !== "undefined") boot();
