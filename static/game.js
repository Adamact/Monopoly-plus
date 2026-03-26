const API = {
    async post(url, data = {}) {
        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
            });
            return res.json();
        } catch (e) {
            return { status: "error", message: "Kunde inte na servern." };
        }
    },
    async get(url) {
        try {
            const res = await fetch(url);
            return res.json();
        } catch (e) {
            return { status: "error", message: "Kunde inte na servern." };
        }
    },
};

let gameState = null;
let socket = null;
let myPlayer = null;
let currentGameId = null;

// ── Socket ──────────────────────────────────────────────────────────────

function connectSocket(gameId) {
    currentGameId = gameId;
    if (socket) socket.disconnect();
    socket = io();

    socket.on("connect", () => {
        socket.emit("join_game_room", { game_id: gameId });
        setConnectionStatus(true);
    });

    socket.on("disconnect", () => {
        setConnectionStatus(false);
    });

    socket.on("connect_error", () => {
        setConnectionStatus(false);
    });

    socket.on("game_update", (data) => {
        gameState = data.game;

        // If on claim screen, re-render player list
        const claimPanel = document.getElementById("setup-claim");
        if (claimPanel && !claimPanel.classList.contains("hidden")) {
            renderClaimPlayers();
        }

        // If on setup-players screen (host lobby), update player list
        const playersPanel = document.getElementById("setup-players");
        if (playersPanel && !playersPanel.classList.contains("hidden")) {
            renderSetupPlayers();
            if (gameState.players.length >= 2) show("btn-start-game");
        }

        // If game started and I have claimed a player, transition to game screen
        if (gameState.started && myPlayer) {
            document.getElementById("setup-screen").classList.remove("active");
            document.getElementById("game-screen").classList.add("active");
        }

        // If game screen is active, re-render
        if (document.getElementById("game-screen").classList.contains("active")) {
            renderGame();
        }
    });
}

function setConnectionStatus(connected) {
    const el = document.getElementById("connection-status");
    if (!el) return;
    el.className = "connection-status " + (connected ? "connected" : "disconnected");
    el.title = connected ? "Ansluten" : "Frkopplad";
}

// ── Helpers ──────────────────────────────────────────────────────────────

function show(id) { document.getElementById(id).classList.remove("hidden"); }
function hide(id) { document.getElementById(id).classList.add("hidden"); }
function fmt(n) { return Number(n).toLocaleString("sv-SE"); }

function toast(msg, isError = false) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = "toast " + (isError ? "error" : "success");
    setTimeout(() => el.classList.add("hidden"), 3500);
}

function populateSelect(id, options) {
    const sel = document.getElementById(id);
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = options.map(o => `<option value="${o.value}">${o.label}</option>`).join("");
    if (prev && options.some(o => String(o.value) === prev)) sel.value = prev;
}

function playerOpts() {
    if (!gameState) return [];
    return gameState.players
        .filter(p => !p.eliminated)
        .map(p => ({
            value: p.name,
            label: `${p.name} (${fmt(p.balance)} kr)${p.distressed ? " [!]" : ""}`
        }));
}

function refreshSelects() {
    const opts = playerOpts();
    [
        "prop-player", "rent-player", "share-owner", "share-buyer",
        "trade-seller", "trade-buyer", "trade-company",
        "bank-loan-player", "ploan-lender", "ploan-borrower",
        "ins-insurer", "ins-insured", "claim-player",
        "money-from", "money-to", "adjust-player", "distress-player"
    ].forEach(id => populateSelect(id, opts));

    if (gameState.all_streets) {
        populateSelect("prop-street", gameState.all_streets.map(s => ({
            value: s.name,
            label: `${s.name} (${s.group}) — ${fmt(s.price)} kr`
        })));
    }

    const contracts = (gameState.insurance_contracts || []).map(c => ({
        value: c.id,
        label: `#${c.id}: ${c.insurer} -> ${c.insured} (${fmt(c.coverage_remaining)} kr kvar)`
    }));
    populateSelect("claim-contract", contracts.length ? contracts : [{ value: "", label: "Inga avtal" }]);

    if (myPlayer) {
        ["prop-player", "rent-player", "bank-loan-player", "adjust-player",
         "distress-player", "ins-insured", "claim-player", "ploan-borrower",
         "money-from"].forEach(id => {
            const sel = document.getElementById(id);
            if (sel) sel.value = myPlayer;
        });
    }
}

// ── Button loading state ────────────────────────────────────────────────

function setLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    if (loading) {
        btn.dataset.originalText = btn.textContent;
        btn.textContent = "...";
    } else if (btn.dataset.originalText) {
        btn.textContent = btn.dataset.originalText;
        delete btn.dataset.originalText;
    }
}

// ── Page refresh recovery ───────────────────────────────────────────────

async function tryRecoverSession() {
    const res = await API.get("/api/state");
    if (res.status !== "ok" || !res.game) return;

    gameState = res.game;
    currentGameId = res.game_id;
    myPlayer = res.my_player || null;

    if (currentGameId) {
        connectSocket(currentGameId);
    }

    if (gameState.started && myPlayer) {
        document.getElementById("setup-screen").classList.remove("active");
        document.getElementById("game-screen").classList.add("active");
        renderGame();
    } else if (gameState.started && !myPlayer) {
        hide("setup-new");
        showClaimScreen(currentGameId);
    } else if (currentGameId && !gameState.started) {
        hide("setup-new");
        showClaimScreen(currentGameId);
    }
}

tryRecoverSession();

// ── Setup ────────────────────────────────────────────────────────────────

document.getElementById("btn-new-game").addEventListener("click", async function() {
    setLoading(this, true);
    const res = await API.post("/api/new_game");
    setLoading(this, false);
    if (res.status === "ok") {
        hide("setup-new");
        show("setup-players");
        document.getElementById("lobby-game-id").textContent = res.game_id;
        connectSocket(res.game_id);
        document.getElementById("player-name-input").focus();
    } else {
        toast(res.message, true);
    }
});

document.getElementById("btn-join-game").addEventListener("click", async function() {
    const input = document.getElementById("join-game-id");
    const gameId = input.value.trim();
    if (!gameId || !/^\d{5}$/.test(gameId)) {
        toast("Ange en giltig 5-siffrig spelkod.", true);
        input.focus();
        return;
    }
    setLoading(this, true);
    const res = await API.post("/api/join_game", { game_id: gameId });
    setLoading(this, false);
    if (res.status === "ok") {
        gameState = res.game;
        hide("setup-new");
        connectSocket(gameId);
        showClaimScreen(gameId);
    } else {
        toast(res.message || "Spelet hittades inte.", true);
        input.focus();
    }
});

document.getElementById("join-game-id").addEventListener("keydown", e => {
    if (e.key === "Enter") document.getElementById("btn-join-game").click();
});

document.getElementById("join-game-id").addEventListener("input", function() {
    this.value = this.value.replace(/\D/g, "");
});

function showClaimScreen(gameId) {
    show("setup-claim");
    document.getElementById("display-game-id").textContent = gameId;
    renderClaimPlayers();
}

function renderClaimPlayers() {
    if (!gameState) return;
    const container = document.getElementById("claim-player-list");
    const claimed = gameState.claimed_players || [];
    container.innerHTML = gameState.players.map(p => {
        const isClaimed = claimed.includes(p.name);
        const isMe = p.name === myPlayer;
        return `<button class="btn ${isMe ? 'btn-primary' : isClaimed ? 'btn-ghost' : 'btn-secondary'} claim-btn"
                    ${isClaimed && !isMe ? 'disabled' : ''}
                    onclick="claimPlayer('${p.name}')">
                    <span class="player-chip-mini" style="background:${p.color}"></span>
                    ${p.name} ${isMe ? '(du)' : isClaimed ? '(tagen)' : ''}
                </button>`;
    }).join("");

    const unclaimArea = document.getElementById("unclaim-area");
    if (unclaimArea) {
        if (myPlayer && !gameState.started) {
            unclaimArea.innerHTML = `<button class="btn btn-ghost btn-small" onclick="unclaimPlayer()">Byt spelare</button>`;
        } else {
            unclaimArea.innerHTML = "";
        }
    }

    const waitingEl = document.getElementById("claim-waiting");
    if (waitingEl) {
        waitingEl.style.display = gameState.started ? "none" : "block";
    }
}

async function claimPlayer(name) {
    if (name === myPlayer) return;
    const res = await API.post("/api/claim_player", { name });
    if (res.status === "ok") {
        myPlayer = name;
        renderClaimPlayers();
        if (gameState && gameState.started) {
            document.getElementById("setup-screen").classList.remove("active");
            document.getElementById("game-screen").classList.add("active");
            renderGame();
        }
    } else {
        toast(res.message, true);
    }
}

async function unclaimPlayer() {
    const res = await API.post("/api/unclaim_player");
    if (res.status === "ok") {
        myPlayer = null;
        renderClaimPlayers();
    } else {
        toast(res.message, true);
    }
}

document.getElementById("btn-add-player").addEventListener("click", addPlayer);
document.getElementById("player-name-input").addEventListener("keydown", e => {
    if (e.key === "Enter") addPlayer();
});

async function addPlayer() {
    const input = document.getElementById("player-name-input");
    const name = input.value.trim();
    if (!name) return;
    const btn = document.getElementById("btn-add-player");
    setLoading(btn, true);
    const res = await API.post("/api/add_player", { name });
    setLoading(btn, false);
    if (res.status === "ok") {
        input.value = "";
        input.focus();
        gameState = res.game;
        renderSetupPlayers();
        if (gameState.players.length >= 2) show("btn-start-game");
    } else {
        toast(res.message, true);
    }
}

function renderSetupPlayers() {
    document.getElementById("player-list-setup").innerHTML = gameState.players
        .map(p => `<div class="player-chip" style="background:${p.color}">${p.name}</div>`)
        .join("");
}

document.getElementById("btn-start-game").addEventListener("click", async function() {
    if (!myPlayer && gameState && gameState.players.length > 0) {
        const claimed = gameState.claimed_players || [];
        const unclaimed = gameState.players.find(p => !claimed.includes(p.name));
        if (unclaimed) {
            const claimRes = await API.post("/api/claim_player", { name: unclaimed.name });
            if (claimRes.status === "ok") myPlayer = unclaimed.name;
        }
    }
    setLoading(this, true);
    const res = await API.post("/api/start_game");
    setLoading(this, false);
    if (res.status === "ok") {
        gameState = res.game;
        document.getElementById("setup-screen").classList.remove("active");
        document.getElementById("game-screen").classList.add("active");
        renderGame();
    } else {
        toast(res.message, true);
    }
});

// ── Copy game ID ────────────────────────────────────────────────────────

// Copy game code when clicking the game-code-display area
document.addEventListener("click", async (e) => {
    const codeWrap = e.target.closest(".game-code-display");
    if (codeWrap) {
        const codeEl = codeWrap.querySelector(".game-code");
        const gameId = codeEl ? codeEl.textContent.trim() : currentGameId;
        if (gameId) {
            try {
                await navigator.clipboard.writeText(gameId);
                toast("Spelkod kopierad!");
            } catch {
                toast("Kunde inte kopiera.", true);
            }
        }
    }
});

// ── Tabs ─────────────────────────────────────────────────────────────────

document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
        tab.classList.add("active");
        const content = document.getElementById("tab-" + tab.dataset.tab);
        content.classList.add("active");
        content.scrollTop = 0;
    });
});

// ── Rendering ────────────────────────────────────────────────────────────

function renderGame() {
    if (!gameState) return;
    refreshSelects();
    renderDashboard();
    renderShareOverview();
    renderLoans();
    renderInsurance();
    renderLog();
}

function renderDashboard() {
    document.getElementById("round-number").textContent = gameState.current_round;
    renderMarketPreview();
    renderPlayers();
}

function renderMarketPreview() {
    const el = document.getElementById("market-preview");
    if (!el || !gameState) { if (el) el.innerHTML = ""; return; }

    const items = [];
    const contracts = gameState.insurance_contracts || [];
    if (contracts.length > 0) {
        const totalPremiums = contracts.reduce((sum, c) => sum + c.premium_per_round, 0);
        items.push(`&#9730; ${contracts.length} forsakring${contracts.length > 1 ? 'ar' : ''}: ${fmt(totalPremiums)} kr i premier`);
    }

    let totalDebt = 0;
    let loanCount = 0;
    gameState.players.forEach(p => {
        p.bank_loans.forEach(l => { totalDebt += Math.round(l.remaining * 0.05); loanCount++; });
    });
    if (loanCount > 0) {
        items.push(`&#9734; ${loanCount} banklan: +${fmt(totalDebt)} kr skuld`);
    }

    const distressed = gameState.players.filter(p => p.distressed && !p.eliminated);
    if (distressed.length > 0) {
        items.push(`&#9888; ${distressed.map(p => p.name).join(", ")} ar distressed`);
    }

    el.innerHTML = items.length > 0
        ? items.map(i => `<div class="market-preview-item">${i}</div>`).join("")
        : "";
}

function renderPlayers() {
    const sorted = [...gameState.players].sort((a, b) => {
        if (a.name === myPlayer) return -1;
        if (b.name === myPlayer) return 1;
        return 0;
    });
    document.getElementById("players-list").innerHTML = sorted.map(p => {
        const statusBadge = p.eliminated ? '<span class="badge badge-dead">Eliminerad</span>'
            : p.distressed ? `<span class="badge badge-warn">Distressed (${p.distress_rounds_left}r)</span>` : "";

        const shareholderList = Object.entries(p.shareholders)
            .map(([name, count]) => `${name}: ${count}st`).join(", ") || "Inga";

        const props = p.properties.length > 0 ? p.properties.join(", ") : "Inga";

        const isMe = p.name === myPlayer;
        return `
            <div class="player-card ${p.eliminated ? 'eliminated' : ''} ${isMe ? 'my-player' : ''}" style="border-left-color:${p.color}">
                <div class="player-color-dot" style="background:${p.color}"></div>
                <div class="player-card-info">
                    <div class="player-card-name">${p.name} ${isMe ? '<span class="you-badge">Du</span>' : ''} ${statusBadge}</div>
                    <div class="player-card-balance">${fmt(p.balance)} kr</div>
                    <div class="player-card-meta">
                        Nettovarde: ${fmt(p.net_worth)} kr | Skuld: ${fmt(p.total_debt)} kr
                    </div>
                    <div class="player-card-meta">
                        Fastigheter (${fmt(p.property_value)} kr): ${props}
                    </div>
                    <div class="player-card-meta">
                        Aktier: ${p.shares_issued}/${p.max_shares} emitterade (${fmt(p.share_price)} kr/st) |
                        Agare: ${shareholderList}
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderShareOverview() {
    const container = document.getElementById("share-overview");
    if (!container) return;

    const rows = [];
    gameState.players.filter(p => !p.eliminated).forEach(company => {
        if (company.shares_issued === 0) return;
        Object.entries(company.shareholders).forEach(([holder, count]) => {
            rows.push({
                company: company.name, holder, count,
                value: count * company.share_price,
                price: company.share_price,
            });
        });
    });

    if (rows.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">&#9650;</div><div class="empty-state-text">Inga aktier emitterade an.</div></div>';
        return;
    }

    container.innerHTML = `
        <table class="data-table">
            <thead><tr><th>Bolag</th><th>Agare</th><th>Antal</th><th>Kurs</th><th>Varde</th></tr></thead>
            <tbody>
                ${rows.map(r => `<tr>
                    <td>${r.company}</td><td>${r.holder}</td>
                    <td>${r.count}</td><td>${fmt(r.price)} kr</td>
                    <td>${fmt(r.value)} kr</td>
                </tr>`).join("")}
            </tbody>
        </table>
    `;

    const owner = document.getElementById("share-owner");
    if (owner && owner.value) {
        const p = gameState.players.find(pl => pl.name === owner.value);
        const info = document.getElementById("share-price-info");
        if (p && info) {
            info.textContent = p.share_price > 0
                ? `Aktiekurs: ${fmt(p.share_price)} kr (${p.shares_issued}/${p.max_shares} emitterade)`
                : "Inga fastigheter registrerade — aktiekurs 0 kr.";
        }
    }
}

function renderLoans() {
    const container = document.getElementById("active-loans");
    const allLoans = [];

    gameState.players.forEach(p => {
        p.bank_loans.forEach((loan, idx) => {
            allLoans.push({
                type: "Bank", player: p.name,
                amount: loan.amount, remaining: loan.remaining,
                idx, from: "Banken", isBank: true,
            });
        });
        p.player_loans_taken.forEach((loan, idx) => {
            allLoans.push({
                type: "Spelar", player: p.name,
                amount: loan.amount, remaining: loan.remaining,
                idx, from: loan.from, isBank: false,
            });
        });
    });

    if (allLoans.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">&#9734;</div><div class="empty-state-text">Inga aktiva lan.</div></div>';
        return;
    }

    container.innerHTML = allLoans.map(l => `
        <div class="loan-card">
            <div>
                <strong>${l.player}</strong> — ${l.type}lan fran ${l.from}<br>
                <span class="hint">Lanade ${fmt(l.amount)} kr | Aterstar: <span class="loan-amount">${fmt(l.remaining)} kr</span></span>
            </div>
            <button class="btn btn-danger btn-small" onclick="repayLoan('${l.player}', ${l.idx}, ${l.isBank})">Betala</button>
        </div>
    `).join("");
}

function renderInsurance() {
    const container = document.getElementById("active-insurance");
    const contracts = gameState.insurance_contracts || [];

    if (contracts.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">&#9730;</div><div class="empty-state-text">Inga aktiva forsakringsavtal.</div></div>';
        return;
    }

    container.innerHTML = contracts.map(c => `
        <div class="ins-card">
            <div>
                <strong>#${c.id}</strong>: ${c.insurer} forsakrar ${c.insured}<br>
                <span class="hint">Premie: ${fmt(c.premium_per_round)} kr/runda | Tak: ${fmt(c.coverage_cap)} kr | Kvar: ${fmt(c.coverage_remaining)} kr</span>
            </div>
            <button class="btn btn-ghost btn-small" onclick="cancelIns(${c.id}, '${c.insurer}')">Avbryt</button>
        </div>
    `).join("");
}

function renderLog() {
    document.getElementById("game-log").innerHTML = gameState.log
        .slice().reverse()
        .map(entry => {
            const isMarker = entry.startsWith("──");
            return `<div class="log-entry ${isMarker ? "round-marker" : ""}">${entry}</div>`;
        })
        .join("");
}

// ── Actions ──────────────────────────────────────────────────────────────

async function apiAction(url, data, btn) {
    if (btn) setLoading(btn, true);
    const res = await API.post(url, data);
    if (btn) setLoading(btn, false);
    if (res.game) { gameState = res.game; renderGame(); }
    toast(res.message, res.status !== "ok");
}

document.getElementById("btn-market-round").addEventListener("click", function() {
    apiAction("/api/market_round", {}, this);
});

document.getElementById("btn-add-prop").addEventListener("click", function() {
    apiAction("/api/add_property", {
        player: document.getElementById("prop-player").value,
        street: document.getElementById("prop-street").value,
    }, this);
});
document.getElementById("btn-remove-prop").addEventListener("click", function() {
    apiAction("/api/remove_property", {
        player: document.getElementById("prop-player").value,
        street: document.getElementById("prop-street").value,
    }, this);
});

document.getElementById("btn-collect-rent").addEventListener("click", function() {
    apiAction("/api/collect_rent", {
        player: document.getElementById("rent-player").value,
        amount: document.getElementById("rent-amount").value,
    }, this);
});

document.getElementById("btn-issue-share").addEventListener("click", function() {
    apiAction("/api/issue_share", {
        owner: document.getElementById("share-owner").value,
        buyer: document.getElementById("share-buyer").value,
    }, this);
});

document.getElementById("share-owner").addEventListener("change", () => renderShareOverview());

document.getElementById("btn-transfer-share").addEventListener("click", function() {
    apiAction("/api/transfer_share", {
        seller: document.getElementById("trade-seller").value,
        buyer: document.getElementById("trade-buyer").value,
        company: document.getElementById("trade-company").value,
        price: document.getElementById("trade-price").value,
    }, this);
});

document.getElementById("bank-loan-amount").addEventListener("input", e => {
    document.getElementById("bank-loan-display").textContent = fmt(e.target.value) + " kr";
});

document.getElementById("btn-bank-loan").addEventListener("click", function() {
    apiAction("/api/take_bank_loan", {
        player: document.getElementById("bank-loan-player").value,
        amount: document.getElementById("bank-loan-amount").value,
    }, this);
});

document.getElementById("btn-player-loan").addEventListener("click", function() {
    apiAction("/api/give_player_loan", {
        lender: document.getElementById("ploan-lender").value,
        borrower: document.getElementById("ploan-borrower").value,
        amount: document.getElementById("ploan-amount").value,
        interest_rate: document.getElementById("ploan-interest").value,
    }, this);
});

async function repayLoan(player, idx, isBank) {
    const url = isBank ? "/api/repay_bank_loan" : "/api/repay_player_loan";
    await apiAction(url, { player, loan_index: idx });
}

document.getElementById("btn-create-insurance").addEventListener("click", function() {
    apiAction("/api/create_insurance", {
        insurer: document.getElementById("ins-insurer").value,
        insured: document.getElementById("ins-insured").value,
        premium: document.getElementById("ins-premium").value,
        coverage_cap: document.getElementById("ins-cap").value,
    }, this);
});

document.getElementById("btn-claim").addEventListener("click", function() {
    apiAction("/api/claim_insurance", {
        player: document.getElementById("claim-player").value,
        contract_id: document.getElementById("claim-contract").value,
        amount: document.getElementById("claim-amount").value,
    }, this);
});

async function cancelIns(contractId, player) {
    await apiAction("/api/cancel_insurance", { player, contract_id: contractId });
}

document.getElementById("btn-transfer-money").addEventListener("click", function() {
    apiAction("/api/transfer_money", {
        from: document.getElementById("money-from").value,
        to: document.getElementById("money-to").value,
        amount: document.getElementById("money-amount").value,
    }, this);
});

document.getElementById("btn-adjust").addEventListener("click", function() {
    apiAction("/api/adjust_balance", {
        player: document.getElementById("adjust-player").value,
        amount: document.getElementById("adjust-amount").value,
    }, this);
});

document.getElementById("btn-distress").addEventListener("click", function() {
    if (!confirm("Ar du saker pa att du vill deklarera nodsituation?")) return;
    apiAction("/api/distress", {
        player: document.getElementById("distress-player").value,
    }, this);
});

// ── Quick-amount buttons ─────────────────────────────────────────────
document.addEventListener("click", (e) => {
    if (e.target.classList.contains("quick-amt")) {
        const target = document.getElementById(e.target.dataset.target);
        if (target) {
            target.value = e.target.dataset.value;
            target.dispatchEvent(new Event("input"));
        }
    }
});

// ── Log panel toggle (mobile) ────────────────────────────────────────
document.getElementById("log-toggle").addEventListener("click", () => {
    const panel = document.getElementById("log-panel");
    const icon = document.getElementById("log-toggle-icon");
    panel.classList.toggle("collapsed");
    icon.classList.toggle("open");
});
