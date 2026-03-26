"""Tkinter GUI for Monopoly Plus.

Players are companies; each full turn across players is considered a year.
Financial metrics are derived automatically from assets and transactions.
"""
from __future__ import annotations

import copy
import random
import tkinter as tk
from tkinter import ttk

from game_models import Company, GameState, SECTOR_MULTIPLIERS
from theme import COLORS, FONTS, CHART_COLORS, configure_styles
from widgets import StyledButton, DiceFace, ToastOverlay


class MonopolyPlusGUI:
    def __init__(self) -> None:
        self.state = GameState()
        self.root = tk.Tk()
        self.root.title("Monopoly Plus")
        self.root.geometry("1400x820")
        self.root.configure(background=COLORS["bg_primary"])
        self.root.minsize(1100, 700)

        configure_styles(self.root)

        self.selected_company: Company | None = None
        self.year_counter: int = 0
        self.active_company: Company | None = None
        self.is_rolling: bool = False
        self.undo_stack: list[GameState] = []

        self.toast = ToastOverlay(self.root)

        self._build_layout()
        self._refresh_company_table()
        self._update_turn_display()
        self.root.bind("<Control-z>", lambda event: self._handle_undo())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        # Header bar
        header_bar = tk.Frame(self.root, bg=COLORS["bg_secondary"], height=52)
        header_bar.pack(fill=tk.X)
        header_bar.pack_propagate(False)

        tk.Label(
            header_bar,
            text="Monopoly Plus",
            font=FONTS["app_title"],
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_primary"],
        ).pack(side=tk.LEFT, padx=20, pady=10)

        # Turn/year info in header right side
        header_right = tk.Frame(header_bar, bg=COLORS["bg_secondary"])
        header_right.pack(side=tk.RIGHT, padx=20)
        self.turn_label = tk.Label(
            header_right,
            text="Next: \u2014",
            bg=COLORS["bg_secondary"],
            fg=COLORS["accent_green"],
            font=FONTS["value"],
        )
        self.turn_label.pack(side=tk.LEFT, padx=(0, 16))
        self.year_label = tk.Label(
            header_right,
            text="Year 0",
            bg=COLORS["bg_secondary"],
            fg=COLORS["accent_gold"],
            font=FONTS["value"],
        )
        self.year_label.pack(side=tk.LEFT)

        # Main content – three columns via grid
        content = tk.Frame(self.root, bg=COLORS["bg_primary"])
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        content.columnconfigure(0, weight=5)
        content.columnconfigure(1, weight=4)
        content.columnconfigure(2, weight=3)
        content.rowconfigure(0, weight=1)

        self._build_company_panel(content)
        self._build_trade_panel(content)
        self._build_dice_panel(content)

    # ------------------------------------------------------------------
    # Company panel (left)
    # ------------------------------------------------------------------
    def _build_company_panel(self, parent: tk.Widget) -> None:
        col = tk.Frame(parent, bg=COLORS["bg_primary"])
        col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        col.rowconfigure(2, weight=1)  # treeview expands
        col.rowconfigure(4, weight=1)  # summary expands

        # -- Panel title --
        tk.Label(col, text="Companies", font=FONTS["panel_title"],
                 bg=COLORS["bg_primary"], fg=COLORS["text_primary"]).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        # -- Add company card --
        card = self._card(col)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        add_frame = tk.Frame(card, bg=COLORS["bg_secondary"])
        add_frame.pack(fill=tk.X)
        self._label(add_frame, "Company / Player").grid(row=0, column=0, sticky="w", pady=2)
        self.new_company_name = self._entry(add_frame)
        self.new_company_name.grid(row=0, column=1, padx=8, pady=2, sticky="ew")
        self._label(add_frame, "Starting balance").grid(row=1, column=0, sticky="w", pady=2)
        self.player_balance = self._entry(add_frame, default="1000")
        self.player_balance.grid(row=1, column=1, padx=8, pady=2, sticky="ew")
        add_frame.columnconfigure(1, weight=1)
        StyledButton(add_frame, "Add company", self._handle_create_company, style="primary").grid(
            row=0, column=2, rowspan=2, padx=(8, 0), pady=2)
        self._bind_enter(self.new_company_name, self._handle_create_company)
        self._bind_enter(self.player_balance, self._handle_create_company)

        # -- Company table --
        tree_frame = tk.Frame(col, bg=COLORS["bg_secondary"])
        tree_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 6))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        columns = ("Top owner", "Valuation", "Main sector", "Cash flow/yr", "Debt")
        self.company_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        for c in columns:
            self.company_tree.heading(c, text=c)
        self.company_tree.column("Top owner", width=120, minwidth=80)
        self.company_tree.column("Valuation", width=100, minwidth=70)
        self.company_tree.column("Main sector", width=100, minwidth=70)
        self.company_tree.column("Cash flow/yr", width=100, minwidth=70)
        self.company_tree.column("Debt", width=70, minwidth=50)
        self.company_tree.grid(row=0, column=0, sticky="nsew")
        self.company_tree.bind("<<TreeviewSelect>>", self._on_company_select)
        self.company_tree.bind("<Motion>", self._on_tree_motion)
        self.company_tree.tag_configure("hover", background=COLORS["bg_tertiary"])
        self.company_tree.tag_configure("even", background=COLORS["row_even"])
        self.company_tree.tag_configure("odd", background=COLORS["row_odd"])

        # -- Assets card --
        assets_card = self._card(col)
        assets_card.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        tk.Label(assets_card, text="Add Asset", font=FONTS["section_label"],
                 bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).pack(anchor="w")
        af = tk.Frame(assets_card, bg=COLORS["bg_secondary"])
        af.pack(fill=tk.X, pady=(4, 0))
        af.columnconfigure(1, weight=1)
        self.asset_name = self._labeled_entry(af, "Name", 0)
        self.asset_value = self._labeled_entry(af, "Value", 1)
        self._label(af, "Sector").grid(row=2, column=0, sticky="w", pady=2)
        self.asset_sector = ttk.Combobox(af, values=list(SECTOR_MULTIPLIERS), state="readonly")
        self.asset_sector.current(0)
        self.asset_sector.grid(row=2, column=1, padx=8, pady=2, sticky="ew")
        self.asset_cashflow = self._labeled_entry(af, "Cash flow/yr", 3, default="0")
        StyledButton(af, "Add asset", self._handle_add_asset, style="secondary").grid(
            row=0, column=2, rowspan=4, padx=(8, 0))
        self._bind_enter(self.asset_name, self._handle_add_asset)
        self._bind_enter(self.asset_value, self._handle_add_asset)
        self._bind_enter(self.asset_cashflow, self._handle_add_asset)

        # -- Company summary --
        self.company_summary = tk.Text(
            col, height=10, wrap=tk.WORD,
            bg=COLORS["bg_tertiary"], fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            selectbackground=COLORS["accent_blue"],
            selectforeground="#ffffff",
            font=FONTS["mono"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_subtle"],
            padx=10, pady=8,
        )
        self.company_summary.grid(row=4, column=0, sticky="nsew", pady=(0, 6))
        self.company_summary.config(state="disabled")

        # -- Balance adjustment --
        bal_card = self._card(col)
        bal_card.grid(row=5, column=0, sticky="ew")
        bf = tk.Frame(bal_card, bg=COLORS["bg_secondary"])
        bf.pack(fill=tk.X)
        bf.columnconfigure(1, weight=1)
        self._label(bf, "Balance adjustment").grid(row=0, column=0, sticky="w")
        self.balance_change = self._entry(bf, default="0")
        self.balance_change.grid(row=0, column=1, padx=8, sticky="ew")
        StyledButton(bf, "Apply", self._handle_balance_change, style="secondary").grid(row=0, column=2)
        self._bind_enter(self.balance_change, self._handle_balance_change)

    # ------------------------------------------------------------------
    # Transactions panel (center)
    # ------------------------------------------------------------------
    def _build_trade_panel(self, parent: tk.Widget) -> None:
        col = tk.Frame(parent, bg=COLORS["bg_primary"])
        col.grid(row=0, column=1, sticky="nsew", padx=6)

        tk.Label(col, text="Transactions", font=FONTS["panel_title"],
                 bg=COLORS["bg_primary"], fg=COLORS["text_primary"]).pack(anchor="w", pady=(0, 6))

        # -- Share trading --
        share_card = self._card(col)
        share_card.pack(fill=tk.X, pady=(0, 6))
        tk.Label(share_card, text="Share Trading", font=FONTS["section_label"],
                 bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).pack(anchor="w")
        sf = tk.Frame(share_card, bg=COLORS["bg_secondary"])
        sf.pack(fill=tk.X, pady=(4, 0))
        sf.columnconfigure(1, weight=1)

        self._label(sf, "Company").grid(row=0, column=0, sticky="w", pady=2)
        self.trade_company_var = tk.StringVar()
        self.trade_company_select = ttk.Combobox(sf, textvariable=self.trade_company_var, values=[])
        self.trade_company_select.grid(row=0, column=1, padx=8, pady=2, sticky="ew")
        self.trade_company_select.bind("<<ComboboxSelected>>", lambda _: self._update_trade_options())

        self._label(sf, "Seller").grid(row=1, column=0, sticky="w", pady=2)
        self.seller_var = tk.StringVar()
        self.seller_select = ttk.Combobox(sf, textvariable=self.seller_var, values=[])
        self.seller_select.grid(row=1, column=1, padx=8, pady=2, sticky="ew")

        self._label(sf, "Buyer").grid(row=2, column=0, sticky="w", pady=2)
        self.buyer_var = tk.StringVar()
        self.buyer_select = ttk.Combobox(sf, textvariable=self.buyer_var, values=[])
        self.buyer_select.grid(row=2, column=1, padx=8, pady=2, sticky="ew")

        self._label(sf, "Share (%)").grid(row=3, column=0, sticky="w", pady=2)
        self.share_entry = self._entry(sf, default="10")
        self.share_entry.grid(row=3, column=1, padx=8, pady=2, sticky="ew")
        self.share_entry.bind("<KeyRelease>", lambda _: self._update_share_price())
        self._bind_enter(self.share_entry, self._handle_share_purchase)

        self.price_label = tk.Label(sf, text="Price: \u2014", bg=COLORS["bg_secondary"],
                                    fg=COLORS["accent_gold"], font=FONTS["value"])
        self.price_label.grid(row=4, column=0, columnspan=2, pady=(6, 2), sticky="w")

        StyledButton(sf, "Complete share deal", self._handle_share_purchase, style="primary").grid(
            row=5, column=0, columnspan=2, pady=(4, 0), sticky="ew")

        help_text = "Valuation uses cash flow, substance, debt and sector multipliers.\nBuyer pays proportional to valuation directly to the seller."
        tk.Label(sf, text=help_text, bg=COLORS["bg_secondary"], fg=COLORS["text_muted"],
                 font=FONTS["helper"], wraplength=320, justify="left").grid(
            row=6, column=0, columnspan=2, pady=(6, 0), sticky="w")

        # -- Money transfer --
        money_card = self._card(col)
        money_card.pack(fill=tk.X, pady=(0, 6))
        tk.Label(money_card, text="Transfer Money", font=FONTS["section_label"],
                 bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).pack(anchor="w")
        mf = tk.Frame(money_card, bg=COLORS["bg_secondary"])
        mf.pack(fill=tk.X, pady=(4, 0))
        mf.columnconfigure(1, weight=1)
        self._label(mf, "From").grid(row=0, column=0, sticky="w", pady=2)
        self.transfer_from = ttk.Combobox(mf, values=[])
        self.transfer_from.grid(row=0, column=1, padx=8, pady=2, sticky="ew")
        self._label(mf, "To").grid(row=1, column=0, sticky="w", pady=2)
        self.transfer_to = ttk.Combobox(mf, values=[])
        self.transfer_to.grid(row=1, column=1, padx=8, pady=2, sticky="ew")
        self._label(mf, "Amount").grid(row=2, column=0, sticky="w", pady=2)
        self.transfer_amount = self._entry(mf, default="100")
        self.transfer_amount.grid(row=2, column=1, padx=8, pady=2, sticky="ew")
        StyledButton(mf, "Transfer", self._handle_money_transfer, style="secondary").grid(
            row=0, column=2, rowspan=3, padx=(8, 0))
        self._bind_enter(self.transfer_amount, self._handle_money_transfer)

        # -- Asset trade --
        asset_card = self._card(col)
        asset_card.pack(fill=tk.X, pady=(0, 6))
        tk.Label(asset_card, text="Asset Trade", font=FONTS["section_label"],
                 bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).pack(anchor="w")
        atf = tk.Frame(asset_card, bg=COLORS["bg_secondary"])
        atf.pack(fill=tk.X, pady=(4, 0))
        atf.columnconfigure(1, weight=1)
        self._label(atf, "Seller").grid(row=0, column=0, sticky="w", pady=2)
        self.asset_seller_var = tk.StringVar()
        self.asset_seller_select = ttk.Combobox(atf, textvariable=self.asset_seller_var, values=[])
        self.asset_seller_select.grid(row=0, column=1, padx=8, pady=2, sticky="ew")
        self.asset_seller_select.bind("<<ComboboxSelected>>", lambda _: self._populate_assets_for_seller())
        self._label(atf, "Asset").grid(row=1, column=0, sticky="w", pady=2)
        self.asset_select = ttk.Combobox(atf, values=[])
        self.asset_select.grid(row=1, column=1, padx=8, pady=2, sticky="ew")
        self._label(atf, "Buyer").grid(row=2, column=0, sticky="w", pady=2)
        self.asset_buyer_select = ttk.Combobox(atf, values=[])
        self.asset_buyer_select.grid(row=2, column=1, padx=8, pady=2, sticky="ew")
        self._label(atf, "Price").grid(row=3, column=0, sticky="w", pady=2)
        self.asset_price_entry = self._entry(atf, default="0")
        self.asset_price_entry.grid(row=3, column=1, padx=8, pady=2, sticky="ew")
        StyledButton(atf, "Complete asset deal", self._handle_asset_sale, style="secondary").grid(
            row=0, column=2, rowspan=4, padx=(8, 0))
        self._bind_enter(self.asset_price_entry, self._handle_asset_sale)

        # -- Rent --
        rent_card = self._card(col)
        rent_card.pack(fill=tk.X)
        tk.Label(rent_card, text="Pay Rent", font=FONTS["section_label"],
                 bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).pack(anchor="w")
        rf = tk.Frame(rent_card, bg=COLORS["bg_secondary"])
        rf.pack(fill=tk.X, pady=(4, 0))
        rf.columnconfigure(1, weight=1)
        self._label(rf, "Asset").grid(row=0, column=0, sticky="w", pady=2)
        self.rent_asset_select = ttk.Combobox(rf, values=[])
        self.rent_asset_select.grid(row=0, column=1, padx=8, pady=2, sticky="ew")
        self.rent_asset_select.bind("<<ComboboxSelected>>", lambda _: self._update_rent_owner())
        self._label(rf, "Tenant").grid(row=1, column=0, sticky="w", pady=2)
        self.rent_payer_select = ttk.Combobox(rf, values=[])
        self.rent_payer_select.grid(row=1, column=1, padx=8, pady=2, sticky="ew")
        self._label(rf, "Owner").grid(row=2, column=0, sticky="w", pady=2)
        self.rent_owner_label = tk.Label(rf, text="\u2014", bg=COLORS["bg_secondary"],
                                         fg=COLORS["accent_blue"], font=FONTS["value"])
        self.rent_owner_label.grid(row=2, column=1, sticky="w", padx=8)
        self._label(rf, "Amount").grid(row=3, column=0, sticky="w", pady=2)
        self.rent_amount_entry = self._entry(rf, default="0")
        self.rent_amount_entry.grid(row=3, column=1, padx=8, pady=2, sticky="ew")
        StyledButton(rf, "Pay rent", self._handle_pay_rent, style="secondary").grid(
            row=0, column=2, rowspan=4, padx=(8, 0))
        self._bind_enter(self.rent_amount_entry, self._handle_pay_rent)

    # ------------------------------------------------------------------
    # Dice & Chart panel (right)
    # ------------------------------------------------------------------
    def _build_dice_panel(self, parent: tk.Widget) -> None:
        col = tk.Frame(parent, bg=COLORS["bg_primary"])
        col.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        tk.Label(col, text="Dice & Years", font=FONTS["panel_title"],
                 bg=COLORS["bg_primary"], fg=COLORS["text_primary"]).pack(anchor="w", pady=(0, 6))

        # -- Dice card --
        dice_card = self._card(col)
        dice_card.pack(fill=tk.X, pady=(0, 6))

        dice_row = tk.Frame(dice_card, bg=COLORS["bg_secondary"])
        dice_row.pack(pady=(4, 8))
        self.die1 = DiceFace(dice_row)
        self.die1.grid(row=0, column=0, padx=10)
        self.die2 = DiceFace(dice_row)
        self.die2.grid(row=0, column=1, padx=10)

        self.last_roll_label = tk.Label(dice_card, text="Last roll: \u2014",
                                        bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"],
                                        font=FONTS["body"])
        self.last_roll_label.pack()

        StyledButton(dice_card, "Roll dice", self._start_dice_roll, style="primary").pack(
            fill=tk.X, pady=(8, 4))

        tk.Label(dice_card, text="Each roll counts as a year and applies\nannual cash flow to the active company.",
                 bg=COLORS["bg_secondary"], fg=COLORS["text_muted"], font=FONTS["helper"],
                 justify="left").pack(anchor="w", pady=(4, 0))

        # -- Valuation history chart --
        chart_card = self._card(col)
        chart_card.pack(fill=tk.BOTH, expand=True)
        tk.Label(chart_card, text="Valuation History", font=FONTS["section_label"],
                 bg=COLORS["bg_secondary"], fg=COLORS["text_primary"]).pack(anchor="w")
        self.history_canvas = tk.Canvas(
            chart_card, bg=COLORS["bg_tertiary"],
            highlightthickness=1, highlightbackground=COLORS["border_subtle"],
        )
        self.history_canvas.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------
    def _card(self, parent: tk.Widget) -> tk.Frame:
        """Create a card-style frame."""
        f = tk.Frame(
            parent, bg=COLORS["bg_secondary"],
            highlightbackground=COLORS["border_subtle"],
            highlightthickness=1,
            padx=14, pady=10,
        )
        return f

    def _label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=COLORS["bg_secondary"],
                        fg=COLORS["text_secondary"], font=FONTS["body"])

    def _entry(self, parent: tk.Widget, default: str = "") -> ttk.Entry:
        e = ttk.Entry(parent)
        if default:
            e.insert(0, default)
        return e

    def _labeled_entry(self, parent: tk.Widget, text: str, row: int, default: str = "") -> ttk.Entry:
        self._label(parent, text).grid(row=row, column=0, sticky="w", pady=2)
        entry = self._entry(parent, default)
        entry.grid(row=row, column=1, padx=8, pady=2, sticky="ew")
        return entry

    def _bind_enter(self, widget: tk.Widget, command) -> None:
        widget.bind("<Return>", lambda _event: command())

    def _save_state(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.state))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def _handle_undo(self) -> None:
        if not self.undo_stack:
            return
        self.state = self.undo_stack.pop()
        self.selected_company = None
        self._refresh_company_table()
        self._update_trade_options()
        self._update_company_summary()
        self._update_turn_display()

    # ------------------------------------------------------------------
    # Tree hover effect
    # ------------------------------------------------------------------
    def _on_tree_motion(self, event):
        item = self.company_tree.identify_row(event.y)
        for child in self.company_tree.get_children():
            idx = list(self.company_tree.get_children()).index(child)
            self.company_tree.item(child, tags=("even" if idx % 2 == 0 else "odd",))
        if item:
            self.company_tree.item(item, tags=("hover",))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _handle_balance_change(self) -> None:
        if not self.selected_company:
            self.toast.show("Select a company first", "error")
            return
        try:
            amount = float(self.balance_change.get())
        except ValueError:
            self.toast.show("Enter a numeric amount", "error")
            return
        self.selected_company.adjust_balance(amount)
        self._refresh_company_table()
        self._update_company_summary()

    def _handle_create_company(self) -> None:
        name = self.new_company_name.get().strip()
        balance_text = self.player_balance.get().strip()
        if not name:
            self.toast.show("Company name is required", "error")
            return
        try:
            balance = float(balance_text)
        except ValueError:
            self.toast.show("Starting balance must be a number", "error")
            return
        try:
            self._save_state()
            company = self.state.add_actor(name, balance)
        except ValueError as exc:
            self.toast.show(str(exc), "error")
            return

        self.selected_company = company
        self.trade_company_var.set(company.name)
        self._refresh_company_table()
        self.company_tree.selection_set(company.name)
        self._update_trade_options()
        self._update_company_summary()
        self._update_share_price()

    def _refresh_company_table(self) -> None:
        for item in self.company_tree.get_children():
            self.company_tree.delete(item)
        for idx, company in enumerate(self.state.actors.values()):
            owner = max(company.ownership_shares.items(), key=lambda item: item[1])[0]
            main_sector = self._dominant_sector(company)
            tag = "even" if idx % 2 == 0 else "odd"
            self.company_tree.insert(
                "", tk.END, iid=company.name,
                values=(
                    owner,
                    f"{company.valuation():.0f} kr",
                    main_sector,
                    f"{company.cash_flow_per_year():.0f}",
                    f"{company.debt:.0f}",
                ),
                tags=(tag,),
            )
        self.trade_company_select["values"] = list(self.state.actors.keys())
        self._update_trade_options()
        self.state.record_all_valuations()
        self._update_turn_display()
        self._draw_valuation_history()

    def _on_company_select(self, _event: tk.Event) -> None:
        selection = self.company_tree.selection()
        if not selection:
            return
        company_name = selection[0]
        self.selected_company = self.state.get_actor(company_name)
        self.trade_company_var.set(company_name)
        self._update_trade_options()
        self._update_company_summary()
        self._update_share_price()

    def _handle_add_asset(self) -> None:
        if not self.selected_company:
            self.toast.show("Select a company", "error")
            return
        name = self.asset_name.get().strip()
        if not name:
            self.toast.show("Asset name is required", "error")
            return
        try:
            value = float(self.asset_value.get())
            cashflow = float(self.asset_cashflow.get())
        except ValueError:
            self.toast.show("Enter numeric values for asset", "error")
            return
        sector = self.asset_sector.get() or list(SECTOR_MULTIPLIERS)[0]
        self._save_state()
        self.selected_company.add_asset(name=name, value=value, sector=sector, cash_flow_per_year=cashflow)
        self._update_company_summary()
        self._refresh_company_table()
        self._update_share_price()

    def _update_company_summary(self) -> None:
        if not self.selected_company:
            return
        self.company_summary.config(state="normal")
        self.company_summary.delete("1.0", tk.END)
        self.company_summary.insert(tk.END, self.selected_company.summary())
        self.company_summary.config(state="disabled")

    def _update_trade_options(self) -> None:
        actor_names = list(self.state.actors.keys())
        self.buyer_select["values"] = actor_names
        self.transfer_from["values"] = actor_names
        self.transfer_to["values"] = actor_names
        self.asset_buyer_select["values"] = actor_names
        self.asset_seller_select["values"] = actor_names
        if self.selected_company:
            owners = list(self.selected_company.ownership_shares.keys())
        else:
            owners = actor_names
        self.seller_select["values"] = owners
        self.rent_payer_select["values"] = actor_names
        self._populate_assets_for_seller()
        self._update_rent_assets()
        self._update_share_price()

    def _dominant_sector(self, company: Company) -> str:
        if not company.assets:
            return "\u2014"
        counts: dict[str, int] = {}
        for asset in company.assets:
            counts[asset.sector] = counts.get(asset.sector, 0) + 1
        return max(counts.items(), key=lambda item: item[1])[0]

    def _update_turn_display(self) -> None:
        if not self.state.order:
            self.turn_label.config(text="Next: \u2014")
            return
        nxt = self.state.order[self.state.current_index]
        self.turn_label.config(text=f"Next: {nxt}")
        self.year_label.config(text=f"Year {self.year_counter}")

    def _update_rent_assets(self) -> None:
        assets = self._all_assets()
        self.rent_asset_select["values"] = assets
        if assets:
            self.rent_asset_select.current(0)
            self._update_rent_owner()
        else:
            self.rent_owner_label.config(text="\u2014")

    def _all_assets(self) -> list[str]:
        names: list[str] = []
        for actor in self.state.actors.values():
            for asset in actor.assets:
                names.append(asset.name)
        return names

    def _handle_share_purchase(self) -> None:
        company = self._get_trade_company()
        if not company:
            return
        share = self._get_trade_percentage()
        if share is None:
            return
        buyer_name = self.buyer_var.get()
        seller_name = self.seller_var.get()
        if not buyer_name or not seller_name:
            self.toast.show("Select both buyer and seller", "error")
            return
        buyer = self.state.get_actor(buyer_name)
        seller = self.state.get_actor(seller_name)
        try:
            self._save_state()
            price = company.buy_in_as_owner(buyer, seller, share)
        except ValueError as exc:
            self.toast.show(str(exc), "error")
            return

        self.toast.show(f"Share deal completed for {price:.0f} kr", "success")
        self._refresh_company_table()
        self._update_company_summary()
        self._update_trade_options()
        self._update_share_price()

    def _handle_money_transfer(self) -> None:
        from_name = self.transfer_from.get()
        to_name = self.transfer_to.get()
        if not from_name or not to_name or from_name == to_name:
            self.toast.show("Choose different sender and receiver", "error")
            return
        try:
            amount = float(self.transfer_amount.get())
        except ValueError:
            self.toast.show("Amount must be numeric", "error")
            return
        sender = self.state.get_actor(from_name)
        receiver = self.state.get_actor(to_name)
        try:
            self._save_state()
            sender.transfer_money(receiver, amount)
        except ValueError as exc:
            self.toast.show(str(exc), "error")
            return
        self._refresh_company_table()
        self._update_company_summary()

    def _populate_assets_for_seller(self) -> None:
        seller_name = self.asset_seller_var.get()
        if not seller_name:
            self.asset_select["values"] = []
            return
        seller = self.state.get_actor(seller_name)
        names = [a.name for a in seller.assets]
        self.asset_select["values"] = names
        if names:
            self.asset_select.current(0)
            self.asset_price_entry.delete(0, tk.END)
            self.asset_price_entry.insert(0, f"{seller.assets[0].value:.0f}")
        self._update_rent_assets()

    def _handle_asset_sale(self) -> None:
        seller_name = self.asset_seller_var.get()
        buyer_name = self.asset_buyer_select.get()
        asset_name = self.asset_select.get()
        if not seller_name or not buyer_name or not asset_name:
            self.toast.show("Select seller, buyer and asset", "error")
            return
        if seller_name == buyer_name:
            self.toast.show("Seller and buyer must differ", "error")
            return
        seller = self.state.get_actor(seller_name)
        buyer = self.state.get_actor(buyer_name)
        asset = next((a for a in seller.assets if a.name == asset_name), None)
        if not asset:
            self.toast.show("Asset not found for seller", "error")
            return
        try:
            price = float(self.asset_price_entry.get()) if self.asset_price_entry.get() else asset.value
        except ValueError:
            self.toast.show("Price must be numeric", "error")
            return
        try:
            self._save_state()
            seller.transfer_asset(buyer, asset, price)
        except ValueError as exc:
            self.toast.show(str(exc), "error")
            return
        self._refresh_company_table()
        self._update_company_summary()
        self._update_trade_options()
        self._update_turn_display()

    def _update_rent_owner(self) -> None:
        asset_name = self.rent_asset_select.get()
        data = self.state.find_asset(asset_name) if asset_name else None
        if data:
            owner, asset = data
            self.rent_owner_label.config(text=owner.name)
            self.rent_amount_entry.delete(0, tk.END)
            self.rent_amount_entry.insert(0, f"{asset.cash_flow_per_year:.0f}")
        else:
            self.rent_owner_label.config(text="\u2014")

    def _handle_pay_rent(self) -> None:
        asset_name = self.rent_asset_select.get()
        tenant_name = self.rent_payer_select.get()
        if not asset_name or not tenant_name:
            self.toast.show("Select asset and tenant", "error")
            return
        data = self.state.find_asset(asset_name)
        if not data:
            self.toast.show("Asset not found", "error")
            return
        owner, _ = data
        if owner.name == tenant_name:
            self.toast.show("Tenant cannot pay themselves", "error")
            return
        try:
            amount = float(self.rent_amount_entry.get())
        except ValueError:
            self.toast.show("Amount must be numeric", "error")
            return
        tenant = self.state.get_actor(tenant_name)
        try:
            self._save_state()
            tenant.transfer_money(owner, amount)
        except ValueError as exc:
            self.toast.show(str(exc), "error")
            return
        self.toast.show(f"{tenant.name} paid {amount:.0f} kr to {owner.name}", "success")
        self._refresh_company_table()
        self._update_company_summary()
        self._update_turn_display()

    # ------------------------------------------------------------------
    # Valuation chart
    # ------------------------------------------------------------------
    def _draw_valuation_history(self) -> None:
        canvas = getattr(self, "history_canvas", None)
        if not canvas:
            return
        canvas.delete("all")
        companies = list(self.state.actors.values())
        if not companies:
            return
        for company in companies:
            if not company.valuation_history:
                company.record_valuation()
        max_len = max(len(c.valuation_history) for c in companies)
        all_vals = [v for c in companies for v in c.valuation_history if c.valuation_history]
        max_val = max(all_vals) if all_vals else 1
        if max_val == 0:
            max_val = 1

        canvas.update_idletasks()
        w = canvas.winfo_width() or 400
        h = canvas.winfo_height() or 200
        margin = {"left": 55, "right": 16, "top": 12, "bottom": 28}
        plot_w = w - margin["left"] - margin["right"]
        plot_h = h - margin["top"] - margin["bottom"]

        # Grid lines
        num_grid = 4
        for i in range(num_grid + 1):
            y = margin["top"] + (plot_h / num_grid) * i
            canvas.create_line(
                margin["left"], y, w - margin["right"], y,
                fill=COLORS["border_subtle"], dash=(3, 3))
            val_label = max_val - (max_val / num_grid) * i
            canvas.create_text(
                margin["left"] - 6, y, text=f"{val_label:.0f}",
                anchor="e", fill=COLORS["text_muted"], font=FONTS["helper"])

        # X-axis labels
        if max_len > 1:
            step = max(1, max_len // 6)
            for i in range(0, max_len, step):
                x = margin["left"] + (i / (max_len - 1)) * plot_w
                canvas.create_text(
                    x, h - 6, text=str(i), anchor="s",
                    fill=COLORS["text_muted"], font=FONTS["helper"])

        # Data lines
        for idx, company in enumerate(companies):
            history = company.valuation_history
            if len(history) < 2:
                continue
            color = CHART_COLORS[idx % len(CHART_COLORS)]
            points = []
            for i, val in enumerate(history):
                x = margin["left"] + (i / (max_len - 1 if max_len > 1 else 1)) * plot_w
                y = margin["top"] + plot_h - (val / max_val) * plot_h
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=2.5, smooth=True)

        # Legend
        lx = margin["left"] + 8
        ly = margin["top"] + 6
        for idx, company in enumerate(companies):
            color = CHART_COLORS[idx % len(CHART_COLORS)]
            canvas.create_rectangle(lx, ly + idx * 16, lx + 10, ly + 10 + idx * 16, fill=color, outline="")
            canvas.create_text(lx + 14, ly + 5 + idx * 16, text=company.name,
                               anchor="w", fill=COLORS["text_primary"], font=FONTS["helper"])

    # ------------------------------------------------------------------
    # Dice
    # ------------------------------------------------------------------
    def _start_dice_roll(self) -> None:
        if self.is_rolling:
            return
        if not self.state.actors:
            self.toast.show("Add companies before rolling", "error")
            return
        self.active_company = self.state.next_actor()
        if self.state.current_index == 0:
            self.year_counter += 1
        self.is_rolling = True
        self._animate_dice(8)

    def _animate_dice(self, steps: int) -> None:
        if steps > 0:
            v1, v2 = random.randint(1, 6), random.randint(1, 6)
            self.die1.flash_gold(v1)
            self.die2.flash_gold(v2)
            self.root.after(90, lambda: self._animate_dice(steps - 1))
        else:
            final1 = random.randint(1, 6)
            final2 = random.randint(1, 6)
            self.die1.set_value(final1)
            self.die2.set_value(final2)
            total = final1 + final2
            self.last_roll_label.config(text=f"Last roll: {total}")
            if self.active_company:
                self._apply_turn_effects(self.active_company)
            self.is_rolling = False

    def _apply_turn_effects(self, company: Company) -> None:
        cash_flow = company.cash_flow_per_year()
        self._save_state()
        company.adjust_balance(cash_flow)
        self._refresh_company_table()
        self._update_company_summary()
        self._update_turn_display()
        self.toast.show(
            f"{company.name} completed a year. Cash flow: {cash_flow:.0f} kr",
            "success",
        )

    # ------------------------------------------------------------------
    # Trade helpers
    # ------------------------------------------------------------------
    def _get_trade_company(self) -> Company | None:
        company_name = self.trade_company_var.get()
        if not company_name:
            self.toast.show("Select a company", "error")
            return None
        company = self.state.get_actor(company_name)
        self.selected_company = company
        return company

    def _get_trade_percentage(self) -> float | None:
        try:
            share = float(self.share_entry.get())
        except ValueError:
            self.toast.show("Share must be numeric", "error")
            return None
        if share <= 0 or share > 100:
            self.toast.show("Share must be between 0 and 100", "error")
            return None
        return share

    def _update_share_price(self) -> None:
        company_name = self.trade_company_var.get()
        if not company_name or company_name not in self.state.actors:
            self.price_label.config(text="Price: \u2014")
            return
        company = self.state.get_actor(company_name)
        try:
            share = float(self.share_entry.get())
        except (ValueError, AttributeError):
            self.price_label.config(text="Price: \u2014")
            return
        if share <= 0 or share > 100:
            self.price_label.config(text="Price: \u2014")
            return
        price = company.valuation() * (share / 100)
        self.price_label.config(text=f"Price: {price:.0f} kr")

    def run(self) -> None:
        self.root.mainloop()


def start_gui() -> None:
    MonopolyPlusGUI().run()


if __name__ == "__main__":
    start_gui()
