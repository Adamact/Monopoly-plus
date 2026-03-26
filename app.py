from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, join_room, emit
import random
import math
import config
import player_settings as psettings
from location_data import location

app = Flask(__name__)
app.secret_key = "monopoly-plus-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*")

games = {}

S = psettings.settings


# ── Models ──────────────────────────────────────────────────────────────────

class Player:
    """Each player IS a company. Other players can buy shares in them."""

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.balance = S["player"]["start_balance"]
        self.properties = []        # list of street names they own on the physical board
        self.property_value = 0     # sum of Pris for owned properties

        # Shares: this player can issue up to 4 shares in themselves
        self.shares_issued = 0      # 0-4 shares currently outstanding
        self.shareholders = {}      # {player_name: count} — who holds shares in ME

        # Loans
        self.bank_loans = []        # [{"amount": int, "remaining": int, "taken_round": int}]
        self.player_loans_given = []   # loans I gave: [{"to": name, "remaining": int, ...}]
        self.player_loans_taken = []   # loans I took: [{"from": name, "remaining": int, "interest_rate": float, ...}]

        # Insurance contracts where I am the insured
        self.insurance_policies = []   # [{"insurer": name, "premium": int, "coverage_cap": int, "active": bool}]

        # Distress
        self.distressed = False
        self.distress_rounds_left = 0
        self.defaults = 0           # second default = elimination
        self.eliminated = False

    @property
    def share_price(self):
        max_shares = S["player"]["max_shares"]
        base = self.property_value + self.balance * 0.1
        if base <= 0:
            return 0
        return base / max_shares

    @property
    def total_debt(self):
        bank = sum(l["remaining"] for l in self.bank_loans)
        player = sum(l["remaining"] for l in self.player_loans_taken)
        return bank + player

    def portfolio_value(self, all_players):
        """Value of shares this player holds in OTHER players."""
        total = 0
        for other in all_players:
            if other.name == self.name or other.eliminated:
                continue
            held = other.shareholders.get(self.name, 0)
            total += held * other.share_price
        return total

    def get_portfolio(self, all_players):
        """Dict of {player_name: {count, value, price}} for shares held in others."""
        portfolio = {}
        for other in all_players:
            if other.name == self.name:
                continue
            held = other.shareholders.get(self.name, 0)
            if held > 0:
                portfolio[other.name] = {
                    "count": held,
                    "price": round(other.share_price, 2),
                    "value": round(held * other.share_price, 2),
                }
        return portfolio

    def net_worth_full(self, all_players):
        """Balance + property value + portfolio value - debt."""
        return self.balance + self.property_value + self.portfolio_value(all_players) - self.total_debt

    def color_groups(self):
        """Returns dict of {color_group: info} for groups where player owns at least 1 street."""
        groups = {}
        for group_name, streets in config.streets.items():
            owned = [s for s in streets if s in self.properties]
            if owned:
                groups[group_name] = {
                    "owned": owned,
                    "total": len(streets),
                    "complete": len(owned) == len(streets),
                }
        return groups

    def to_dict(self, all_players=None):
        all_p = all_players or []
        portfolio = self.get_portfolio(all_p) if all_p else {}
        nw = self.net_worth_full(all_p) if all_p else (self.balance + self.property_value - self.total_debt)
        return {
            "name": self.name,
            "color": self.color,
            "balance": self.balance,
            "properties": self.properties,
            "property_value": self.property_value,
            "color_groups": self.color_groups(),
            "shares_issued": self.shares_issued,
            "max_shares": S["player"]["max_shares"],
            "shareholders": self.shareholders,
            "share_price": round(self.share_price, 2),
            "portfolio": portfolio,
            "portfolio_value": round(self.portfolio_value(all_p), 2) if all_p else 0,
            "bank_loans": self.bank_loans,
            "player_loans_taken": self.player_loans_taken,
            "player_loans_given": self.player_loans_given,
            "insurance_policies": self.insurance_policies,
            "total_debt": self.total_debt,
            "net_worth": round(nw, 2),
            "distressed": self.distressed,
            "distress_rounds_left": self.distress_rounds_left,
            "defaults": self.defaults,
            "eliminated": self.eliminated,
            "insolvent": nw < 0,
        }


class InsuranceContract:
    """A contract between two players."""
    _next_id = 0

    def __init__(self, insurer, insured, premium_per_round, coverage_cap):
        InsuranceContract._next_id += 1
        self.id = InsuranceContract._next_id
        self.insurer = insurer          # player name
        self.insured = insured          # player name
        self.premium_per_round = premium_per_round
        self.coverage_cap = coverage_cap
        self.coverage_used = 0
        self.active = True
        self.missed_payments = 0

    def to_dict(self):
        return {
            "id": self.id,
            "insurer": self.insurer,
            "insured": self.insured,
            "premium_per_round": self.premium_per_round,
            "coverage_cap": self.coverage_cap,
            "coverage_used": self.coverage_used,
            "coverage_remaining": self.coverage_cap - self.coverage_used,
            "active": self.active,
            "missed_payments": self.missed_payments,
        }


class Game:
    PLAYER_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]

    def __init__(self):
        self.players = []
        self.names = []
        self.insurance_contracts = []
        self.current_round = 0
        self.started = False
        self.log = []
        self.claimed_players = set()
        self._next_loan_id = 0
        self.auction_pool = []  # properties from eliminated players
        self.transactions = []  # structured history: [{round, type, player, amount, counterparty, detail}]

    def _record(self, tx_type, player, amount=0, counterparty=None, detail=""):
        self.transactions.append({
            "round": self.current_round,
            "type": tx_type,
            "player": player,
            "amount": amount,
            "counterparty": counterparty,
            "detail": detail,
        })

    def add_player(self, name):
        if name in self.names or len(self.players) >= 6:
            return False
        color = self.PLAYER_COLORS[len(self.players)]
        self.players.append(Player(name, color))
        self.names.append(name)
        return True

    def get_player(self, name):
        for p in self.players:
            if p.name == name:
                return p
        return None

    def buy_from_auction(self, buyer_name, street_name, bid):
        """Buy a property from the auction pool at agreed price."""
        buyer = self.get_player(buyer_name)
        if not buyer or buyer.eliminated:
            return False, "Invalid player."
        if street_name not in self.auction_pool:
            return False, "Property not in auction."
        if bid <= 0:
            return False, "Invalid bid."
        if buyer.balance < bid:
            return False, f"Not enough money. Have {buyer.balance}kr."

        # Find real price for property_value tracking
        real_price = 0
        for group in config.streets.values():
            if street_name in group:
                real_price = group[street_name]["Pris"]
                break

        buyer.balance -= bid
        self.auction_pool.remove(street_name)
        buyer.properties.append(street_name)
        buyer.property_value += real_price

        self.log.append(f"{buyer_name} bought {street_name} from auction for {bid}kr (value: {real_price}kr).")
        return True, f"Bought {street_name} for {bid}kr."

    # ── Properties (reported from physical board) ─────────────────────

    def add_property(self, player_name, street_name):
        """Player tells us they bought a property on the physical board."""
        player = self.get_player(player_name)
        if not player or player.eliminated:
            return False, "Invalid player."
        if street_name in player.properties:
            return False, "Already owns this property."

        # Find property price in config
        price = None
        for group in config.streets.values():
            if street_name in group:
                price = group[street_name]["Pris"]
                break
        if price is None:
            return False, "Property not found."

        player.properties.append(street_name)
        player.property_value += price

        self.log.append(f"{player_name} registered {street_name} ({price}kr).")
        return True, f"Registered {street_name}. Share price now {player.share_price:.0f}kr."

    def remove_property(self, player_name, street_name):
        """Player sold/lost a property."""
        player = self.get_player(player_name)
        if not player or street_name not in player.properties:
            return False, "Property not found."

        price = 0
        for group in config.streets.values():
            if street_name in group:
                price = group[street_name]["Pris"]
                break

        old_price = player.share_price
        player.properties.remove(street_name)
        player.property_value -= price
        new_price = player.share_price

        self.log.append(f"{player_name} removed {street_name}.")
        if player.shares_issued > 0 and new_price < old_price * 0.7:
            self.log.append(
                f"  ALERT: {player_name}'s share price dropped {old_price:.0f} -> {new_price:.0f}kr!"
            )
        return True, f"Removed {street_name}. Share price: {new_price:.0f}kr."

    def transfer_property(self, from_name, to_name, street_name):
        from_p = self.get_player(from_name)
        to_p = self.get_player(to_name)
        if not from_p or not to_p:
            return False, "Invalid player."
        if street_name not in from_p.properties:
            return False, f"{from_name} doesn't own {street_name}."
        price = 0
        for group in config.streets.values():
            if street_name in group:
                price = group[street_name]["Pris"]
                break
        from_p.properties.remove(street_name)
        from_p.property_value -= price
        to_p.properties.append(street_name)
        to_p.property_value += price
        self.log.append(f"{from_name} transferred {street_name} to {to_name}.")
        return True, f"Transferred {street_name} ({price}kr)."

    # ── Shares ────────────────────────────────────────────────────────
    # Each player can issue up to 4 shares. Buying a share = investing
    # in that player. Shareholders get 15% of rent per share held.

    def issue_share(self, owner_name, buyer_name):
        """Owner issues a new share, buyer pays share_price."""
        owner = self.get_player(owner_name)
        buyer = self.get_player(buyer_name)
        if not owner or not buyer:
            return False, "Invalid player."
        if owner.eliminated or buyer.eliminated:
            return False, "Eliminated player."
        if buyer.distressed:
            return False, "Cannot buy shares while distressed."
        if owner_name == buyer_name:
            return False, "Cannot buy your own shares."
        if owner.shares_issued >= S["player"]["max_shares"]:
            return False, f"Max {S['player']['max_shares']} shares already issued."
        if owner.share_price <= 0:
            return False, "No properties yet — share price is 0."
        if buyer.balance < owner.share_price:
            return False, f"Not enough money. Share costs {owner.share_price:.0f}kr."

        price = owner.share_price
        buyer.balance -= price
        owner.balance += price  # owner raises cash by issuing equity
        owner.shares_issued += 1
        owner.shareholders[buyer_name] = owner.shareholders.get(buyer_name, 0) + 1

        self.log.append(
            f"{buyer_name} bought 1 share in {owner_name} for {price:.0f}kr. "
            f"({owner.shares_issued}/{S['player']['max_shares']} issued)"
        )
        self._record("share_issue", buyer_name, price, owner_name, f"1 share at {price:.0f}kr")
        return True, f"Bought share in {owner_name} for {price:.0f}kr."

    def transfer_share(self, seller_name, buyer_name, company_name, price):
        """Free trade: seller transfers a share in company_name to buyer at agreed price."""
        seller = self.get_player(seller_name)
        buyer = self.get_player(buyer_name)
        company = self.get_player(company_name)
        if not seller or not buyer or not company:
            return False, "Invalid player."
        if seller.eliminated or buyer.eliminated:
            return False, "Eliminated player."

        held = company.shareholders.get(seller_name, 0)
        if held <= 0:
            return False, f"{seller_name} holds no shares in {company_name}."
        if buyer.balance < price:
            return False, f"{buyer_name} can't afford {price}kr."

        buyer.balance -= price
        seller.balance += price
        company.shareholders[seller_name] -= 1
        if company.shareholders[seller_name] == 0:
            del company.shareholders[seller_name]
        company.shareholders[buyer_name] = company.shareholders.get(buyer_name, 0) + 1

        self.log.append(
            f"{seller_name} sold 1 share in {company_name} to {buyer_name} for {price}kr."
        )
        return True, f"Share transferred for {price}kr."

    def buyback_share(self, owner_name, from_holder_name):
        owner = self.get_player(owner_name)
        holder = self.get_player(from_holder_name)
        if not owner or not holder:
            return False, "Invalid player."
        held = owner.shareholders.get(from_holder_name, 0)
        if held <= 0:
            return False, f"{from_holder_name} holds no shares in {owner_name}."
        price = owner.share_price
        if owner.balance < price:
            return False, f"Not enough money. Buyback costs {price:.0f}kr."
        owner.balance -= price
        holder.balance += price
        owner.shareholders[from_holder_name] -= 1
        if owner.shareholders[from_holder_name] == 0:
            del owner.shareholders[from_holder_name]
        owner.shares_issued -= 1
        self.log.append(
            f"{owner_name} bought back 1 share from {from_holder_name} for {price:.0f}kr. "
            f"({owner.shares_issued}/{S['player']['max_shares']} outstanding)"
        )
        return True, f"Bought back share for {price:.0f}kr."

    # ── Rent & Dividends ──────────────────────────────────────────────

    def collect_rent(self, collector_name, amount):
        """Player reports collecting rent. Auto-distributes dividends to shareholders.
        If collector is distressed, rent is halved."""
        collector = self.get_player(collector_name)
        if not collector or collector.eliminated:
            return False, "Invalid player."

        effective = amount
        if collector.distressed:
            effective = int(amount * S["distress"]["rent_penalty"])
            self.log.append(f"{collector_name} is distressed — rent halved: {effective}kr (was {amount}kr).")

        # Distribute dividends: 15% per share
        dividend_rate = S["player"]["dividend_per_share"]
        total_dividends = 0
        for holder_name, count in collector.shareholders.items():
            holder = self.get_player(holder_name)
            if holder and not holder.eliminated:
                dividend = int(effective * dividend_rate * count)
                if dividend > 0:
                    effective -= dividend
                    total_dividends += dividend
                    holder.balance += dividend
                    self.log.append(
                        f"  {holder_name} received {dividend}kr dividend "
                        f"({count} share{'s' if count > 1 else ''} in {collector_name})."
                    )

        collector.balance += effective
        msg = f"{collector_name} collected {amount}kr rent"
        if total_dividends > 0:
            msg += f" ({total_dividends}kr to shareholders, {effective}kr kept)"
        msg += "."
        self.log.append(msg)
        return True, msg

    def pay_rent_with_insurance(self, player_name, rent_amount):
        """Convenience: pay rent, auto-claiming from best insurance contract."""
        player = self.get_player(player_name)
        if not player:
            return False, "Invalid player."

        covered = 0
        for c in self.insurance_contracts:
            if c.insured == player_name and c.active:
                remaining = c.coverage_cap - c.coverage_used
                claim = min(rent_amount - covered, remaining)
                if claim <= 0:
                    continue
                insurer = self.get_player(c.insurer)
                if not insurer or insurer.balance < claim:
                    continue
                insurer.balance -= claim
                player.balance += claim
                c.coverage_used += claim
                covered += claim
                self.log.append(
                    f"  Insurance #{c.id} covered {claim}kr (paid by {c.insurer})."
                )
                if c.coverage_used >= c.coverage_cap:
                    c.active = False
                if covered >= rent_amount:
                    break

        out_of_pocket = rent_amount - covered
        if out_of_pocket > 0:
            player.balance -= out_of_pocket

        self._sync_insurance(player_name)
        msg = f"{player_name} paid {rent_amount}kr rent"
        if covered > 0:
            msg += f" ({covered}kr covered by insurance, {out_of_pocket}kr out of pocket)"
        msg += "."
        self.log.append(msg)
        return True, msg

    # ── Bank Loans ────────────────────────────────────────────────────

    def take_bank_loan(self, player_name, amount):
        player = self.get_player(player_name)
        if not player or player.eliminated:
            return False, "Invalid player."
        if player.distressed:
            return False, "Cannot borrow while distressed."
        cfg = S["bank_loan"]
        if amount < cfg["min_loan"] or amount > cfg["max_loan"]:
            return False, f"Bank loans: {cfg['min_loan']}-{cfg['max_loan']}kr."

        remaining = int(amount * (1 + cfg["interest_rate"]))
        player.balance += amount
        player.bank_loans.append({
            "amount": amount,
            "remaining": remaining,
            "interest_rate": cfg["interest_rate"],
            "taken_round": self.current_round,
        })

        self.log.append(
            f"{player_name} took a bank loan: {amount}kr "
            f"(repay {remaining}kr at {cfg['interest_rate']*100:.0f}%)."
        )
        self._record("bank_loan", player_name, amount, "Bank", f"repay {remaining}kr")
        return True, f"Bank loan: {amount}kr (repay {remaining}kr)."

    def repay_bank_loan(self, player_name, loan_index, amount=None):
        """Repay a bank loan. If amount is None, repays in full."""
        player = self.get_player(player_name)
        if not player:
            return False, "Invalid player."
        if loan_index < 0 or loan_index >= len(player.bank_loans):
            return False, "Invalid loan."
        loan = player.bank_loans[loan_index]
        pay = amount if amount is not None else loan["remaining"]
        pay = min(pay, loan["remaining"])
        if pay <= 0:
            return False, "Invalid amount."
        if player.balance < pay:
            return False, f"Not enough money. Have {player.balance}kr."

        player.balance -= pay
        loan["remaining"] -= pay
        if loan["remaining"] <= 0:
            player.bank_loans.pop(loan_index)
            self.log.append(f"{player_name} fully repaid bank loan: {pay}kr.")
        else:
            self.log.append(f"{player_name} partially repaid bank loan: {pay}kr ({loan['remaining']}kr left).")
        return True, f"Repaid {pay}kr."

    def restructure_bank_loan(self, player_name, loan_index):
        """Restructure: adds 20% to remaining but resets compound clock. Once per loan."""
        player = self.get_player(player_name)
        if not player:
            return False, "Invalid player."
        if loan_index < 0 or loan_index >= len(player.bank_loans):
            return False, "Invalid loan."
        loan = player.bank_loans[loan_index]
        if loan.get("restructured"):
            return False, "Already restructured once."

        old_remaining = loan["remaining"]
        loan["remaining"] = int(loan["remaining"] * 1.20)
        loan["amount"] = loan["remaining"]  # reset cap basis
        loan["restructured"] = True
        self.log.append(
            f"{player_name} restructured bank loan: {old_remaining}kr -> {loan['remaining']}kr "
            f"(+20%, compound clock reset)."
        )
        return True, f"Restructured. New balance: {loan['remaining']}kr."

    # ── Player-to-Player Loans ────────────────────────────────────────

    def give_player_loan(self, lender_name, borrower_name, amount, interest_rate):
        """Lender gives borrower a loan at negotiated interest."""
        lender = self.get_player(lender_name)
        borrower = self.get_player(borrower_name)
        if not lender or not borrower:
            return False, "Invalid player."
        if lender_name == borrower_name:
            return False, "Can't lend to yourself."
        if lender.distressed:
            return False, "Cannot lend while distressed."
        if amount <= 0:
            return False, "Invalid amount."
        if lender.balance < amount:
            return False, f"{lender_name} doesn't have {amount}kr."

        remaining = int(amount * (1 + interest_rate / 100))

        lender.balance -= amount
        borrower.balance += amount

        self._next_loan_id += 1
        loan_record = {
            "id": self._next_loan_id,
            "amount": amount,
            "remaining": remaining,
            "interest_rate": interest_rate,
            "taken_round": self.current_round,
        }

        # Cross-reference
        lender.player_loans_given.append({
            **loan_record, "to": borrower_name
        })
        borrower.player_loans_taken.append({
            **loan_record, "from": lender_name
        })

        self.log.append(
            f"{lender_name} lent {borrower_name} {amount}kr "
            f"at {interest_rate}% (repay {remaining}kr)."
        )
        self._record("player_loan", borrower_name, amount, lender_name, f"{interest_rate}% interest")
        return True, f"Loan given: {amount}kr at {interest_rate}%."

    def repay_player_loan(self, borrower_name, loan_index, amount=None):
        """Repay a player loan. If amount is None, repays in full."""
        borrower = self.get_player(borrower_name)
        if not borrower:
            return False, "Invalid player."
        if loan_index < 0 or loan_index >= len(borrower.player_loans_taken):
            return False, "Invalid loan."

        loan = borrower.player_loans_taken[loan_index]
        pay = amount if amount is not None else loan["remaining"]
        pay = min(pay, loan["remaining"])
        if pay <= 0:
            return False, "Invalid amount."
        if borrower.balance < pay:
            return False, f"Not enough money. Have {borrower.balance}kr."

        lender = self.get_player(loan["from"])
        borrower.balance -= pay
        if lender:
            lender.balance += pay

        loan["remaining"] -= pay
        loan_id = loan.get("id")

        # Sync lender's copy by ID
        if lender and loan_id:
            for gl in lender.player_loans_given:
                if gl.get("id") == loan_id:
                    gl["remaining"] = loan["remaining"]
                    break

        if loan["remaining"] <= 0:
            borrower.player_loans_taken.pop(loan_index)
            if lender:
                lender.player_loans_given = [gl for gl in lender.player_loans_given if gl.get("id") != loan_id]
            self.log.append(f"{borrower_name} fully repaid {loan['from']}: {pay}kr.")
        else:
            self.log.append(f"{borrower_name} partially repaid {loan['from']}: {pay}kr ({loan['remaining']}kr left).")
        return True, f"Repaid {pay}kr to {loan['from']}."

    # ── Insurance ─────────────────────────────────────────────────────

    def create_insurance(self, insurer_name, insured_name, premium, coverage_cap):
        """Insurer offers a contract: insured pays premium/round, gets coverage up to cap."""
        insurer = self.get_player(insurer_name)
        insured = self.get_player(insured_name)
        if not insurer or not insured:
            return False, "Invalid player."
        if insurer_name == insured_name:
            return False, "Can't insure yourself."
        if premium <= 0 or coverage_cap <= 0:
            return False, "Invalid terms."

        contract = InsuranceContract(insurer_name, insured_name, premium, coverage_cap)
        self.insurance_contracts.append(contract)
        insured.insurance_policies.append(contract.to_dict())

        self.log.append(
            f"Insurance: {insurer_name} insures {insured_name} — "
            f"premium {premium}kr/round, coverage up to {coverage_cap}kr."
        )
        return True, f"Contract created (ID: {contract.id})."

    def claim_insurance(self, insured_name, contract_id, claim_amount):
        """Insured makes a claim against a contract."""
        insured = self.get_player(insured_name)
        if not insured:
            return False, "Invalid player."

        contract = None
        for c in self.insurance_contracts:
            if c.id == contract_id and c.insured == insured_name and c.active:
                contract = c
                break
        if not contract:
            return False, "No active contract found."

        remaining_coverage = contract.coverage_cap - contract.coverage_used
        payout = min(claim_amount, remaining_coverage)
        if payout <= 0:
            return False, "Coverage exhausted."

        insurer = self.get_player(contract.insurer)
        if not insurer or insurer.balance < payout:
            return False, f"Insurer {contract.insurer} can't pay {payout}kr."

        insurer.balance -= payout
        insured.balance += payout
        contract.coverage_used += payout

        # Sync to player's policy list
        self._sync_insurance(insured_name)

        if contract.coverage_used >= contract.coverage_cap:
            contract.active = False
            self.log.append(f"Insurance #{contract.id} coverage exhausted.")

        self.log.append(
            f"{insured_name} claimed {payout}kr from insurance #{contract.id} "
            f"(paid by {contract.insurer}). {remaining_coverage - payout}kr coverage left."
        )
        return True, f"Claimed {payout}kr."

    def cancel_insurance(self, player_name, contract_id):
        for c in self.insurance_contracts:
            if c.id == contract_id and (c.insurer == player_name or c.insured == player_name) and c.active:
                c.active = False
                self._sync_insurance(c.insured)
                self.log.append(f"Insurance #{contract_id} cancelled by {player_name}.")
                return True, "Contract cancelled."
        return False, "Contract not found."

    def _sync_insurance(self, player_name):
        """Sync insurance_policies on player with contract objects."""
        player = self.get_player(player_name)
        if player:
            player.insurance_policies = [
                c.to_dict() for c in self.insurance_contracts
                if c.insured == player_name and c.active
            ]

    # ── Transactions ──────────────────────────────────────────────────

    def transfer_money(self, from_name, to_name, amount):
        sender = self.get_player(from_name)
        receiver = self.get_player(to_name)
        if not sender or not receiver:
            return False, "Invalid player."
        if amount <= 0:
            return False, "Invalid amount."
        if sender.balance < amount:
            return False, "Not enough money."

        sender.balance -= amount
        receiver.balance += amount
        self.log.append(f"{from_name} paid {to_name} {amount}kr.")
        return True, f"Transferred {amount}kr."

    def adjust_balance(self, player_name, amount):
        """For board events: rent paid, taxes, passing Start, etc."""
        player = self.get_player(player_name)
        if not player:
            return False, "Invalid player."
        player.balance += amount
        if amount >= 0:
            self.log.append(f"{player_name} received {amount}kr.")
        else:
            self.log.append(f"{player_name} paid {abs(amount)}kr.")
        return True, f"Balance adjusted by {amount:+}kr."

    # ── Distress & Default ────────────────────────────────────────────

    def enter_distress(self, player_name):
        """Player can't pay rent — enters distressed status."""
        player = self.get_player(player_name)
        if not player:
            return False, "Invalid player."
        if player.eliminated:
            return False, "Already eliminated."

        player.defaults += 1
        if player.defaults >= 2:
            player.eliminated = True
            player.distressed = False
            self.log.append(f"{player_name} defaulted a second time — ELIMINATED!")
            self._handle_elimination(player)
            winner = self.check_winner()
            if winner:
                self.log.append(f"── {winner} WINS THE GAME! ──")
            return True, f"{player_name} eliminated!"
        else:
            player.distressed = True
            player.distress_rounds_left = S["distress"]["duration_rounds"]
            self.log.append(
                f"{player_name} defaulted — enters DISTRESSED status for "
                f"{S['distress']['duration_rounds']} rounds (rent income halved). "
                f"A second default means elimination."
            )
            return True, f"{player_name} is now distressed."

    def _handle_elimination(self, player):
        name = player.name
        # Void insurance
        for c in self.insurance_contracts:
            if c.insurer == name or c.insured == name:
                c.active = False
        # Shares others hold in eliminated player become worthless
        if player.shareholders:
            for holder_name, count in list(player.shareholders.items()):
                self.log.append(f"  {holder_name}'s {count} share(s) in {name} are now worthless.")
            player.shareholders.clear()
            player.shares_issued = 0
        # Shares eliminated player holds in others — shareholder slot freed
        for other in self.players:
            if other.name == name:
                continue
            held = other.shareholders.pop(name, 0)
            if held > 0:
                self.log.append(f"  {name}'s {held} share(s) in {other.name} voided (slots now available).")
        # Player loans FROM eliminated = forgiven
        for loan in player.player_loans_given:
            borrower = self.get_player(loan["to"])
            if borrower:
                borrower.player_loans_taken = [l for l in borrower.player_loans_taken if l["from"] != name]
                self.log.append(f"  {loan['to']}'s loan from {name} ({loan['remaining']}kr) forgiven.")
        player.player_loans_given.clear()
        # Player loans TO eliminated = lenders lose out
        for loan in player.player_loans_taken:
            lender = self.get_player(loan["from"])
            if lender:
                lender.player_loans_given = [gl for gl in lender.player_loans_given if gl["to"] != name]
                self.log.append(f"  {loan['from']} lost {loan['remaining']}kr lent to {name}.")
        player.player_loans_taken.clear()
        # Bank loans written off
        if player.bank_loans:
            total = sum(l["remaining"] for l in player.bank_loans)
            self.log.append(f"  Bank wrote off {total}kr in loans to {name}.")
            player.bank_loans.clear()

        # Properties go to auction pool
        if player.properties:
            props = list(player.properties)
            player.properties.clear()
            player.property_value = 0
            if not hasattr(self, 'auction_pool'):
                self.auction_pool = []
            self.auction_pool.extend(props)
            self.log.append(f"  {name}'s properties ({', '.join(props)}) available for auction.")

        for p in self.players:
            self._sync_insurance(p.name)

    def active_player_count(self):
        return sum(1 for p in self.players if not p.eliminated)

    def check_winner(self):
        active = [p for p in self.players if not p.eliminated]
        if len(active) == 1 and len(self.players) > 1:
            return active[0].name
        return None

    # ── Market Round (triggered when someone passes Go) ───────────────

    def market_round(self):
        """Process per-round financials: insurance premiums, distress countdown, loan interest."""
        self.current_round += 1
        messages = []

        # 0) Process distress countdowns first
        for player in self.players:
            if player.eliminated or not player.distressed:
                continue
            player.distress_rounds_left -= 1
            if player.distress_rounds_left <= 0:
                player.distressed = False
                messages.append(f"{player.name} recovered from distressed status!")
            else:
                messages.append(
                    f"{player.name} still distressed ({player.distress_rounds_left} rounds left)."
                )

        for player in self.players:
            if player.eliminated:
                continue

            # 1) Insurance premiums (skipped if distressed, 1 grace period for missed payment)
            for c in self.insurance_contracts:
                if c.insured == player.name and c.active:
                    if player.distressed:
                        messages.append(f"{player.name} is distressed — insurance #{c.id} premium deferred.")
                        continue
                    if player.balance >= c.premium_per_round:
                        player.balance -= c.premium_per_round
                        insurer = self.get_player(c.insurer)
                        if insurer:
                            insurer.balance += c.premium_per_round
                        c.missed_payments = 0
                        messages.append(
                            f"{player.name} paid {c.premium_per_round}kr premium to {c.insurer}."
                        )
                    else:
                        c.missed_payments += 1
                        if c.missed_payments >= 2:
                            c.active = False
                            messages.append(
                                f"{player.name} missed 2 premiums — insurance #{c.id} LAPSED!"
                            )
                        else:
                            messages.append(
                                f"WARNING: {player.name} missed premium for #{c.id} "
                                f"(1 grace round — pay next round or it lapses)."
                            )

            # 2) Bank loan interest compounds (skip if distressed, cap at 2x)
            if not player.distressed:
                for loan in player.bank_loans:
                    cap = loan["amount"] * 2
                    if loan["remaining"] >= cap:
                        continue  # capped
                    interest = int(loan["remaining"] * 0.05)
                    loan["remaining"] = min(loan["remaining"] + interest, cap)
                    if interest > 0:
                        capped_msg = " (CAPPED)" if loan["remaining"] >= cap else ""
                        messages.append(
                            f"{player.name}'s bank loan grew by {interest}kr "
                            f"(owes {loan['remaining']}kr){capped_msg}."
                        )

                # 3) Player loan interest compounds (skip if distressed, cap at 2x)
                for loan in player.player_loans_taken:
                    rate = loan.get("interest_rate", 0)
                    cap = loan["amount"] * 2
                    if rate > 0 and loan["remaining"] < cap:
                        compound = int(loan["remaining"] * rate / 100 * 0.1)
                        if compound > 0:
                            loan["remaining"] = min(loan["remaining"] + compound, cap)
                            loan_id = loan.get("id")
                            lender = self.get_player(loan["from"])
                            if lender and loan_id:
                                for gl in lender.player_loans_given:
                                    if gl.get("id") == loan_id:
                                        gl["remaining"] = loan["remaining"]
                                        break
                            capped_msg = " (CAPPED)" if loan["remaining"] >= cap else ""
                            messages.append(
                                f"{player.name}'s loan from {loan['from']} grew by {compound}kr "
                                f"(owes {loan['remaining']}kr){capped_msg}."
                            )
            else:
                messages.append(f"{player.name} is distressed — loan interest frozen this round.")

            # 4) Distress countdown (already processed at start of round)
            pass

        # Sync all insurance
        for p in self.players:
            self._sync_insurance(p.name)

        # Round summary
        total_interest = sum(1 for m in messages if "grew by" in m)
        total_premiums = sum(1 for m in messages if "premium" in m)
        for msg in messages:
            self.log.append(msg)
        self.log.append(
            f"── Market Round {self.current_round} "
            f"({total_interest} interest charges, {total_premiums} premiums) ──"
        )
        return messages

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self):
        player_dicts = [p.to_dict(self.players) for p in self.players]
        leaderboard = sorted(
            [{"name": p["name"], "net_worth": p["net_worth"], "color": p["color"]}
             for p in player_dicts if not p["eliminated"]],
            key=lambda x: x["net_worth"], reverse=True
        )
        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1
        winner = self.check_winner()
        return {
            "players": player_dicts,
            "insurance_contracts": [c.to_dict() for c in self.insurance_contracts if c.active],
            "current_round": self.current_round,
            "started": self.started,
            "log": self.log[-40:],
            "all_streets": self._all_streets(),
            "claimed_players": list(self.claimed_players),
            "leaderboard": leaderboard,
            "auction_pool": self.auction_pool,
            "transactions": self.transactions[-30:],
            "winner": winner,
        }

    def _all_streets(self):
        owner_map = {}
        for p in self.players:
            for s in p.properties:
                owner_map[s] = p.name
        streets = []
        for group_name, group in config.streets.items():
            for street_name, info in group.items():
                streets.append({
                    "name": street_name,
                    "group": group_name,
                    "price": info["Pris"],
                    "owner": owner_map.get(street_name),
                })
        return streets


# ── Helper ──────────────────────────────────────────────────────────────────

def get_game():
    game_id = session.get("game_id")
    if game_id and game_id in games:
        return games[game_id]
    return None

def game_required(f):
    """Decorator for endpoints that need an active started game."""
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        game = get_game()
        if not game or not game.started:
            return jsonify({"status": "error", "message": "Game not started."}), 400
        return f(game, *args, **kwargs)
    return wrapped


# ── Broadcast helper ────────────────────────────────────────────────────────

def broadcast_state(game_id):
    """Push current game state to all clients in this game's room."""
    if game_id in games:
        socketio.emit("game_update", {"game": games[game_id].to_dict()}, room=game_id)


# ── SocketIO events ────────────────────────────────────────────────────────

@socketio.on("join_game_room")
def handle_join_room(data):
    game_id = session.get("game_id")
    if game_id:
        join_room(game_id)
        if game_id in games:
            emit("game_update", {"game": games[game_id].to_dict()})


@socketio.on("disconnect")
def handle_disconnect():
    game_id = session.get("game_id")
    player_name = session.get("player_name")
    if game_id and game_id in games and player_name:
        game = games[game_id]
        if not game.started:
            game.claimed_players.discard(player_name)
            session.pop("player_name", None)
            broadcast_state(game_id)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/new_game", methods=["POST"])
def new_game():
    game_id = str(random.randint(10000, 99999))
    session["game_id"] = game_id
    session.pop("player_name", None)
    games[game_id] = Game()
    return jsonify({"status": "ok", "game_id": game_id})


@app.route("/api/join_game", methods=["POST"])
def join_game():
    game_id = str(request.json.get("game_id", "")).strip()
    if game_id not in games:
        return jsonify({"status": "error", "message": "Spelet hittades inte."}), 404
    session["game_id"] = game_id
    session.pop("player_name", None)
    game = games[game_id]
    return jsonify({"status": "ok", "game_id": game_id, "game": game.to_dict()})


@app.route("/api/claim_player", methods=["POST"])
def claim_player():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    name = request.json.get("name", "").strip()
    player = game.get_player(name)
    if not player:
        return jsonify({"status": "error", "message": "Spelaren finns inte."}), 400
    if name in game.claimed_players:
        return jsonify({"status": "error", "message": "Spelaren ar redan tagen."}), 400
    game.claimed_players.add(name)
    session["player_name"] = name
    broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok", "player_name": name})


@app.route("/api/unclaim_player", methods=["POST"])
def unclaim_player():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    name = session.get("player_name")
    if not name:
        return jsonify({"status": "error", "message": "Du har ingen spelare vald."}), 400
    if game.started:
        return jsonify({"status": "error", "message": "Kan inte byta spelare efter att spelet startat."}), 400
    game.claimed_players.discard(name)
    session.pop("player_name", None)
    broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok"})


@app.route("/api/add_player", methods=["POST"])
def add_player():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    name = request.json.get("name", "").strip().capitalize()
    if not name:
        return jsonify({"status": "error", "message": "Name required."}), 400
    if game.add_player(name):
        broadcast_state(session.get("game_id"))
        return jsonify({"status": "ok", "game": game.to_dict()})
    return jsonify({"status": "error", "message": "Name taken or max players reached."}), 400


@app.route("/api/start_game", methods=["POST"])
def start_game():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    if game.started:
        return jsonify({"status": "error", "message": "Spelet har redan startat."}), 400
    if len(game.players) < 2:
        return jsonify({"status": "error", "message": "Need at least 2 players."}), 400
    game.started = True
    game.log.append("── Game started! ──")
    broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok", "game": game.to_dict()})


@app.route("/api/state", methods=["GET"])
def state():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    return jsonify({
        "status": "ok",
        "game": game.to_dict(),
        "my_player": session.get("player_name"),
        "game_id": session.get("game_id"),
    })


# ── Properties ──

@app.route("/api/add_property", methods=["POST"])
@game_required
def add_property(game):
    d = request.json
    ok, msg = game.add_property(d.get("player"), d.get("street"))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/remove_property", methods=["POST"])
@game_required
def remove_property(game):
    d = request.json
    ok, msg = game.remove_property(d.get("player"), d.get("street"))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Shares ──

@app.route("/api/issue_share", methods=["POST"])
@game_required
def issue_share(game):
    d = request.json
    ok, msg = game.issue_share(d.get("owner"), d.get("buyer"))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/transfer_share", methods=["POST"])
@game_required
def transfer_share(game):
    d = request.json
    ok, msg = game.transfer_share(
        d.get("seller"), d.get("buyer"), d.get("company"), int(d.get("price", 0))
    )
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Rent ──

@app.route("/api/collect_rent", methods=["POST"])
@game_required
def collect_rent(game):
    d = request.json
    ok, msg = game.collect_rent(d.get("player"), int(d.get("amount", 0)))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Bank Loans ──

@app.route("/api/take_bank_loan", methods=["POST"])
@game_required
def take_bank_loan(game):
    d = request.json
    ok, msg = game.take_bank_loan(d.get("player"), int(d.get("amount", 0)))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/repay_bank_loan", methods=["POST"])
@game_required
def repay_bank_loan(game):
    d = request.json
    amt = d.get("amount")
    ok, msg = game.repay_bank_loan(d.get("player"), int(d.get("loan_index", 0)), int(amt) if amt else None)
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Player Loans ──

@app.route("/api/give_player_loan", methods=["POST"])
@game_required
def give_player_loan(game):
    d = request.json
    ok, msg = game.give_player_loan(
        d.get("lender"), d.get("borrower"),
        int(d.get("amount", 0)), float(d.get("interest_rate", 10))
    )
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/repay_player_loan", methods=["POST"])
@game_required
def repay_player_loan(game):
    d = request.json
    amt = d.get("amount")
    ok, msg = game.repay_player_loan(d.get("player"), int(d.get("loan_index", 0)), int(amt) if amt else None)
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Insurance ──

@app.route("/api/create_insurance", methods=["POST"])
@game_required
def create_insurance(game):
    d = request.json
    ok, msg = game.create_insurance(
        d.get("insurer"), d.get("insured"),
        int(d.get("premium", 0)), int(d.get("coverage_cap", 0))
    )
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/claim_insurance", methods=["POST"])
@game_required
def claim_insurance(game):
    d = request.json
    ok, msg = game.claim_insurance(
        d.get("player"), int(d.get("contract_id", 0)), int(d.get("amount", 0))
    )
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/cancel_insurance", methods=["POST"])
@game_required
def cancel_insurance(game):
    d = request.json
    ok, msg = game.cancel_insurance(d.get("player"), int(d.get("contract_id", 0)))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Money ──

@app.route("/api/transfer_money", methods=["POST"])
@game_required
def transfer_money(game):
    d = request.json
    ok, msg = game.transfer_money(
        d.get("from"), d.get("to"), int(d.get("amount", 0))
    )
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/adjust_balance", methods=["POST"])
@game_required
def adjust_balance(game):
    d = request.json
    ok, msg = game.adjust_balance(d.get("player"), int(d.get("amount", 0)))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Distress ──

@app.route("/api/distress", methods=["POST"])
@game_required
def distress(game):
    d = request.json
    ok, msg = game.enter_distress(d.get("player"))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


# ── Market Round ──

@app.route("/api/market_round", methods=["POST"])
@game_required
def market_round(game):
    messages = game.market_round()
    broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok", "messages": messages, "game": game.to_dict()})



@app.route("/api/transfer_property", methods=["POST"])
@game_required
def transfer_property_route(game):
    d = request.json
    ok, msg = game.transfer_property(d.get("from"), d.get("to"), d.get("street"))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/buyback_share", methods=["POST"])
@game_required
def buyback_share_route(game):
    d = request.json
    ok, msg = game.buyback_share(d.get("owner"), d.get("holder"))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})

@app.route("/api/buy_from_auction", methods=["POST"])
@game_required
def buy_from_auction_route(game):
    d = request.json
    ok, msg = game.buy_from_auction(d.get("player"), d.get("street"), int(d.get("bid", 0)))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/restructure_bank_loan", methods=["POST"])
@game_required
def restructure_bank_loan_route(game):
    d = request.json
    ok, msg = game.restructure_bank_loan(d.get("player"), int(d.get("loan_index", 0)))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/pay_rent_with_insurance", methods=["POST"])
@game_required
def pay_rent_with_insurance_route(game):
    d = request.json
    ok, msg = game.pay_rent_with_insurance(d.get("player"), int(d.get("amount", 0)))
    if ok:
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/renegotiate_insurance", methods=["POST"])
@game_required
def renegotiate_insurance_route(game):
    d = request.json
    contract_id = int(d.get("contract_id", 0))
    # Cancel old, create new with remaining coverage
    contract = None
    for c in game.insurance_contracts:
        if c.id == contract_id and c.active:
            contract = c
            break
    if not contract:
        return jsonify({"status": "error", "message": "Contract not found.", "game": game.to_dict()})

    remaining_coverage = contract.coverage_cap - contract.coverage_used
    new_premium = int(d.get("new_premium", contract.premium_per_round))
    new_cap = int(d.get("new_cap", remaining_coverage))
    new_cap = min(new_cap, remaining_coverage)  # can't increase beyond remaining

    contract.active = False
    ok, msg = game.create_insurance(contract.insurer, contract.insured, new_premium, new_cap)
    if ok:
        game.log.append(f"Insurance #{contract_id} renegotiated -> new terms.")
        broadcast_state(session.get("game_id"))
    return jsonify({"status": "ok" if ok else "error", "message": msg, "game": game.to_dict()})


if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000, host="0.0.0.0")
