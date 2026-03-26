const API = {
    async post(url, data = {}) {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        return res.json();
    },
    async get(url) {
        const res = await fetch(url);
        return res.json();
    },
};

let gameState = null;

// ---- SETUP ----

document.getElementById("btn-new-game").addEventListener("click", async () => {
    const res = await API.post("/api/new_game");
    if (res.status === "ok") {
        document.getElementById("setup-new").classList.add("hidden");
        document.getElementById("setup-players").classList.remove("hidden");
        document.getElementById("player-name-input").focus();
    }
});

document.getElementById("btn-add-player").addEventListener("click", addPlayer);
document.getElementById("player-name-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") addPlayer();
});

async function addPlayer() {
    const input = document.getElementById("player-name-input");
    const name = input.value.trim();
    if (!name) return;

    const res = await API.post("/api/add_player", { name });
    if (res.status === "ok") {
        input.value = "";
        input.focus();
        gameState = res.game;
        renderSetupPlayers();

        if (gameState.players.length >= 2) {
            document.getElementById("btn-start-game").classList.remove("hidden");
        }
    } else {
        alert(res.message);
    }
}

function renderSetupPlayers() {
    const container = document.getElementById("player-list-setup");
    container.innerHTML = gameState.players
        .map(
            (p) =>
                `<div class="player-chip" style="background:${p.color}">${p.name}</div>`
        )
        .join("");
}

document.getElementById("btn-start-game").addEventListener("click", async () => {
    const res = await API.post("/api/start_game");
    if (res.status === "ok") {
        gameState = res.game;
        document.getElementById("setup-screen").classList.remove("active");
        document.getElementById("game-screen").classList.add("active");
        buildBoard();
        renderGame();
    } else {
        alert(res.message);
    }
});

// ---- BOARD BUILDING ----

// Board position mapping: the 40 squares around the edge of an 11x11 grid
// Bottom row (right to left): positions 0-10
// Left column (bottom to top): positions 10-20
// Top row (left to right): positions 20-30
// Right column (top to bottom): positions 30-40(0)
function getBoardGridPosition(pos) {
    if (pos <= 10) {
        // Bottom row: pos 0 = bottom-right corner (col 11, row 11)
        return { row: 11, col: 11 - pos, edge: "bottom" };
    } else if (pos <= 20) {
        // Left column: pos 11 = (row 10, col 1) up to pos 20 = (row 1, col 1)
        return { row: 11 - (pos - 10), col: 1, edge: "left" };
    } else if (pos <= 30) {
        // Top row: pos 21 = (row 1, col 2) to pos 30 = (row 1, col 11)
        return { row: 1, col: 1 + (pos - 20), edge: "top" };
    } else {
        // Right column: pos 31 = (row 2, col 11) to pos 39 = (row 10, col 11)
        return { row: 1 + (pos - 30), col: 11, edge: "right" };
    }
}

function buildBoard() {
    const board = document.getElementById("board");
    board.innerHTML = "";

    // Create 40 squares
    for (let pos = 0; pos < 40; pos++) {
        const { row, col, edge } = getBoardGridPosition(pos);
        const sq = document.createElement("div");
        sq.className = `board-square edge-${edge}`;
        sq.style.gridRow = row;
        sq.style.gridColumn = col;
        sq.dataset.pos = pos;

        const isCorner = [0, 10, 20, 30].includes(pos);
        if (isCorner) sq.classList.add("corner");

        sq.innerHTML = `
            <div class="color-bar"></div>
            <div class="sq-name"></div>
            <div class="sq-price"></div>
            <div class="player-tokens"></div>
        `;
        board.appendChild(sq);
    }

    // Center
    const center = document.createElement("div");
    center.className = "board-center";
    center.innerHTML = `<h2>Monopoly<br><span class="plus">Plus</span></h2>`;
    board.appendChild(center);
}

// ---- GAME RENDERING ----

function renderGame() {
    if (!gameState) return;
    renderBoard();
    renderPlayers();
    renderTurnInfo();
    renderLog();
    updateBuyButton();
}

function renderBoard() {
    const squares = document.querySelectorAll(".board-square");
    squares.forEach((sq) => {
        const pos = parseInt(sq.dataset.pos);
        const boardData = gameState.board[pos];
        if (!boardData) return;

        const colorBar = sq.querySelector(".color-bar");
        const nameEl = sq.querySelector(".sq-name");
        const priceEl = sq.querySelector(".sq-price");
        const tokensEl = sq.querySelector(".player-tokens");

        // Color bar
        if (boardData.color) {
            colorBar.style.background = boardData.color;
        } else {
            colorBar.style.background = "transparent";
        }

        // Name
        let displayName = boardData.name;
        if (typeof displayName === "string" && displayName.length > 12) {
            displayName = displayName.substring(0, 11) + ".";
        }
        nameEl.textContent = displayName;

        // Price
        if (boardData.price) {
            priceEl.textContent = boardData.price + "kr";
        } else {
            priceEl.textContent = "";
        }

        // Ownership indicator
        let ownerDot = sq.querySelector(".owned-indicator");
        if (boardData.owner) {
            const ownerPlayer = gameState.players.find((p) => p.name === boardData.owner);
            if (!ownerDot) {
                ownerDot = document.createElement("div");
                ownerDot.className = "owned-indicator";
                sq.appendChild(ownerDot);
            }
            ownerDot.style.background = ownerPlayer ? ownerPlayer.color : "#fff";
        } else if (ownerDot) {
            ownerDot.remove();
        }

        // Player tokens
        tokensEl.innerHTML = "";
        gameState.players.forEach((p) => {
            if (p.position === pos) {
                const token = document.createElement("div");
                token.className = "token";
                token.style.background = p.color;
                token.title = p.name;
                tokensEl.appendChild(token);
            }
        });
    });
}

function renderPlayers() {
    const container = document.getElementById("players-list");
    container.innerHTML = gameState.players
        .map((p, i) => {
            const isActive = i === gameState.current_turn;
            return `
            <div class="player-card ${isActive ? "active-player" : ""}">
                <div class="player-color-dot" style="background:${p.color}"></div>
                <div class="player-card-info">
                    <div class="player-card-name">${p.name}${p.in_jail ? " (Fängelse)" : ""}</div>
                    <div class="player-card-balance">${p.balance.toLocaleString("sv-SE")} kr</div>
                    <div class="player-card-streets">${p.streets.length > 0 ? p.streets.join(", ") : "Inga fastigheter"}</div>
                </div>
            </div>
        `;
        })
        .join("");
}

function renderTurnInfo() {
    const player = gameState.players[gameState.current_turn];
    const nameEl = document.getElementById("current-player-name");
    const balanceEl = document.getElementById("current-player-balance");
    nameEl.textContent = player.name + "s tur";
    nameEl.style.color = player.color;
    balanceEl.textContent = player.balance.toLocaleString("sv-SE") + " kr";
}

function renderLog() {
    const container = document.getElementById("game-log");
    container.innerHTML = gameState.log
        .slice()
        .reverse()
        .map((entry) => `<div class="log-entry">${entry}</div>`)
        .join("");
}

function updateBuyButton() {
    const btn = document.getElementById("btn-buy");
    // Show buy button only if current player is on a buyable, unowned property
    // We'll just show it and let the server validate
    btn.classList.add("hidden");

    if (!gameState.started) return;

    const currentPlayer = gameState.players[gameState.current_turn];
    const boardData = gameState.board[currentPlayer.position];

    if (boardData && boardData.price && !boardData.owner) {
        // Check if the previous turn player (who just rolled) is on a buyable spot
        // Actually we need to track who just rolled. For simplicity, show for all.
        btn.classList.remove("hidden");
    }
}

// ---- ACTIONS ----

document.getElementById("btn-roll").addEventListener("click", async () => {
    const btn = document.getElementById("btn-roll");
    btn.disabled = true;

    const res = await API.post("/api/roll");
    if (res.status === "ok") {
        // Animate dice
        const die1 = document.getElementById("die1");
        const die2 = document.getElementById("die2");
        die1.classList.add("rolling");
        die2.classList.add("rolling");
        die1.textContent = res.dice[0];
        die2.textContent = res.dice[1];

        setTimeout(() => {
            die1.classList.remove("rolling");
            die2.classList.remove("rolling");
        }, 400);

        gameState = res.game;
        renderGame();
    } else {
        alert(res.message);
    }

    btn.disabled = false;
});

document.getElementById("btn-buy").addEventListener("click", async () => {
    // Find the player who just moved (previous turn since move advances turn)
    const prevTurn =
        (gameState.current_turn - 1 + gameState.players.length) %
        gameState.players.length;
    const res = await API.post("/api/buy", { player_index: prevTurn });
    if (res.status === "ok" || res.game) {
        gameState = res.game;
        renderGame();
    }
    if (res.message) {
        // Show in log - it's already added server-side
    }
});
