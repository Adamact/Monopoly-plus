"""Domain models for Monopoly Plus GUI.

A single turn through all players is considered one “year” for
valuation and cash flow calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from player_settings import settings

ROUNDS_PER_YEAR = 1

SECTOR_MULTIPLIERS: Dict[str, float] = {
    "Property": 1.08,
    "Railroad": 0.95,
    "Utility": 1.0,
}

SECTOR_MARGINS: Dict[str, float] = {
    "Property": 0.3,
    "Railroad": 0.22,
    "Utility": 0.18,
}


@dataclass
class Asset:
    name: str
    value: float
    sector: str = "Property"
    cash_flow_per_year: float = 0.0


class Actor:
    """Represents a player/company actor in the game."""

    def __init__(self, name: str, balance: float | None = None, owner_name: Optional[str] = None):
        self.name = name
        self.balance = balance if balance is not None else settings["player"]["start_balance"]
        self.growth_expectation: float = 0.02
        self.risk_premium: float = 0.08
        self.debt: float = 0.0
        self.assets: List[Asset] = []
        main_owner = owner_name or name
        self.ownership_shares: Dict[str, float] = {main_owner: 100.0}
        self.holdings: Dict[str, float] = {}
        self.valuation_history: List[float] = []

    # --- Money / holdings helpers ---
    def adjust_balance(self, amount: float) -> None:
        self.balance = round(self.balance + amount, 2)

    def add_asset(self, name: str, value: float, sector: str, cash_flow_per_year: float = 0.0) -> Asset:
        asset = Asset(
            name=name,
            value=value,
            sector=sector if sector in SECTOR_MULTIPLIERS else "Property",
            cash_flow_per_year=cash_flow_per_year,
        )
        self.assets.append(asset)
        return asset

    # --- Derived metrics ---
    def total_asset_value(self) -> float:
        direct_value = sum(a.value * SECTOR_MULTIPLIERS.get(a.sector, 1.0) for a in self.assets)
        discounted_flow = sum(a.cash_flow_per_year for a in self.assets) * 4
        return direct_value + discounted_flow

    def cash_flow_multiple(self) -> float:
        base = 3 + (self.growth_expectation * 18)
        risk_adjustment = max(0.55, 1 - self.risk_premium)
        return max(2.0, base * risk_adjustment)

    def cash_flow_per_year(self) -> float:
        return sum(a.cash_flow_per_year for a in self.assets)

    def operating_result_per_year(self) -> float:
        total_flow = self.cash_flow_per_year()
        if total_flow == 0:
            margin = SECTOR_MARGINS["Property"]
        else:
            weighted_margins = sum(
                (a.cash_flow_per_year / total_flow) * SECTOR_MARGINS.get(a.sector, SECTOR_MARGINS["Property"])
                for a in self.assets
            )
            margin = weighted_margins
        return total_flow * margin

    def valuation(self) -> float:
        substance = self.total_asset_value()
        cash_flow = self.operating_result_per_year() * self.cash_flow_multiple()
        debt_risk = self.debt * 1.05
        sentiment = sum(SECTOR_MULTIPLIERS.get(a.sector, 1.0) for a in self.assets) / len(self.assets) if self.assets else 1.0
        return max(round((substance + cash_flow) * sentiment - debt_risk, 2), 0.0)

    def summary(self) -> str:
        assets = ", ".join([f"{a.name} ({a.value:.0f}, {a.sector})" for a in self.assets]) or "None"
        ownership = ", ".join([f"{name}: {share:.1f}%" for name, share in self.ownership_shares.items()])
        external = ", ".join([f"{name}: {share:.1f}%" for name, share in self.holdings.items()]) or "None"
        return (
            f"Balance: {self.balance:.0f} kr\n"
            f"Assets: {assets}\n"
            f"Ownership (this company): {ownership}\n"
            f"Holdings in others: {external}\n"
            f"Valuation: {self.valuation():.0f} kr\n"
            f"Annual cash flow: {self.cash_flow_per_year():.0f} kr"
        )

    # --- Ownership handling ---
    def share_for(self, name: str) -> float:
        return self.ownership_shares.get(name, 0.0)

    def buy_in_as_owner(self, buyer: "Actor", seller: "Actor", share: float) -> float:
        if share <= 0:
            raise ValueError("Share must be positive")
        if self.share_for(seller.name) < share:
            raise ValueError("Seller lacks that share")
        price = self.valuation() * (share / 100)
        if buyer.balance < price:
            raise ValueError("Buyer cannot afford the purchase")

        self.ownership_shares[seller.name] -= share
        if self.ownership_shares[seller.name] <= 0:
            del self.ownership_shares[seller.name]

        self.ownership_shares[buyer.name] = self.ownership_shares.get(buyer.name, 0) + share

        seller.adjust_balance(price)
        buyer.adjust_balance(-price)

        buyer.holdings[self.name] = self.ownership_shares[buyer.name]
        seller.holdings[self.name] = self.ownership_shares.get(seller.name, 0)
        if seller.holdings[self.name] == 0:
            del seller.holdings[self.name]

        return round(price, 2)

    def transfer_asset(self, buyer: "Actor", asset: Asset, price: Optional[float] = None) -> float:
        if asset not in self.assets:
            raise ValueError("Seller does not own the asset")
        cost = price if price is not None else asset.value
        if buyer.balance < cost:
            raise ValueError("Buyer cannot afford the asset")

        self.assets.remove(asset)
        buyer.assets.append(asset)
        buyer.adjust_balance(-cost)
        self.adjust_balance(cost)
        return round(cost, 2)

    def transfer_money(self, recipient: "Actor", amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        self.adjust_balance(-amount)
        recipient.adjust_balance(amount)

    def record_valuation(self) -> None:
        self.valuation_history.append(self.valuation())


Company = Actor


class GameState:
    """Container for actors and order."""

    def __init__(self):
        self.actors: Dict[str, Actor] = {}
        self.order: List[str] = []
        self.current_index: int = 0

    def add_actor(self, name: str, balance: float | None = None, sector: str = "Property", owner_name: str | None = None) -> Actor:
        if name in self.actors:
            raise ValueError("Actor already exists")
        actor = Actor(name, balance, owner_name)
        self.actors[name] = actor
        self.order.append(name)
        return actor

    def get_actor(self, name: str) -> Actor:
        return self.actors[name]

    def next_actor(self) -> Actor:
        if not self.order:
            raise ValueError("No actors added")
        actor_name = self.order[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.order)
        return self.actors[actor_name]

    def find_asset(self, name: str) -> Optional[Tuple[Actor, Asset]]:
        for actor in self.actors.values():
            for asset in actor.assets:
                if asset.name == name:
                    return actor, asset
        return None

    def record_all_valuations(self) -> None:
        for actor in self.actors.values():
            actor.record_valuation()
