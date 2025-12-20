"""Domänmodeller för Monopoly Plus GUI.

En aktör representerar både spelare och företag. Ett “år” motsvarar
att alla spelare gjort ett tärningsslag (ett varv), vilket används i
värderingen av aktörens kassaflöde.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from player_settings import settings


ROUNDS_PER_YEAR = 1

SECTOR_MULTIPLIERS: Dict[str, float] = {
    "Fastighet": 1.08,
    "Tåg": 0.95,
    "Statligt": 1.0,
}

SECTOR_MARGINS: Dict[str, float] = {
    "Fastighet": 0.3,
    "Tåg": 0.22,
    "Statligt": 0.18,
}


@dataclass
class Tillgang:
    """Enskild tillgång som påverkar en aktörs substansvärde."""

    namn: str
    vardering: float
    sektor: str = "Fastighet"
    kassaflode_per_varv: float = 0.0


class Aktor:
    """Representerar spelare och företag (samma typ av aktör)."""

    def __init__(self, namn: str, saldo: float | None = None, agare_namn: Optional[str] = None):
        self.namn = namn
        self.saldo = saldo if saldo is not None else settings["player"]["start_balance"]
        self.kassa: float = 0.0
        self.intakt_per_varv: float = 0.0
        self.tillvaxtforvantning: float = 0.02
        self.riskpremie: float = 0.08
        self.skulder: float = 0.0
        self.tillgangar: List[Tillgang] = []
        agare = agare_namn or namn
        self.agare_andelar: Dict[str, float] = {agare: 100.0}
        self.innehav: Dict[str, float] = {}
        self.vardehistorik: List[float] = []

    def justera_saldo(self, belopp: float) -> None:
        self.saldo = round(self.saldo + belopp, 2)

    def lagg_till_tillgang(self, namn: str, vardering: float, sektor: str, kassaflode_per_varv: float = 0.0) -> Tillgang:
        tillgang = Tillgang(
            namn=namn,
            vardering=vardering,
            sektor=sektor if sektor in SECTOR_MULTIPLIERS else "Fastighet",
            kassaflode_per_varv=kassaflode_per_varv,
        )
        self.tillgangar.append(tillgang)
        return tillgang

    def sammanfattning(self) -> str:
        asset_summary = ", ".join([f"{a.namn} ({a.vardering:.0f}, {a.sektor})" for a in self.tillgangar]) or "Inga"
        holdings = ", ".join([f"{namn}: {andel:.1f}%" for namn, andel in self.agare_andelar.items()])
        externa_innehav = ", ".join([f"{namn}: {andel:.1f}%" for namn, andel in self.innehav.items()]) or "Inga"
        return (
            f"Saldo: {self.saldo:.0f} kr\n"
            f"Tillgångar: {asset_summary}\n"
            f"Ägarandelar (i detta bolag): {holdings}\n"
            f"Innehav i andra bolag: {externa_innehav}\n"
            f"Beräknad värdering: {self.vardera():.0f} kr"
        )

    # --- Värdering ---
    def tillgangsvarde(self) -> float:
        direkt_varde = sum(t.vardering * SECTOR_MULTIPLIERS.get(t.sektor, 1.0) for t in self.tillgangar)
        diskonterat_flode = sum(t.kassaflode_per_varv for t in self.tillgangar) * ROUNDS_PER_YEAR * 4
        return direkt_varde + diskonterat_flode

    def kassaflodesmultipel(self) -> float:
        bas = 3 + (self.tillvaxtforvantning * 18)
        riskjustering = max(0.55, 1 - self.riskpremie)
        return max(2.0, bas * riskjustering)

    def varvskassaflode(self) -> float:
        return self.intakt_per_varv + sum(t.kassaflode_per_varv for t in self.tillgangar)

    def driftresultat_per_ar(self) -> float:
        total_flode = self.varvskassaflode()
        if total_flode == 0:
            marginal = 0
        else:
            viktade_marginaler = sum(
                (t.kassaflode_per_varv / total_flode) * SECTOR_MARGINS.get(t.sektor, SECTOR_MARGINS["Fastighet"])
                for t in self.tillgangar
            )
            marginal = viktade_marginaler
        return (total_flode * ROUNDS_PER_YEAR) * (marginal if marginal > 0 else SECTOR_MARGINS["Fastighet"])

    def vardera(self) -> float:
        substans = self.tillgangsvarde() + self.kassa
        kassaflode = self.driftresultat_per_ar() * self.kassaflodesmultipel()
        skuldrisk = self.skulder * 1.05
        sentiment = (
            sum(SECTOR_MULTIPLIERS.get(t.sektor, 1.0) for t in self.tillgangar) / len(self.tillgangar)
            if self.tillgangar
            else 1.0
        )
        return max(round((substans + kassaflode) * sentiment - skuldrisk, 2), 0.0)

    # --- Ägarhantering ---
    def andel_for(self, namn: str) -> float:
        return self.agare_andelar.get(namn, 0.0)

    def kop_in_som_agare(self, kopare: Aktor, saljare: Aktor, andel: float) -> float:
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

    def flytta_tillgang(self, kopare: Aktor, tillgang: Tillgang, pris: Optional[float] = None) -> float:
        if tillgang not in self.tillgangar:
            raise ValueError("Tillgången ägs inte av säljaren")
        kostnad = pris if pris is not None else tillgang.vardering
        if kopare.saldo < kostnad:
            raise ValueError("Köparen har inte råd med köpet")

        self.tillgangar.remove(tillgang)
        kopare.tillgangar.append(tillgang)
        kopare.justera_saldo(-kostnad)
        self.justera_saldo(kostnad)
        return round(kostnad, 2)

    def overfor_pengar(self, mottagare: Aktor, belopp: float) -> None:
        if belopp <= 0:
            raise ValueError("Beloppet måste vara positivt")
        if self.saldo < belopp:
            raise ValueError("Otillräckligt saldo")
        self.justera_saldo(-belopp)
        mottagare.justera_saldo(belopp)

    def registrera_varde(self) -> None:
        self.vardehistorik.append(self.vardera())

    # --- Finansiella uppdateringar ---
    def uppdatera_finansiellt(
        self,
        *,
        kassa: float | None = None,
        intakt_per_varv: float | None = None,
        skulder: float | None = None,
        tillvaxt: float | None = None,
        riskpremie: float | None = None,
    ) -> None:
        if kassa is not None:
            self.kassa = round(max(kassa, 0), 2)
        if intakt_per_varv is not None:
            self.intakt_per_varv = max(intakt_per_varv, 0)
        if skulder is not None:
            self.skulder = max(skulder, 0)
        if tillvaxt is not None:
            self.tillvaxtforvantning = max(min(tillvaxt, 0.25), -0.05)
        if riskpremie is not None:
            self.riskpremie = max(min(riskpremie, 0.4), 0.02)


# Typalias för bakåtkompatibilitet i GUI:t
Bolag = Aktor


class Spelstat:
    """Samlar aktörer för GUI:t."""

    def __init__(self):
        self.aktorer: Dict[str, Aktor] = {}
        self.ordning: List[str] = []
        self.current_index: int = 0

    def lagg_till_aktor(self, namn: str, saldo: float | None = None, sektor: str = "Fastighet", agare_namn: str | None = None) -> Aktor:
        if namn in self.aktorer:
            raise ValueError("Aktör finns redan")
        aktor = Aktor(namn, saldo, agare_namn)
        self.aktorer[namn] = aktor
        self.ordning.append(namn)
        return aktor

    def hamta_aktor(self, namn: str) -> Aktor:
        return self.aktorer[namn]

    def nasta_aktor(self) -> Aktor:
        if not self.ordning:
            raise ValueError("Inga aktörer tillagda")
        aktor_namn = self.ordning[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.ordning)
        return self.aktorer[aktor_namn]

    def hamta_tillgang(self, namn: str) -> tuple[Aktor, Tillgang] | None:
        for aktor in self.aktorer.values():
            for t in aktor.tillgangar:
                if t.namn == namn:
                    return aktor, t
        return None

    def registrera_varden(self) -> None:
        for aktor in self.aktorer.values():
            aktor.registrera_varde()
