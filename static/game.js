// Browser side of the game. The server holds the real state; this file
// asks for it every second, draws it, and sends clicks back to the server.

const CODE = document.body.dataset.code;
const TOKEN = document.body.dataset.token;
const API = `/api/game/${CODE}/${TOKEN}`;
const SIZE = 10;
const ROWS = "ABCDEFGHIJ";

let state = null;        // latest state from the server
let lastJson = "";       // used to skip redrawing when nothing changed
let placement = [];      // ships placed in this browser before pressing Ready
let horizontal = true;
let hover = null;        // {row, col} under the mouse while placing
let busy = false;

const $ = (id) => document.getElementById(id);

// ---------- Talking to the server ----------

async function request(url, options = {}) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    throw new Error("Can't reach the server. Check that Flask is still running.");
  }
  let data = {};
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) throw new Error(data.error || `The server answered with error ${res.status}.`);
  return data;
}

function post(path, body) {
  return request(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function poll() {
  try {
    const data = await request(`${API}/state`);
    $("connection").hidden = true;
    const json = JSON.stringify(data);
    if (json !== lastJson) {
      lastJson = json;
      state = data;
      render();
    }
  } catch (err) {
    $("connection").textContent = err.message;
    $("connection").hidden = false;
  }
}

let flashTimer;
function flash(message) {
  $("flash").textContent = message;
  $("flash").hidden = false;
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => { $("flash").hidden = true; }, 4000);
}

// ---------- Drawing the boards ----------

function labelCell(text) {
  const div = document.createElement("div");
  div.className = "label";
  div.textContent = text;
  return div;
}

function buildGrid(el, onClick, onHover) {
  el.appendChild(labelCell(""));
  for (let c = 0; c < SIZE; c++) el.appendChild(labelCell(c + 1));
  for (let r = 0; r < SIZE; r++) {
    el.appendChild(labelCell(ROWS[r]));
    for (let c = 0; c < SIZE; c++) {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cell empty";
      cell.dataset.row = r;
      cell.dataset.col = c;
      cell.setAttribute("aria-label", ROWS[r] + (c + 1));
      cell.addEventListener("click", () => onClick(r, c));
      if (onHover) {
        cell.addEventListener("mouseenter", () => onHover({ row: r, col: c }));
        cell.addEventListener("focus", () => onHover({ row: r, col: c }));
      }
      el.appendChild(cell);
    }
  }
  if (onHover) el.addEventListener("mouseleave", () => onHover(null));
}

function paint(el, grid) {
  el.querySelectorAll(".cell").forEach((cell) => {
    cell.className = "cell " + grid[cell.dataset.row][cell.dataset.col];
  });
}

// ---------- Placing ships ----------

function isPlacing() {
  return state && ["waiting", "placing"].includes(state.phase) && !state.you.ready;
}

function sizeOf(name) {
  return state.fleet.find((s) => s.name === name).size;
}

function cellsFor(row, col, size, horiz) {
  return Array.from({ length: size }, (_, i) => (horiz ? [row, col + i] : [row + i, col]));
}

function takenCells() {
  const taken = new Set();
  for (const ship of placement) {
    for (const [r, c] of cellsFor(ship.row, ship.col, sizeOf(ship.name), ship.horizontal)) {
      taken.add(`${r},${c}`);
    }
  }
  return taken;
}

function fits(cells, taken) {
  return cells.every(([r, c]) => r >= 0 && r < SIZE && c >= 0 && c < SIZE && !taken.has(`${r},${c}`));
}

function nextShip() {
  return state.fleet[placement.length];
}

function renderMyBoard() {
  if (!state) return;
  if (!isPlacing()) {
    paint($("my-board"), state.my_board);
    return;
  }
  const grid = Array.from({ length: SIZE }, () => Array(SIZE).fill("empty"));
  const taken = takenCells();
  for (const key of taken) {
    const [r, c] = key.split(",").map(Number);
    grid[r][c] = "ship";
  }
  const ship = nextShip();
  if (ship && hover) {
    const cells = cellsFor(hover.row, hover.col, ship.size, horizontal);
    const ok = fits(cells, taken);
    for (const [r, c] of cells) {
      if (r < SIZE && c < SIZE) grid[r][c] = ok ? "preview" : "preview-bad";
    }
  }
  paint($("my-board"), grid);
}

function renderPlacementControls() {
  const ship = nextShip();
  $("placing-label").textContent = ship
    ? `Click your waters to place the ${ship.name}, ${ship.size} squares, ${horizontal ? "across" : "down"}. Press R to rotate.`
    : "All ships are placed. Press I'm ready when you're happy with the layout.";
  $("rotate").textContent = horizontal ? "Rotate to vertical" : "Rotate to horizontal";
  $("ready").disabled = placement.length !== state.fleet.length;
}

function onMyBoardClick(row, col) {
  if (!isPlacing()) return;
  const ship = nextShip();
  if (!ship) return;
  const cells = cellsFor(row, col, ship.size, horizontal);
  if (!fits(cells, takenCells())) {
    flash(`The ${ship.name} doesn't fit there.`);
    return;
  }
  placement.push({ name: ship.name, row, col, horizontal });
  renderMyBoard();
  renderPlacementControls();
}

function rotate() {
  horizontal = !horizontal;
  renderMyBoard();
  renderPlacementControls();
}

$("rotate").addEventListener("click", rotate);
document.addEventListener("keydown", (e) => {
  if ((e.key === "r" || e.key === "R") && isPlacing()) rotate();
});

$("reset").addEventListener("click", () => {
  placement = [];
  renderMyBoard();
  renderPlacementControls();
});

$("randomize").addEventListener("click", async () => {
  try {
    const data = await request("/api/random-fleet");
    placement = data.ships;
    renderMyBoard();
    renderPlacementControls();
  } catch (err) {
    flash(err.message);
  }
});

$("ready").addEventListener("click", async () => {
  try {
    await post("/place", { ships: placement });
    await poll();
  } catch (err) {
    flash(err.message);
  }
});

// ---------- Firing ----------

async function onTargetClick(row, col) {
  if (!state || busy) return;
  if (!state.your_turn) {
    flash(state.phase === "playing" ? "Wait for your turn." : "The battle hasn't started.");
    return;
  }
  if (state.target_board[row][col] !== "empty") {
    flash(`You already fired at ${ROWS[row]}${col + 1}.`);
    return;
  }
  busy = true;
  try {
    await post("/fire", { row, col });
    await poll();
  } catch (err) {
    flash(err.message);
  } finally {
    busy = false;
  }
}

// ---------- Putting it all on screen ----------

function statusText() {
  const opp = state.opponent ? state.opponent.name : "your opponent";
  switch (state.phase) {
    case "waiting":
      return state.you.ready
        ? "Your fleet is ready. Waiting for an opponent to join."
        : "Waiting for an opponent. Place your ships while you wait.";
    case "placing":
      return state.you.ready ? `Waiting for ${opp} to place their ships.` : "Place your ships.";
    case "playing":
      return state.your_turn ? "Your turn. Pick a square in the enemy waters." : `${opp} is aiming…`;
    case "over":
      return state.winner === "you" ? "You sank the whole fleet. You win!" : `${opp} sank your fleet. Better luck next game.`;
  }
  return "";
}

function renderFleet(el, sunkNames) {
  el.innerHTML = "";
  for (const ship of state.fleet) {
    const li = document.createElement("li");
    li.textContent = ship.name;
    const size = document.createElement("span");
    size.textContent = ship.size;
    li.appendChild(size);
    if (sunkNames.includes(ship.name)) li.className = "sunk";
    el.appendChild(li);
  }
}

function render() {
  $("status").textContent = statusText();
  $("status").classList.toggle("your-turn", state.your_turn);
  $("event").textContent = state.last_event;
  $("share").hidden = state.phase !== "waiting";
  $("placement").hidden = !isPlacing();
  $("again").hidden = state.phase !== "over";
  $("target-caption").textContent = state.opponent ? `${state.opponent.name}'s waters` : "Enemy waters";
  $("target-board").classList.toggle("active", state.your_turn);
  if (isPlacing()) renderPlacementControls();
  renderMyBoard();
  paint($("target-board"), state.target_board);
  renderFleet($("my-fleet"), state.my_sunk);
  renderFleet($("enemy-fleet"), state.opponent_sunk);
}

buildGrid($("my-board"), onMyBoardClick, (cell) => { hover = cell; renderMyBoard(); });
buildGrid($("target-board"), onTargetClick);
poll();
setInterval(poll, 1000);
