"""Tkinter-baserad GUI för Monopoly Plus.

Ger en visuell översikt över spelare, deras bolag och möjliggör
aktieköp mellan spelare baserat på modellens värdering.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from game_models import (
    SECTOR_MULTIPLIERS,
    Anvandare,
    Bolag,
    Spelstat,
    Tillgang,
)


class MonopolyPlusGUI:
    def __init__(self) -> None:
        self.state = Spelstat()
        self.root = tk.Tk()
        self.root.title("Monopoly Plus - Bolagsägarverktyg")
        self.root.geometry("1200x720")
        self.root.configure(background="#f5f5f5")

        self.selected_company: Bolag | None = None
        self.selected_player: Anvandare | None = None

        self._build_layout()
        self._refresh_player_list()
        self._refresh_company_table()

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

        self._build_player_panel(content)
        self._build_company_panel(content)
        self._build_trade_panel(content)

    def _build_player_panel(self, parent: tk.Widget) -> None:
        frame = tk.LabelFrame(parent, text="Spelare", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        add_frame = tk.Frame(frame, bg="#ffffff")
        add_frame.pack(fill=tk.X, pady=5)

        tk.Label(add_frame, text="Namn", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.player_name = tk.Entry(add_frame)
        self.player_name.grid(row=0, column=1, padx=5)

        tk.Label(add_frame, text="Startsaldo", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.player_balance = tk.Entry(add_frame)
        self.player_balance.insert(0, "1000")
        self.player_balance.grid(row=1, column=1, padx=5)

        tk.Button(add_frame, text="Lägg till spelare", command=self._handle_add_player).grid(
            row=0, column=2, rowspan=2, padx=10
        )

        self.player_list = tk.Listbox(frame, height=10)
        self.player_list.pack(fill=tk.BOTH, expand=True, pady=5)
        self.player_list.bind("<<ListboxSelect>>", self._on_player_select)

        balance_frame = tk.Frame(frame, bg="#ffffff")
        balance_frame.pack(fill=tk.X, pady=5)
        tk.Label(balance_frame, text="Saldojustering", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.balance_change = tk.Entry(balance_frame)
        self.balance_change.insert(0, "0")
        self.balance_change.grid(row=0, column=1, padx=5)
        tk.Button(balance_frame, text="Uppdatera saldo", command=self._handle_balance_change).grid(
            row=0, column=2, padx=5
        )

        asset_frame = tk.Frame(frame, bg="#ffffff")
        asset_frame.pack(fill=tk.X, pady=5)
        tk.Label(asset_frame, text="Tillgång", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.player_asset_name = tk.Entry(asset_frame)
        self.player_asset_name.grid(row=0, column=1, padx=5)
        tk.Label(asset_frame, text="Värde", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.player_asset_value = tk.Entry(asset_frame)
        self.player_asset_value.insert(0, "0")
        self.player_asset_value.grid(row=1, column=1, padx=5)
        tk.Button(asset_frame, text="Lägg till ägd tillgång", command=self._handle_add_player_asset).grid(
            row=0, column=2, rowspan=2, padx=10
        )

        company_frame = tk.Frame(frame, bg="#ffffff")
        company_frame.pack(fill=tk.X, pady=5)
        tk.Label(company_frame, text="Nytt bolag", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.new_company_name = tk.Entry(company_frame)
        self.new_company_name.grid(row=0, column=1, padx=5)
        self.sector_var = tk.StringVar(value="Allmänt")
        self.sector_select = ttk.Combobox(company_frame, textvariable=self.sector_var, values=list(SECTOR_MULTIPLIERS))
        self.sector_select.grid(row=0, column=2, padx=5)
        tk.Button(company_frame, text="Skapa bolag", command=self._handle_create_company).grid(
            row=0, column=3, padx=5
        )

        summary_frame = tk.LabelFrame(frame, text="Detaljer", bg="#ffffff")
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.player_summary = tk.Text(summary_frame, height=8, wrap=tk.WORD)
        self.player_summary.pack(fill=tk.BOTH, expand=True)
        self.player_summary.config(state="disabled")

    def _build_company_panel(self, parent: tk.Widget) -> None:
        frame = tk.LabelFrame(parent, text="Bolag och värdering", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("Ägare", "Värdering", "Sektor", "Intäkter", "Skulder")
        self.company_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.company_tree.heading(col, text=col)
        self.company_tree.column("Ägare", width=120)
        self.company_tree.column("Värdering", width=110)
        self.company_tree.column("Sektor", width=90)
        self.company_tree.column("Intäkter", width=90)
        self.company_tree.column("Skulder", width=80)
        self.company_tree.pack(fill=tk.BOTH, expand=True)
        self.company_tree.bind("<<TreeviewSelect>>", self._on_company_select)

        update_frame = tk.LabelFrame(frame, text="Finansiella nycklar", bg="#ffffff")
        update_frame.pack(fill=tk.X, pady=5)

        self.intakt_entry = self._labeled_entry(update_frame, "Årliga intäkter", 0)
        self.kassa_entry = self._labeled_entry(update_frame, "Kassa", 1)
        self.skulder_entry = self._labeled_entry(update_frame, "Skulder", 2)
        self.tillvaxt_entry = self._labeled_entry(update_frame, "Tillväxtförv. (0-0.25)", 3, default="0.03")
        self.risk_entry = self._labeled_entry(update_frame, "Riskpremie (0.02-0.4)", 4, default="0.08")

        tk.Button(update_frame, text="Uppdatera bolag", command=self._handle_update_company).grid(
            row=0, column=2, rowspan=2, padx=10
        )

        asset_frame = tk.LabelFrame(frame, text="Tillgångar", bg="#ffffff")
        asset_frame.pack(fill=tk.X, pady=5)
        self.asset_name = self._labeled_entry(asset_frame, "Namn", 0)
        self.asset_value = self._labeled_entry(asset_frame, "Värdering", 1)
        self.asset_cashflow = self._labeled_entry(asset_frame, "Årligt kassaflöde", 2, default="0")
        tk.Button(asset_frame, text="Lägg till tillgång", command=self._handle_add_asset).grid(
            row=0, column=2, rowspan=3, padx=10
        )

        self.company_summary = tk.Text(frame, height=10, wrap=tk.WORD)
        self.company_summary.pack(fill=tk.BOTH, expand=True, pady=5)
        self.company_summary.config(state="disabled")

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

    def _labeled_entry(self, parent: tk.Widget, text: str, row: int, default: str = "") -> tk.Entry:
        tk.Label(parent, text=text, bg="#ffffff").grid(row=row, column=0, sticky="w")
        entry = tk.Entry(parent)
        entry.insert(0, default)
        entry.grid(row=row, column=1, padx=5, pady=2)
        return entry

    def _handle_add_player(self) -> None:
        namn = self.player_name.get().strip()
        saldo_text = self.player_balance.get().strip()
        if not namn:
            messagebox.showwarning("Fel", "Ange ett namn på spelaren")
            return
        try:
            saldo = float(saldo_text)
        except ValueError:
            messagebox.showwarning("Fel", "Startsaldo måste vara en siffra")
            return
        try:
            self.state.lagg_till_anvandare(namn, saldo)
        except ValueError as exc:
            messagebox.showwarning("Fel", str(exc))
            return

        self.player_name.delete(0, tk.END)
        self._refresh_player_list()

    def _refresh_player_list(self) -> None:
        self.player_list.delete(0, tk.END)
        for namn, anv in self.state.anvandare.items():
            self.player_list.insert(tk.END, f"{namn} - {anv.saldo:.0f} kr")
        self._update_trade_options()

    def _on_player_select(self, _event: tk.Event) -> None:
        selection = self.player_list.curselection()
        if not selection:
            return
        namn = self.player_list.get(selection[0]).split(" - ")[0]
        self.selected_player = self.state.hamta_anvandare(namn)
        self._update_player_summary()

    def _handle_balance_change(self) -> None:
        if not self.selected_player:
            messagebox.showwarning("Fel", "Välj en spelare först")
            return
        try:
            belopp = float(self.balance_change.get())
        except ValueError:
            messagebox.showwarning("Fel", "Ange ett numeriskt belopp")
            return
        self.selected_player.justera_saldo(belopp)
        self._refresh_player_list()
        self._update_player_summary()

    def _handle_add_player_asset(self) -> None:
        if not self.selected_player:
            messagebox.showwarning("Fel", "Välj en spelare först")
            return
        namn = self.player_asset_name.get().strip()
        if not namn:
            messagebox.showwarning("Fel", "Namn på tillgång saknas")
            return
        try:
            vardering = float(self.player_asset_value.get())
        except ValueError:
            messagebox.showwarning("Fel", "Värdering måste vara numerisk")
            return
        self.selected_player.lagg_till_tillgang(namn, vardering)
        self.player_asset_name.delete(0, tk.END)
        self.player_asset_value.delete(0, tk.END)
        self.player_asset_value.insert(0, "0")
        self._update_player_summary()

    def _update_player_summary(self) -> None:
        if not self.selected_player:
            return
        self.player_summary.config(state="normal")
        self.player_summary.delete("1.0", tk.END)
        self.player_summary.insert(tk.END, self.selected_player.sammanfattning())
        self.player_summary.config(state="disabled")

    def _handle_create_company(self) -> None:
        if not self.selected_player:
            messagebox.showwarning("Fel", "Välj en spelare som ägare")
            return
        namn = self.new_company_name.get().strip()
        if not namn:
            messagebox.showwarning("Fel", "Bolagsnamn saknas")
            return
        sektor = self.sector_var.get()
        try:
            bolag = self.state.skapa_bolag(self.selected_player.namn, namn, sektor)
        except ValueError as exc:
            messagebox.showwarning("Fel", str(exc))
            return

        self.selected_company = bolag
        self.trade_company_var.set(bolag.namn)
        self._refresh_company_table()
        self._update_trade_options()
        self._update_company_summary()

    def _refresh_company_table(self) -> None:
        for item in self.company_tree.get_children():
            self.company_tree.delete(item)
        for bolag in self.state.bolag.values():
            agare = max(bolag.agare_andelar.items(), key=lambda item: item[1])[0]
            self.company_tree.insert(
                "",
                tk.END,
                iid=bolag.namn,
                values=(
                    agare,
                    f"{bolag.vardera():.0f} kr",
                    bolag.sektor,
                    f"{bolag.arliga_intakter:.0f}",
                    f"{bolag.skulder:.0f}",
                ),
            )
        self.trade_company_select["values"] = list(self.state.bolag.keys())

    def _on_company_select(self, _event: tk.Event) -> None:
        selection = self.company_tree.selection()
        if not selection:
            return
        bolagsnamn = selection[0]
        self.selected_company = self.state.hamta_bolag(bolagsnamn)
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
            kassa=kassa, intakter=intakter, skulder=skulder, tillvaxt=tillvaxt, riskpremie=risk
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
        tillgang = Tillgang(namn=namn, vardering=vardering, kassaflode=kassaflode)
        self.selected_company.lagg_till_tillgang(tillgang)
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
        self.buyer_select["values"] = list(self.state.anvandare.keys())
        if self.selected_company:
            agare = list(self.selected_company.agare_andelar.keys())
        else:
            agare = []
        self.seller_select["values"] = agare

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
        kopare = self.state.hamta_anvandare(kopare_namn)
        saljare = self.state.hamta_anvandare(saljare_namn)
        try:
            pris = bolag.kop_in_som_agare(kopare, saljare, andel)
        except ValueError as exc:
            messagebox.showwarning("Fel", str(exc))
            return

        messagebox.showinfo("Genomfört", f"Köpet genomfört för {pris:.0f} kr")
        self._refresh_company_table()
        self._refresh_player_list()
        self._update_company_summary()
        self._update_player_summary()
        self._update_trade_options()

    def _get_trade_company(self) -> Bolag | None:
        bolagsnamn = self.trade_company_var.get()
        if not bolagsnamn:
            messagebox.showwarning("Fel", "Välj bolag")
            return None
        bolag = self.state.hamta_bolag(bolagsnamn)
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
