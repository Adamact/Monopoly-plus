"""Domänmodeller för Monopoly Plus GUI.

Innehåller klasser för användare, bolag och tillgångar med
värderingslogik som efterliknar verkliga faktorer som kassaflöde,
väntad tillväxt och skuldsättning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from player_settings import settings


SECTOR_MULTIPLIERS: Dict[str, float] = {
    "Allmänt": 1.0,
    "Teknik": 1.12,
    "Industri": 1.02,
    "Finans": 0.95,
    "Fastighet": 1.05,
}

SECTOR_MARGINS: Dict[str, float] = {
    "Allmänt": 0.18,
    "Teknik": 0.26,
    "Industri": 0.2,
    "Finans": 0.24,
    "Fastighet": 0.3,
}


@dataclass
class Tillgang:
    """Enskild tillgång som påverkar ett bolags substansvärde."""

    namn: str
    vardering: float
    kassaflode: float = 0.0


class Anvandare:
    """Representerar en spelare och dess resurser."""

    def __init__(self, namn: str, saldo: float | None = None):
        self.namn = namn
        self.saldo = saldo if saldo is not None else settings["player"]["start_balance"]
        self.tillgangar: List[Tillgang] = []
        self.innehav: Dict[str, float] = {}
        self.bolag: Dict[str, Bolag] = {}

    def justera_saldo(self, belopp: float) -> None:
        self.saldo = round(self.saldo + belopp, 2)

    def lagg_till_tillgang(self, namn: str, vardering: float, kassaflode: float = 0.0) -> Tillgang:
        tillgang = Tillgang(namn=namn, vardering=vardering, kassaflode=kassaflode)
        self.tillgangar.append(tillgang)
        return tillgang

    def skapa_bolag(self, namn: str, sektor: str = "Allmänt") -> "Bolag":
        bolag = Bolag(namn=namn, agare=self, sektor=sektor)
        self.bolag[namn] = bolag
        self.innehav[namn] = 100.0
        return bolag

    def sammanfattning(self) -> str:
        asset_summary = ", ".join([f"{a.namn} ({a.vardering:.0f})" for a in self.tillgangar]) or "Inga"
        holdings = ", ".join([f"{bolag}: {andel:.1f}%" for bolag, andel in self.innehav.items()]) or "Inga"
        return (
            f"Saldo: {self.saldo:.0f} kr\n"
            f"Tillgångar: {asset_summary}\n"
            f"Ägarandelar: {holdings}"
        )


class Bolag:
    """Företag som värderas utifrån kassaflöde, tillgångar och skulder."""

    def __init__(self, namn: str, agare: Anvandare, sektor: str = "Allmänt"):
        self.namn = namn
        self.agare = agare
        self.sektor = sektor if sektor in SECTOR_MULTIPLIERS else "Allmänt"
        self.kassa: float = 0.0
        self.arliga_intakter: float = 0.0
        self.tillvaxtforvantning: float = 0.03
        self.riskpremie: float = 0.08
        self.skulder: float = 0.0
        self.tillgangar: List[Tillgang] = []
        self.agare_andelar: Dict[str, float] = {agare.namn: 100.0}

    def tillgangsvarde(self) -> float:
        direkt_varde = sum(t.vardering for t in self.tillgangar)
        diskonterat_flode = sum(t.kassaflode for t in self.tillgangar) * 3
        return direkt_varde + diskonterat_flode

    def kassaflodesmultipel(self) -> float:
        bas = 4 + (self.tillvaxtforvantning * 20)
        riskjustering = max(0.6, 1 - self.riskpremie)
        return max(2.0, bas * riskjustering)

    def driftresultat(self) -> float:
        marginal = SECTOR_MARGINS.get(self.sektor, SECTOR_MARGINS["Allmänt"])
        return self.arliga_intakter * marginal

    def vardera(self) -> float:
        substans = self.tillgangsvarde() + self.kassa
        kassaflode = self.driftresultat() * self.kassaflodesmultipel()
        skuldrisk = self.skulder * 1.05
        sentiment = SECTOR_MULTIPLIERS.get(self.sektor, 1.0)
        return max(round((substans + kassaflode) * sentiment - skuldrisk, 2), 0.0)

    def andel_for(self, namn: str) -> float:
        return self.agare_andelar.get(namn, 0.0)

    def uppdatera_finansiellt(self, *, kassa: float | None = None, intakter: float | None = None,
                              skulder: float | None = None, tillvaxt: float | None = None,
                              riskpremie: float | None = None) -> None:
        if kassa is not None:
            self.kassa = round(max(kassa, 0), 2)
        if intakter is not None:
            self.arliga_intakter = max(intakter, 0)
        if skulder is not None:
            self.skulder = max(skulder, 0)
        if tillvaxt is not None:
            self.tillvaxtforvantning = max(min(tillvaxt, 0.25), -0.05)
        if riskpremie is not None:
            self.riskpremie = max(min(riskpremie, 0.4), 0.02)

    def lagg_till_tillgang(self, tillgang: Tillgang) -> None:
        self.tillgangar.append(tillgang)

    def kop_in_som_agare(self, kopare: Anvandare, saljare: Anvandare, andel: float) -> float:
        if andel <= 0:
            raise ValueError("Andelen måste vara positiv")
        if self.andel_for(saljare.namn) < andel:
            raise ValueError("Säljaren saknar angiven andel")
        pris = self.vardera() * (andel / 100)
        if kopare.saldo < pris:
            raise ValueError("Köparen har inte råd med köpet")

        self.agare_andelar[saljare.namn] -= andel
        if self.agare_andelar[saljare.namn] <= 0:
            del self.agare_andelar[saljare.namn]

        self.agare_andelar[kopare.namn] = self.agare_andelar.get(kopare.namn, 0) + andel

        saljare.justera_saldo(pris)
        kopare.justera_saldo(-pris)

        kopare.innehav[self.namn] = self.agare_andelar[kopare.namn]
        saljare.innehav[self.namn] = self.agare_andelar.get(saljare.namn, 0)
        if saljare.innehav[self.namn] == 0:
            del saljare.innehav[self.namn]

        return round(pris, 2)

    def sammanfattning(self) -> str:
        tillgangar = ", ".join([f"{t.namn} ({t.vardering:.0f} kr)" for t in self.tillgangar]) or "Inga"
        agare = ", ".join([f"{namn}: {andel:.1f}%" for namn, andel in self.agare_andelar.items()])
        return (
            f"Sektor: {self.sektor}\n"
            f"Värdering: {self.vardera():.0f} kr\n"
            f"Kassa: {self.kassa:.0f} kr, Skulder: {self.skulder:.0f} kr\n"
            f"Årliga intäkter: {self.arliga_intakter:.0f} kr\n"
            f"Tillgångar: {tillgangar}\n"
            f"Ägare: {agare}"
        )


class Spelstat:
    """Samlar spelare och bolag för GUI:t."""

    def __init__(self):
        self.anvandare: Dict[str, Anvandare] = {}
        self.bolag: Dict[str, Bolag] = {}

    def lagg_till_anvandare(self, namn: str, saldo: float | None = None) -> Anvandare:
        if namn in self.anvandare:
            raise ValueError("Spelare finns redan")
        anv = Anvandare(namn, saldo)
        self.anvandare[namn] = anv
        return anv

    def skapa_bolag(self, agare_namn: str, bolagsnamn: str, sektor: str = "Allmänt") -> Bolag:
        if bolagsnamn in self.bolag:
            raise ValueError("Bolagsnamnet används redan")
        agare = self.anvandare[agare_namn]
        bolag = agare.skapa_bolag(bolagsnamn, sektor)
        self.bolag[bolag.namn] = bolag
        return bolag

    def hamta_anvandare(self, namn: str) -> Anvandare:
        return self.anvandare[namn]

    def hamta_bolag(self, namn: str) -> Bolag:
        return self.bolag[namn]
