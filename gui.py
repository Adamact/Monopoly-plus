"""Tkinter GUI for Monopoly Plus.

Players are companies; each full turn across players is considered a year.
Financial metrics are derived automatically from assets and transactions.
"""
from __future__ import annotations

import copy
import random
import tkinter as tk
from tkinter import messagebox, ttk

from game_models import Company, GameState, SECTOR_MULTIPLIERS


class MonopolyPlusGUI:
    def __init__(self) -> None:
        self.state = GameState()
        self.root = tk.Tk()
        self.root.title("Monopoly Plus - Companies")
        self.root.geometry("1300x760")
        self.root.configure(background="#f5f5f5")

        self.selected_company: Company | None = None
        self.year_counter: int = 0
        self.active_company: Company | None = None
        self.is_rolling: bool = False
        self.undo_stack: list[GameState] = []

        self._build_layout()
        self._refresh_company_table()
        self._update_turn_display()
        self.root.bind("<Control-z>", lambda event: self._handle_undo())

    # --- Layout ---
    def _build_layout(self) -> None:
        header = tk.Label(
            self.root,
            text="Digital Monopoly helper: manage companies, assets and ownership",
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
        frame = tk.LabelFrame(parent, text="Companies", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        add_frame = tk.Frame(frame, bg="#ffffff")
        add_frame.pack(fill=tk.X, pady=5)
        tk.Label(add_frame, text="Company/Player", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.new_company_name = tk.Entry(add_frame)
        self.new_company_name.grid(row=0, column=1, padx=5)
        tk.Label(add_frame, text="Starting balance", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.player_balance = tk.Entry(add_frame)
        self.player_balance.insert(0, "1000")
        self.player_balance.grid(row=1, column=1, padx=5)
        tk.Button(add_frame, text="Add company", command=self._handle_create_company).grid(
            row=0, column=2, rowspan=2, padx=10
        )
        self._bind_enter(self.new_company_name, self._handle_create_company)
        self._bind_enter(self.player_balance, self._handle_create_company)

        columns = ("Top owner", "Valuation", "Main sector", "Cash flow/year", "Debt")
        self.company_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.company_tree.heading(col, text=col)
        self.company_tree.column("Top owner", width=130)
        self.company_tree.column("Valuation", width=120)
        self.company_tree.column("Main sector", width=120)
        self.company_tree.column("Cash flow/year", width=120)
        self.company_tree.column("Debt", width=80)
        self.company_tree.pack(fill=tk.BOTH, expand=True)
        self.company_tree.bind("<<TreeviewSelect>>", self._on_company_select)

        asset_frame = tk.LabelFrame(frame, text="Assets", bg="#ffffff")
        asset_frame.pack(fill=tk.X, pady=5)
        self.asset_name = self._labeled_entry(asset_frame, "Name", 0)
        self.asset_value = self._labeled_entry(asset_frame, "Value", 1)
        tk.Label(asset_frame, text="Sector", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.asset_sector = ttk.Combobox(asset_frame, values=list(SECTOR_MULTIPLIERS), state="readonly")
        self.asset_sector.current(0)
        self.asset_sector.grid(row=2, column=1, padx=5, pady=2)
        self.asset_cashflow = self._labeled_entry(asset_frame, "Cash flow/year", 3, default="0")
        tk.Button(asset_frame, text="Add asset", command=self._handle_add_asset).grid(
            row=0, column=2, rowspan=4, padx=10
        )
        self._bind_enter(self.asset_name, self._handle_add_asset)
        self._bind_enter(self.asset_value, self._handle_add_asset)
        self._bind_enter(self.asset_cashflow, self._handle_add_asset)

        self.company_summary = tk.Text(frame, height=12, wrap=tk.WORD)
        self.company_summary.pack(fill=tk.BOTH, expand=True, pady=5)
        self.company_summary.config(state="disabled")

        balance_frame = tk.Frame(frame, bg="#ffffff")
        balance_frame.pack(fill=tk.X, pady=5)
        tk.Label(balance_frame, text="Balance adjustment", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.balance_change = tk.Entry(balance_frame)
        self.balance_change.insert(0, "0")
        self.balance_change.grid(row=0, column=1, padx=5)
        tk.Button(balance_frame, text="Apply", command=self._handle_balance_change).grid(row=0, column=2, padx=5)
        self._bind_enter(self.balance_change, self._handle_balance_change)

    def _build_trade_panel(self, parent: tk.Widget) -> None:
        frame = tk.LabelFrame(parent, text="Transactions", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Company", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.trade_company_var = tk.StringVar()
        self.trade_company_select = ttk.Combobox(frame, textvariable=self.trade_company_var, values=[])
        self.trade_company_select.grid(row=0, column=1, padx=5)
        self.trade_company_select.bind("<<ComboboxSelected>>", lambda _: self._update_trade_options())

        tk.Label(frame, text="Seller", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.seller_var = tk.StringVar()
        self.seller_select = ttk.Combobox(frame, textvariable=self.seller_var, values=[])
        self.seller_select.grid(row=1, column=1, padx=5)

        tk.Label(frame, text="Buyer", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.buyer_var = tk.StringVar()
        self.buyer_select = ttk.Combobox(frame, textvariable=self.buyer_var, values=[])
        self.buyer_select.grid(row=2, column=1, padx=5)

        tk.Label(frame, text="Share (%)", bg="#ffffff").grid(row=3, column=0, sticky="w")
        self.share_entry = tk.Entry(frame)
        self.share_entry.insert(0, "10")
        self.share_entry.grid(row=3, column=1, padx=5)
        self.share_entry.bind("<KeyRelease>", lambda _event: self._update_share_price())
        self._bind_enter(self.share_entry, self._handle_share_purchase)

        self.price_label = tk.Label(frame, text="Price: -", bg="#ffffff", font=("Arial", 11, "bold"))
        self.price_label.grid(row=4, column=0, columnspan=2, pady=5)

        tk.Button(frame, text="Complete share deal", command=self._handle_share_purchase).grid(row=5, column=0, columnspan=2, pady=5)

        help_text = (
            "Valuation uses cash flow, substance, debt and sector multipliers.\n"
            "Buyer pays proportional to valuation directly to the seller."
        )
        tk.Label(frame, text=help_text, bg="#ffffff", wraplength=320, justify="left").grid(
            row=6, column=0, columnspan=2, pady=10
        )

        money_frame = tk.LabelFrame(frame, text="Transfer money", bg="#ffffff")
        money_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=8)
        tk.Label(money_frame, text="From", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.transfer_from = ttk.Combobox(money_frame, values=[])
        self.transfer_from.grid(row=0, column=1, padx=5)
        tk.Label(money_frame, text="To", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.transfer_to = ttk.Combobox(money_frame, values=[])
        self.transfer_to.grid(row=1, column=1, padx=5)
        tk.Label(money_frame, text="Amount", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.transfer_amount = tk.Entry(money_frame)
        self.transfer_amount.insert(0, "100")
        self.transfer_amount.grid(row=2, column=1, padx=5)
        tk.Button(money_frame, text="Transfer", command=self._handle_money_transfer).grid(
            row=0, column=2, rowspan=3, padx=10
        )
        self._bind_enter(self.transfer_amount, self._handle_money_transfer)

        asset_trade = tk.LabelFrame(frame, text="Asset trade", bg="#ffffff")
        asset_trade.grid(row=8, column=0, columnspan=2, sticky="ew", pady=8)
        tk.Label(asset_trade, text="Seller", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.asset_seller_var = tk.StringVar()
        self.asset_seller_select = ttk.Combobox(asset_trade, textvariable=self.asset_seller_var, values=[])
        self.asset_seller_select.grid(row=0, column=1, padx=5)
        self.asset_seller_select.bind("<<ComboboxSelected>>", lambda _: self._populate_assets_for_seller())

        tk.Label(asset_trade, text="Asset", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.asset_select = ttk.Combobox(asset_trade, values=[])
        self.asset_select.grid(row=1, column=1, padx=5)

        tk.Label(asset_trade, text="Buyer", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.asset_buyer_select = ttk.Combobox(asset_trade, values=[])
        self.asset_buyer_select.grid(row=2, column=1, padx=5)

        tk.Label(asset_trade, text="Price", bg="#ffffff").grid(row=3, column=0, sticky="w")
        self.asset_price_entry = tk.Entry(asset_trade)
        self.asset_price_entry.insert(0, "0")
        self.asset_price_entry.grid(row=3, column=1, padx=5)

        tk.Button(asset_trade, text="Complete asset deal", command=self._handle_asset_sale).grid(row=0, column=2, rowspan=4, padx=10)
        self._bind_enter(self.asset_price_entry, self._handle_asset_sale)

        rent_frame = tk.LabelFrame(frame, text="Pay rent", bg="#ffffff")
        rent_frame.grid(row=9, column=0, columnspan=2, sticky="ew", pady=8)
        tk.Label(rent_frame, text="Asset", bg="#ffffff").grid(row=0, column=0, sticky="w")
        self.rent_asset_select = ttk.Combobox(rent_frame, values=[])
        self.rent_asset_select.grid(row=0, column=1, padx=5)
        self.rent_asset_select.bind("<<ComboboxSelected>>", lambda _: self._update_rent_owner())
        tk.Label(rent_frame, text="Tenant", bg="#ffffff").grid(row=1, column=0, sticky="w")
        self.rent_payer_select = ttk.Combobox(rent_frame, values=[])
        self.rent_payer_select.grid(row=1, column=1, padx=5)
        tk.Label(rent_frame, text="Owner:", bg="#ffffff").grid(row=2, column=0, sticky="w")
        self.rent_owner_label = tk.Label(rent_frame, text="-", bg="#ffffff")
        self.rent_owner_label.grid(row=2, column=1, sticky="w")
        tk.Label(rent_frame, text="Amount", bg="#ffffff").grid(row=3, column=0, sticky="w")
        self.rent_amount_entry = tk.Entry(rent_frame)
        self.rent_amount_entry.insert(0, "0")
        self.rent_amount_entry.grid(row=3, column=1, padx=5)
        tk.Button(rent_frame, text="Pay rent", command=self._handle_pay_rent).grid(row=0, column=2, rowspan=4, padx=10)
        self._bind_enter(self.rent_amount_entry, self._handle_pay_rent)

    def _build_dice_panel(self, parent: tk.Widget) -> None:
        frame = tk.LabelFrame(parent, text="Dice & Years", padx=10, pady=10, bg="#ffffff")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.turn_label = tk.Label(frame, text="Next company: -", bg="#ffffff", font=("Arial", 11, "bold"))
        self.turn_label.pack(anchor="w")
        self.year_label = tk.Label(frame, text="Years completed: 0", bg="#ffffff")
        self.year_label.pack(anchor="w")

        dice_frame = tk.Frame(frame, bg="#ffffff")
        dice_frame.pack(pady=10)
        self.die1_label = tk.Label(dice_frame, text="🎲", font=("Arial", 32), bg="#ffffff")
        self.die1_label.grid(row=0, column=0, padx=10)
        self.die2_label = tk.Label(dice_frame, text="🎲", font=("Arial", 32), bg="#ffffff")
        self.die2_label.grid(row=0, column=1, padx=10)
        self.last_roll_label = tk.Label(frame, text="Last roll: -", bg="#ffffff")
        self.last_roll_label.pack()

        tk.Button(frame, text="Roll dice", command=self._start_dice_roll).pack(pady=5)
        tk.Label(frame, text="Each roll counts as a year and applies annual cash flow to the active company.", bg="#ffffff", wraplength=320).pack(pady=5)

        self.history_canvas = tk.Canvas(frame, width=520, height=240, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
        self.history_canvas.pack(fill=tk.BOTH, expand=True, pady=10)

    # --- Helpers ---
    def _labeled_entry(self, parent: tk.Widget, text: str, row: int, default: str = "") -> tk.Entry:
        tk.Label(parent, text=text, bg="#ffffff").grid(row=row, column=0, sticky="w")
        entry = tk.Entry(parent)
        entry.insert(0, default)
        entry.grid(row=row, column=1, padx=5, pady=2)
        return entry

    # --- Actions ---
    def _handle_balance_change(self) -> None:
        if not self.selected_company:
            messagebox.showwarning("Error", "Select a company first")
            return
        try:
            amount = float(self.balance_change.get())
        except ValueError:
            messagebox.showwarning("Error", "Enter a numeric amount")
            return
        self.selected_company.adjust_balance(amount)
        self._refresh_company_table()
        self._update_company_summary()

    def _handle_create_company(self) -> None:
        name = self.new_company_name.get().strip()
        balance_text = self.player_balance.get().strip()
        if not name:
            messagebox.showwarning("Error", "Company name is required")
            return
        try:
            balance = float(balance_text)
        except ValueError:
            messagebox.showwarning("Error", "Starting balance must be a number")
            return
        try:
            company = self.state.add_actor(name, balance)
        except ValueError as exc:
            messagebox.showwarning("Error", str(exc))
            return

        self.selected_company = company
        self.trade_company_var.set(company.name)
        self._refresh_company_table()
        self.company_tree.selection_set(company.name)
        self._update_trade_options()
        self._update_company_summary()
        self._update_share_price()
        self._update_share_price()
        self._update_share_price()

    def _refresh_company_table(self) -> None:
        for item in self.company_tree.get_children():
            self.company_tree.delete(item)
        for company in self.state.actors.values():
            owner = max(company.ownership_shares.items(), key=lambda item: item[1])[0]
            main_sector = self._dominant_sector(company)
            self.company_tree.insert(
                "",
                tk.END,
                iid=company.name,
                values=(
                    owner,
                    f"{company.valuation():.0f} kr",
                    main_sector,
                    f"{company.cash_flow_per_year():.0f}",
                    f"{company.debt:.0f}",
                ),
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
            messagebox.showwarning("Error", "Select a company")
            return
        name = self.asset_name.get().strip()
        if not name:
            messagebox.showwarning("Error", "Asset name is required")
            return
        try:
            value = float(self.asset_value.get())
            cashflow = float(self.asset_cashflow.get())
        except ValueError:
            messagebox.showwarning("Error", "Enter numeric values for asset")
            return
        sector = self.asset_sector.get() or list(SECTOR_MULTIPLIERS)[0]
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
            return "-"
        counts: Dict[str, int] = {}
        for asset in company.assets:
            counts[asset.sector] = counts.get(asset.sector, 0) + 1
        return max(counts.items(), key=lambda item: item[1])[0]

    def _update_turn_display(self) -> None:
        if not self.state.order:
            self.turn_label.config(text="Next company: -")
            return
        nxt = self.state.order[self.state.current_index]
        self.turn_label.config(text=f"Next company: {nxt}")
        self.year_label.config(text=f"Years completed: {self.year_counter}")

    def _update_rent_assets(self) -> None:
        assets = self._all_assets()
        self.rent_asset_select["values"] = assets
        if assets:
            self.rent_asset_select.current(0)
            self._update_rent_owner()
        else:
            self.rent_owner_label.config(text="-")

    def _all_assets(self) -> list[str]:
        names: list[str] = []
        for actor in self.state.actors.values():
            for asset in actor.assets:
                names.append(asset.name)
        return names

    def _handle_calculate_price(self) -> None:
        company = self._get_trade_company()
        if not company:
            return
        share = self._get_trade_percentage()
        if share is None:
            return
        price = company.valuation() * (share / 100)
        self.price_label.config(text=f"Price: {price:.0f} kr")

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
            messagebox.showwarning("Error", "Select both buyer and seller")
            return
        buyer = self.state.get_actor(buyer_name)
        seller = self.state.get_actor(seller_name)
        try:
            price = company.buy_in_as_owner(buyer, seller, share)
        except ValueError as exc:
            messagebox.showwarning("Error", str(exc))
            return

        messagebox.showinfo("Done", f"Share deal completed for {price:.0f} kr")
        self._refresh_company_table()
        self._update_company_summary()
        self._update_trade_options()
        self._update_share_price()

    def _handle_money_transfer(self) -> None:
        from_name = self.transfer_from.get()
        to_name = self.transfer_to.get()
        if not from_name or not to_name or from_name == to_name:
            messagebox.showwarning("Error", "Choose different sender and receiver")
            return
        try:
            amount = float(self.transfer_amount.get())
        except ValueError:
            messagebox.showwarning("Error", "Amount must be numeric")
            return
        sender = self.state.get_actor(from_name)
        receiver = self.state.get_actor(to_name)
        try:
            sender.transfer_money(receiver, amount)
        except ValueError as exc:
            messagebox.showwarning("Error", str(exc))
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
            messagebox.showwarning("Error", "Select seller, buyer and asset")
            return
        if seller_name == buyer_name:
            messagebox.showwarning("Error", "Seller and buyer must differ")
            return
        seller = self.state.get_actor(seller_name)
        buyer = self.state.get_actor(buyer_name)
        asset = next((a for a in seller.assets if a.name == asset_name), None)
        if not asset:
            messagebox.showwarning("Error", "Asset not found for seller")
            return
        try:
            price = float(self.asset_price_entry.get()) if self.asset_price_entry.get() else asset.value
        except ValueError:
            messagebox.showwarning("Error", "Price must be numeric")
            return
        try:
            seller.transfer_asset(buyer, asset, price)
        except ValueError as exc:
            messagebox.showwarning("Error", str(exc))
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
            self.rent_owner_label.config(text="-")

    def _handle_pay_rent(self) -> None:
        asset_name = self.rent_asset_select.get()
        tenant_name = self.rent_payer_select.get()
        if not asset_name or not tenant_name:
            messagebox.showwarning("Error", "Select asset and tenant")
            return
        data = self.state.find_asset(asset_name)
        if not data:
            messagebox.showwarning("Error", "Asset not found")
            return
        owner, _ = data
        if owner.name == tenant_name:
            messagebox.showwarning("Error", "Tenant cannot pay themselves")
            return
        try:
            amount = float(self.rent_amount_entry.get())
        except ValueError:
            messagebox.showwarning("Error", "Amount must be numeric")
            return
        tenant = self.state.get_actor(tenant_name)
        try:
            tenant.transfer_money(owner, amount)
        except ValueError as exc:
            messagebox.showwarning("Error", str(exc))
            return
        messagebox.showinfo("Rent paid", f"{tenant.name} paid {amount:.0f} kr to {owner.name}")
        self._refresh_company_table()
        self._update_company_summary()
        self._update_turn_display()

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
        max_val = max((max(c.valuation_history) for c in companies if c.valuation_history), default=1)
        width = int(canvas["width"])
        height = int(canvas["height"])
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
        for idx, company in enumerate(companies):
            history = company.valuation_history
            if len(history) < 2 or max_val == 0:
                continue
            color = colors[idx % len(colors)]
            for i in range(1, len(history)):
                x1 = (i - 1) / (max_len - 1 if max_len > 1 else 1) * (width - 40) + 20
                x2 = i / (max_len - 1 if max_len > 1 else 1) * (width - 40) + 20
                y1 = height - (history[i - 1] / max_val) * (height - 40) - 20
                y2 = height - (history[i] / max_val) * (height - 40) - 20
                canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
            canvas.create_text(60, 20 + 15 * idx, text=f"{company.name}", fill=color, anchor="w")

    def _start_dice_roll(self) -> None:
        if self.is_rolling:
            return
        if not self.state.actors:
            messagebox.showwarning("Error", "Add companies before rolling")
            return
        self.active_company = self.state.next_actor()
        if self.state.current_index == 0:
            self.year_counter += 1
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
            self.last_roll_label.config(text=f"Last roll: {total}")
            if self.active_company:
                self._apply_turn_effects(self.active_company)
            self.is_rolling = False

    def _apply_turn_effects(self, company: Company) -> None:
        cash_flow = company.cash_flow_per_year()
        company.adjust_balance(cash_flow)
        self._refresh_company_table()
        self._update_company_summary()
        self._update_turn_display()
        messagebox.showinfo(
            "Year complete",
            f"{company.name} completed a year. Applied cash flow: {cash_flow:.0f} kr",
        )

    def _get_trade_company(self) -> Company | None:
        company_name = self.trade_company_var.get()
        if not company_name:
            messagebox.showwarning("Error", "Select a company")
            return None
        company = self.state.get_actor(company_name)
        self.selected_company = company
        return company

    def _get_trade_percentage(self) -> float | None:
        try:
            share = float(self.share_entry.get())
        except ValueError:
            messagebox.showwarning("Error", "Share must be numeric")
            return None
        if share <= 0 or share > 100:
            messagebox.showwarning("Error", "Share must be between 0 and 100")
            return None
        return share

    def _update_share_price(self) -> None:
        company = self._get_trade_company()
        if not company:
            self.price_label.config(text="Price: -")
            return
        share = self._get_trade_percentage()
        if share is None:
            self.price_label.config(text="Price: -")
            return
        price = company.valuation() * (share / 100)
        self.price_label.config(text=f"Price: {price:.0f} kr")

    def run(self) -> None:
        self.root.mainloop()


def start_gui() -> None:
    MonopolyPlusGUI().run()


if __name__ == "__main__":
    start_gui()
