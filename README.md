# Monopoly Plus

A financial extension layer for physical Monopoly (Stockholm edition). Players use their phones to manage shares, loans, insurance contracts, and more — all synced in real-time across devices.

## Features

### Shares & Dividends
Each player is a publicly tradeable company. Other players can buy shares in you.

- Issue up to 4 shares at a price derived from your property value
- Shareholders receive **15% of rent** collected per share held
- Free-market trading between players at negotiated prices
- Share buyback at current market price

### Bank Loans
- Borrow 500–10,000 kr at 10% interest
- Debt compounds 5% per market round (capped at 2x original)
- One-time loan restructuring available (+20% balance, resets compound clock)

### Player-to-Player Loans
- Negotiate custom amount and interest rate
- Compounds each market round
- Forgiven if the lender is eliminated

### Insurance Contracts
- Any player can offer insurance to another
- Insured pays a premium per round; insurer covers costs up to a cap
- Claims auto-deduct from coverage when collecting rent
- Premiums deferred (not cancelled) during distress

### Distress & Elimination
- **First default**: Distressed for 2 rounds — rent halved, no borrowing, interest frozen
- **Second default**: Eliminated — properties auctioned, shares voided, loans resolved

### Market Rounds
Triggered when a player passes Go. Processes all recurring financials:
- Insurance premiums
- Loan interest compounding
- Distress countdowns

### Real-Time Multiplayer
- Host creates a game and gets a **5-digit game code**
- Other players join from any device by entering the code
- Each player claims a character — live sync via WebSocket
- Connection status indicator, auto-reconnect on page refresh

## Tech Stack

- **Backend**: Python / Flask + Flask-SocketIO
- **Frontend**: Vanilla JS + HTML/CSS (single-page app)
- **State**: In-memory (no database)
- **Board**: Swedish Monopoly — Stockholm street names

## Getting Started

```bash
pip install -r requirements.txt
python app.py
```

Server starts on `http://0.0.0.0:5000`. Open it on your phone or share the URL across your local network.

1. Click **Skapa Nytt Spel** to create a game
2. Share the 5-digit code with other players
3. Add player names, then start the game
4. Each player claims their character from their own device

## Configuration

Game settings are in `player_settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `start_balance` | 30,000 kr | Starting cash per player |
| `max_shares` | 4 | Max shares a player can issue |
| `dividend_per_share` | 15% | Rent share paid to each shareholder |
| `interest_rate` | 10% | Bank loan interest per lap |
| `min_loan` / `max_loan` | 500 / 10,000 kr | Bank loan limits |
| `rent_penalty` | 50% | Rent reduction while distressed |
| `duration_rounds` | 2 | Rounds spent in distressed status |

## API

All endpoints return `{ status, message, game }`. State changes broadcast to all connected clients via WebSocket.

**Game**: `new_game`, `join_game`, `claim_player`, `unclaim_player`, `add_player`, `start_game`, `state`
**Properties**: `add_property`, `remove_property`, `transfer_property`
**Shares**: `issue_share`, `transfer_share`, `buyback_share`
**Rent**: `collect_rent`
**Bank Loans**: `take_bank_loan`, `repay_bank_loan`, `restructure_bank_loan`
**Player Loans**: `give_player_loan`, `repay_player_loan`
**Insurance**: `create_insurance`, `claim_insurance`, `cancel_insurance`
**Money**: `transfer_money`, `adjust_balance`
**Game Events**: `distress`, `market_round`, `buy_from_auction`
