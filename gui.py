"""Tkinter-baserad GUI för Monopoly Plus.

Ger en visuell översikt över spelare, deras bolag och möjliggör
aktieköp mellan spelare baserat på modellens värdering.
"""
from __future__ import annotations

import random
import tkinter as tk
from tkinter import messagebox, ttk

from game_models import SECTOR_MULTIPLIERS, Aktor, Bolag, Spelstat, Tillgang


class MonopolyPlusGUI:
    def __init__(self) -> None:
        self.state = Spelstat()
        self.root = tk.Tk()
        self.root.title("Monopoly Plus - Bolagsägarverktyg")
        self.root.geometry("1200x720")
        self.root.configure(background="#f5f5f5")

        self.selected_company: Bolag | None = None
        self.round_counter: int = 0
        self.active_actor: Aktor | None = None
        self.is_rolling: bool = False

        self._build_layout()
        self._refresh_company_table()
        self._update_turn_display()

    def _build_layout(self) -> None:
        header = tk.Label(
            self.root,
            text="Digitalt tillägg till Monopol: följ bolag, värderingar och ägarandelar",
            font=("Arial", 14, "bold"),
            bg="#f5f5f5",
        )
        header.pack(pady=(10, 5))

        content = tk.Frame(self.root, bg="#f5f5f5")
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_company_panel(content)
        self._build_trade_panel(content)
        self._build_dice_panel(content)

    def _build_company_panel(self, parent: tk.Widget) -> None:
        frame = tk.LabelFrame(parent, text="Bolag och värdering", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        add_frame = tk.Frame(frame, bg="#ffffff")
        add_frame.pack(fill=tk.X, pady=5)
        tk.Label(add_frame, text="Bolag/Spelare", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.new_company_name = tk.Entry(add_frame)
        self.new_company_name.grid(row=0, column=1, padx=5)
        tk.Label(add_frame, text="Startsaldo", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.player_balance = tk.Entry(add_frame)
        self.player_balance.insert(0, "1000")
        self.player_balance.grid(row=1, column=1, padx=5)
        tk.Button(add_frame, text="Lägg till bolag", command=self._handle_create_company).grid(
            row=0, column=2, rowspan=2, padx=10
        )

        columns = ("Störst ägare", "Värdering", "Huvudsektor", "Intäkt/varv", "Skulder")
        self.company_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.company_tree.heading(col, text=col)
        self.company_tree.column("Störst ägare", width=120)
        self.company_tree.column("Värdering", width=110)
        self.company_tree.column("Huvudsektor", width=110)
        self.company_tree.column("Intäkt/varv", width=90)
        self.company_tree.column("Skulder", width=80)
        self.company_tree.pack(fill=tk.BOTH, expand=True)
        self.company_tree.bind("<<TreeviewSelect>>", self._on_company_select)

        update_frame = tk.LabelFrame(frame, text="Finansiella nycklar", bg="#ffffff")
        update_frame.pack(fill=tk.X, pady=5)

        self.intakt_entry = self._labeled_entry(update_frame, "Intäkt per varv", 0)
        self.kassa_entry = self._labeled_entry(update_frame, "Kassa", 1)
        self.skulder_entry = self._labeled_entry(update_frame, "Skulder", 2)
        self.tillvaxt_entry = self._labeled_entry(update_frame, "Tillväxtförv. (0-0.25)", 3, default="0.02")
        self.risk_entry = self._labeled_entry(update_frame, "Riskpremie (0.02-0.4)", 4, default="0.08")

        tk.Button(update_frame, text="Uppdatera bolag", command=self._handle_update_company).grid(
            row=0, column=2, rowspan=2, padx=10
        )

        asset_frame = tk.LabelFrame(frame, text="Tillgångar", bg="#ffffff")
        asset_frame.pack(fill=tk.X, pady=5)
        self.asset_name = self._labeled_entry(asset_frame, "Namn", 0)
        self.asset_value = self._labeled_entry(asset_frame, "Värdering", 1)
        tk.Label(asset_frame, text="Sektor", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.asset_sector = ttk.Combobox(asset_frame, values=list(SECTOR_MULTIPLIERS), state="readonly")
        self.asset_sector.current(0)
        self.asset_sector.grid(row=2, column=1, padx=5, pady=2)
        self.asset_cashflow = self._labeled_entry(asset_frame, "Kassaflöde/varv", 3, default="0")
        tk.Button(asset_frame, text="Lägg till tillgång", command=self._handle_add_asset).grid(
            row=0, column=2, rowspan=4, padx=10
        )

        self.company_summary = tk.Text(frame, height=10, wrap=tk.WORD)
        self.company_summary.pack(fill=tk.BOTH, expand=True, pady=5)
        self.company_summary.config(state="disabled")

        balance_frame = tk.Frame(frame, bg="#ffffff")
        balance_frame.pack(fill=tk.X, pady=5)
        tk.Label(balance_frame, text="Saldojustering", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.balance_change = tk.Entry(balance_frame)
        self.balance_change.insert(0, "0")
        self.balance_change.grid(row=0, column=1, padx=5)
        tk.Button(balance_frame, text="Uppdatera saldo", command=self._handle_balance_change).grid(
            row=0, column=2, padx=5
        )

    def _build_trade_panel(self, parent: tk.Widget) -> None:
        frame = tk.LabelFrame(parent, text="Ägartransaktion", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Bolag", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.trade_company_var = tk.StringVar()
        self.trade_company_select = ttk.Combobox(frame, textvariable=self.trade_company_var, values=[])
        self.trade_company_select.grid(row=0, column=1, padx=5)
        self.trade_company_select.bind("<<ComboboxSelected>>", lambda _: self._update_trade_options())

        tk.Label(frame, text="Säljare", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.seller_var = tk.StringVar()
        self.seller_select = ttk.Combobox(frame, textvariable=self.seller_var, values=[])
        self.seller_select.grid(row=1, column=1, padx=5)

        tk.Label(frame, text="Köpare", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.buyer_var = tk.StringVar()
        self.buyer_select = ttk.Combobox(frame, textvariable=self.buyer_var, values=[])
        self.buyer_select.grid(row=2, column=1, padx=5)

        tk.Label(frame, text="Andel (%)", bg="#ffffff").grid(row=3, column=0, sticky="w")
        self.share_entry = tk.Entry(frame)
        self.share_entry.insert(0, "10")
        self.share_entry.grid(row=3, column=1, padx=5)

        self.price_label = tk.Label(frame, text="Pris: -", bg="#ffffff", font=("Arial", 11, "bold"))
        self.price_label.grid(row=4, column=0, columnspan=2, pady=5)

        tk.Button(frame, text="Beräkna pris", command=self._handle_calculate_price).grid(row=5, column=0, pady=5)
        tk.Button(frame, text="Genomför köp", command=self._handle_share_purchase).grid(row=5, column=1, pady=5)

        help_text = (
            "Värderingen bygger på kassaflöde, substans, skulder och sektor.\n"
            "Köparen betalar procentuell andel av värderingen direkt till säljaren."
        )
        tk.Label(frame, text=help_text, bg="#ffffff", wraplength=320, justify="left").grid(
            row=6, column=0, columnspan=2, pady=10
        )

        money_frame = tk.LabelFrame(frame, text="Överför pengar", bg="#ffffff")
        money_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=8)
        tk.Label(money_frame, text="Från", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.transfer_from = ttk.Combobox(money_frame, values=[])
        self.transfer_from.grid(row=0, column=1, padx=5)
        tk.Label(money_frame, text="Till", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.transfer_to = ttk.Combobox(money_frame, values=[])
        self.transfer_to.grid(row=1, column=1, padx=5)
        tk.Label(money_frame, text="Belopp", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.transfer_amount = tk.Entry(money_frame)
        self.transfer_amount.insert(0, "100")
        self.transfer_amount.grid(row=2, column=1, padx=5)
        tk.Button(money_frame, text="Genomför överföring", command=self._handle_money_transfer).grid(
            row=0, column=2, rowspan=3, padx=10
        )

        asset_trade = tk.LabelFrame(frame, text="Köp/Sälj tillgång", bg="#ffffff")
        asset_trade.grid(row=8, column=0, columnspan=2, sticky="ew", pady=8)
        tk.Label(asset_trade, text="Säljare", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.asset_seller_var = tk.StringVar()
        self.asset_seller_select = ttk.Combobox(asset_trade, textvariable=self.asset_seller_var, values=[])
        self.asset_seller_select.grid(row=0, column=1, padx=5)
        self.asset_seller_select.bind("<<ComboboxSelected>>", lambda _: self._populate_assets_for_seller())

        tk.Label(asset_trade, text="Tillgång", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.asset_select = ttk.Combobox(asset_trade, values=[])
        self.asset_select.grid(row=1, column=1, padx=5)

        tk.Label(asset_trade, text="Köpare", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.asset_buyer_select = ttk.Combobox(asset_trade, values=[])
        self.asset_buyer_select.grid(row=2, column=1, padx=5)

        tk.Label(asset_trade, text="Pris", bg="#ffffff").grid(row=3, column=0, sticky="w")
        self.asset_price_entry = tk.Entry(asset_trade)
        self.asset_price_entry.insert(0, "0")
        self.asset_price_entry.grid(row=3, column=1, padx=5)

        tk.Button(asset_trade, text="Genomför affär", command=self._handle_asset_sale).grid(row=0, column=2, rowspan=4, padx=10)

    def _build_dice_panel(self, parent: tk.Widget) -> None:
        frame = tk.LabelFrame(parent, text="Tärningsslag och rundor", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.turn_label = tk.Label(frame, text="Nästa aktör: -", bg="#ffffff", font=("Arial", 11, "bold"))
        self.turn_label.pack(anchor="w")
        self.round_label = tk.Label(frame, text="Genomförda varv: 0", bg="#ffffff")
        self.round_label.pack(anchor="w")

        dice_frame = tk.Frame(frame, bg="#ffffff")
        dice_frame.pack(pady=10)
        self.die1_label = tk.Label(dice_frame, text="🎲", font=("Arial", 32), bg="#ffffff")
        self.die1_label.grid(row=0, column=0, padx=10)
        self.die2_label = tk.Label(dice_frame, text="🎲", font=("Arial", 32), bg="#ffffff")
        self.die2_label.grid(row=0, column=1, padx=10)
        self.last_roll_label = tk.Label(frame, text="Senaste slag: -", bg="#ffffff")
        self.last_roll_label.pack()

        tk.Button(frame, text="Rulla tärningar", command=self._start_dice_roll).pack(pady=5)
        tk.Label(frame, text="Varje slag räknar som ett varv för aktuell aktör och justerar saldo med kassaflöde/varv.", bg="#ffffff", wraplength=260).pack(pady=5)

    def _labeled_entry(self, parent: tk.Widget, text: str, row: int, default: str = "") -> tk.Entry:
        tk.Label(parent, text=text, bg="#ffffff").grid(row=row, column=0, sticky="w")
        entry = tk.Entry(parent)
        entry.insert(0, default)
        entry.grid(row=row, column=1, padx=5, pady=2)
        return entry

    def _handle_balance_change(self) -> None:
        if not self.selected_company:
            messagebox.showwarning("Fel", "Välj ett bolag i listan")
            return
        try:
            belopp = float(self.balance_change.get())
        except ValueError:
            messagebox.showwarning("Fel", "Ange ett numeriskt belopp")
            return
        self.selected_company.justera_saldo(belopp)
        self._refresh_company_table()
        self._update_company_summary()

    def _handle_create_company(self) -> None:
        namn = self.new_company_name.get().strip()
        saldo_text = self.player_balance.get().strip()
        if not namn:
            messagebox.showwarning("Fel", "Bolagsnamn saknas")
            return
        try:
            saldo = float(saldo_text)
        except ValueError:
            messagebox.showwarning("Fel", "Startsaldo måste vara en siffra")
            return
        try:
            bolag = self.state.lagg_till_aktor(namn, saldo)
        except ValueError as exc:
            messagebox.showwarning("Fel", str(exc))
            return

        self.selected_company = bolag
        self.trade_company_var.set(bolag.namn)
        self._refresh_company_table()
        self.company_tree.selection_set(bolag.namn)
        self._update_trade_options()
        self._update_company_summary()

    def _refresh_company_table(self) -> None:
        for item in self.company_tree.get_children():
            self.company_tree.delete(item)
        for bolag in self.state.aktorer.values():
            agare = max(bolag.agare_andelar.items(), key=lambda item: item[1])[0]
            dom_sektor = self._dominant_sector(bolag)
            self.company_tree.insert(
                "",
                tk.END,
                iid=bolag.namn,
                values=(
                    agare,
                    f"{bolag.vardera():.0f} kr",
                    dom_sektor,
                    f"{bolag.intakt_per_varv:.0f}",
                    f"{bolag.skulder:.0f}",
                ),
            )
        self.trade_company_select["values"] = list(self.state.aktorer.keys())
        self._update_trade_options()
        self._update_turn_display()

    def _on_company_select(self, _event: tk.Event) -> None:
        selection = self.company_tree.selection()
        if not selection:
            return
        bolagsnamn = selection[0]
        self.selected_company = self.state.hamta_aktor(bolagsnamn)
        self.trade_company_var.set(bolagsnamn)
        self._update_trade_options()
        self._update_company_summary()

    def _handle_update_company(self) -> None:
        if not self.selected_company:
            messagebox.showwarning("Fel", "Välj ett bolag")
            return
        try:
            intakter = float(self.intakt_entry.get()) if self.intakt_entry.get() else None
            kassa = float(self.kassa_entry.get()) if self.kassa_entry.get() else None
            skulder = float(self.skulder_entry.get()) if self.skulder_entry.get() else None
            tillvaxt = float(self.tillvaxt_entry.get()) if self.tillvaxt_entry.get() else None
            risk = float(self.risk_entry.get()) if self.risk_entry.get() else None
        except ValueError:
            messagebox.showwarning("Fel", "Alla finansiella fält måste vara numeriska")
            return

        self.selected_company.uppdatera_finansiellt(
            kassa=kassa, intakt_per_varv=intakter, skulder=skulder, tillvaxt=tillvaxt, riskpremie=risk
        )
        self._refresh_company_table()
        self._update_company_summary()

    def _handle_add_asset(self) -> None:
        if not self.selected_company:
            messagebox.showwarning("Fel", "Välj ett bolag")
            return
        namn = self.asset_name.get().strip()
        if not namn:
            messagebox.showwarning("Fel", "Namn på tillgång saknas")
            return
        try:
            vardering = float(self.asset_value.get())
            kassaflode = float(self.asset_cashflow.get())
        except ValueError:
            messagebox.showwarning("Fel", "Ange numeriska värden för tillgången")
            return
        sektor = self.asset_sector.get() or list(SECTOR_MULTIPLIERS)[0]
        self.selected_company.lagg_till_tillgang(
            namn=namn, vardering=vardering, sektor=sektor, kassaflode_per_varv=kassaflode
        )
        self._update_company_summary()
        self._refresh_company_table()

    def _update_company_summary(self) -> None:
        if not self.selected_company:
            return
        self.company_summary.config(state="normal")
        self.company_summary.delete("1.0", tk.END)
        self.company_summary.insert(tk.END, self.selected_company.sammanfattning())
        self.company_summary.config(state="disabled")

    def _update_trade_options(self) -> None:
        aktor_namn = list(self.state.aktorer.keys())
        self.buyer_select["values"] = aktor_namn
        if self.selected_company:
            agare = list(self.selected_company.agare_andelar.keys())
        else:
            agare = aktor_namn
        self.seller_select["values"] = agare
        self.transfer_from["values"] = aktor_namn
        self.transfer_to["values"] = aktor_namn
        self.asset_buyer_select["values"] = aktor_namn
        self.asset_seller_select["values"] = aktor_namn
        self._populate_assets_for_seller()

    def _dominant_sector(self, aktor: Aktor) -> str:
        if not aktor.tillgangar:
            return "-"
        counts: Dict[str, int] = {}
        for t in aktor.tillgangar:
            counts[t.sektor] = counts.get(t.sektor, 0) + 1
        return max(counts.items(), key=lambda item: item[1])[0]

    def _update_turn_display(self) -> None:
        if not self.state.ordning:
            self.turn_label.config(text="Nästa aktör: -")
            return
        nasta = self.state.ordning[self.state.current_index]
        self.turn_label.config(text=f"Nästa aktör: {nasta}")
        self.round_label.config(text=f"Genomförda varv: {self.round_counter}")

    def _handle_calculate_price(self) -> None:
        bolag = self._get_trade_company()
        if not bolag:
            return
        andel = self._get_trade_percentage()
        if andel is None:
            return
        pris = bolag.vardera() * (andel / 100)
        self.price_label.config(text=f"Pris: {pris:.0f} kr")

    def _handle_share_purchase(self) -> None:
        bolag = self._get_trade_company()
        if not bolag:
            return
        andel = self._get_trade_percentage()
        if andel is None:
            return
        kopare_namn = self.buyer_var.get()
        saljare_namn = self.seller_var.get()
        if not kopare_namn or not saljare_namn:
            messagebox.showwarning("Fel", "Välj både köpare och säljare")
            return
        kopare = self.state.hamta_aktor(kopare_namn)
        saljare = self.state.hamta_aktor(saljare_namn)
        try:
            pris = bolag.kop_in_som_agare(kopare, saljare, andel)
        except ValueError as exc:
            messagebox.showwarning("Fel", str(exc))
            return

        messagebox.showinfo("Genomfört", f"Köpet genomfört för {pris:.0f} kr")
        self._refresh_company_table()
        self._update_company_summary()
        self._update_trade_options()

    def _handle_money_transfer(self) -> None:
        fran = self.transfer_from.get()
        till = self.transfer_to.get()
        if not fran or not till or fran == till:
            messagebox.showwarning("Fel", "Välj olika aktörer som avsändare och mottagare")
            return
        try:
            belopp = float(self.transfer_amount.get())
        except ValueError:
            messagebox.showwarning("Fel", "Belopp måste vara en siffra")
            return
        avsandare = self.state.hamta_aktor(fran)
        mottagare = self.state.hamta_aktor(till)
        try:
            avsandare.overfor_pengar(mottagare, belopp)
        except ValueError as exc:
            messagebox.showwarning("Fel", str(exc))
            return
        self._refresh_company_table()
        self._update_company_summary()

    def _populate_assets_for_seller(self) -> None:
        seller_name = self.asset_seller_var.get()
        if not seller_name:
            self.asset_select["values"] = []
            return
        seller = self.state.hamta_aktor(seller_name)
        names = [t.namn for t in seller.tillgangar]
        self.asset_select["values"] = names
        if names:
            self.asset_select.current(0)
            self.asset_price_entry.delete(0, tk.END)
            self.asset_price_entry.insert(0, f"{seller.tillgangar[0].vardering:.0f}")

    def _handle_asset_sale(self) -> None:
        seller_name = self.asset_seller_var.get()
        buyer_name = self.asset_buyer_select.get()
        asset_name = self.asset_select.get()
        if not seller_name or not buyer_name or not asset_name:
            messagebox.showwarning("Fel", "Välj säljare, köpare och tillgång")
            return
        if seller_name == buyer_name:
            messagebox.showwarning("Fel", "Säljare och köpare måste vara olika")
            return
        seller = self.state.hamta_aktor(seller_name)
        buyer = self.state.hamta_aktor(buyer_name)
        tillgang = next((t for t in seller.tillgangar if t.namn == asset_name), None)
        if not tillgang:
            messagebox.showwarning("Fel", "Tillgången hittades inte hos säljaren")
            return
        try:
            pris = float(self.asset_price_entry.get()) if self.asset_price_entry.get() else tillgang.vardering
        except ValueError:
            messagebox.showwarning("Fel", "Pris måste vara numeriskt")
            return
        try:
            seller.flytta_tillgang(buyer, tillgang, pris)
        except ValueError as exc:
            messagebox.showwarning("Fel", str(exc))
            return
        self._refresh_company_table()
        self._update_company_summary()
        self._update_trade_options()
        self._update_turn_display()

    def _start_dice_roll(self) -> None:
        if self.is_rolling:
            return
        if not self.state.aktorer:
            messagebox.showwarning("Fel", "Lägg till aktörer innan du rullar tärningarna")
            return
        self.active_actor = self.state.nasta_aktor()
        if self.state.current_index == 0:
            self.round_counter += 1
        self.is_rolling = True
        self._animate_dice(8)

    def _animate_dice(self, steps: int) -> None:
        if steps > 0:
            self.die1_label.config(text=str(random.randint(1, 6)))
            self.die2_label.config(text=str(random.randint(1, 6)))
            self.root.after(90, lambda: self._animate_dice(steps - 1))
        else:
            final1 = random.randint(1, 6)
            final2 = random.randint(1, 6)
            self.die1_label.config(text=str(final1))
            self.die2_label.config(text=str(final2))
            total = final1 + final2
            self.last_roll_label.config(text=f"Senaste slag: {total}")
            if self.active_actor:
                self._apply_turn_effects(self.active_actor)
            self.is_rolling = False

    def _apply_turn_effects(self, actor: Aktor) -> None:
        kassaflode = actor.varvskassaflode()
        actor.justera_saldo(kassaflode)
        self._refresh_company_table()
        self._update_company_summary()
        self._update_turn_display()
        messagebox.showinfo(
            "Varv klart",
            f"{actor.namn} slog tärningarna.\nKassaflöde för varvet: {kassaflode:.0f} kr till saldot.",
        )

    def _get_trade_company(self) -> Bolag | None:
        bolagsnamn = self.trade_company_var.get()
        if not bolagsnamn:
            messagebox.showwarning("Fel", "Välj bolag")
            return None
        bolag = self.state.hamta_aktor(bolagsnamn)
        self.selected_company = bolag
        return bolag

    def _get_trade_percentage(self) -> float | None:
        try:
            andel = float(self.share_entry.get())
        except ValueError:
            messagebox.showwarning("Fel", "Andel måste vara en siffra")
            return None
        if andel <= 0 or andel > 100:
            messagebox.showwarning("Fel", "Andelen måste vara mellan 0 och 100")
            return None
        return andel

    def run(self) -> None:
        self.root.mainloop()


def start_gui() -> None:
    MonopolyPlusGUI().run()


if __name__ == "__main__":
    start_gui()
