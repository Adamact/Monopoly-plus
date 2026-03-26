"""Color palette, font specs, and ttk style configuration for Monopoly Plus."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

COLORS = {
    "bg_primary": "#1a1d23",
    "bg_secondary": "#23272f",
    "bg_tertiary": "#2c313a",
    "bg_hover": "#343a46",
    "border_subtle": "#3a3f4b",
    "border_focus": "#5b9bd5",
    "text_primary": "#e8eaed",
    "text_secondary": "#9aa0a6",
    "text_muted": "#6b7280",
    "accent_green": "#00c853",
    "accent_green_hover": "#00e676",
    "accent_gold": "#ffc107",
    "accent_gold_hover": "#ffca28",
    "accent_blue": "#42a5f5",
    "accent_red": "#ef5350",
    "accent_red_hover": "#e57373",
    "success_bg": "#1b3a26",
    "error_bg": "#3a1b1b",
    "info_bg": "#1a2a3a",
    "row_even": "#23272f",
    "row_odd": "#282d36",
    "row_selected": "#1a3a5c",
}

_FONT_FAMILY = ("Segoe UI Variable Text", "Segoe UI", "Arial")
_FONT_DISPLAY = ("Segoe UI Variable Display Semib", "Segoe UI Semibold", "Arial")
_FONT_MONO = ("Cascadia Code", "Consolas", "Courier New")

FONTS = {
    "app_title": (*_FONT_DISPLAY, 18),
    "panel_title": (*_FONT_DISPLAY, 13),
    "section_label": (*_FONT_FAMILY, 11, "bold"),
    "body": (*_FONT_FAMILY, 10),
    "value": (*_FONT_FAMILY, 11, "bold"),
    "helper": (*_FONT_FAMILY, 9),
    "dice": (*_FONT_DISPLAY, 36),
    "mono": (*_FONT_MONO, 10),
}

CHART_COLORS = ["#42a5f5", "#ffc107", "#00c853", "#ef5350", "#ab47bc", "#ff7043"]


def configure_styles(root: tk.Tk) -> None:
    """Apply the dark theme to all ttk widgets."""
    style = ttk.Style(root)
    style.theme_use("clam")

    # Combobox dropdown (must be set before widget creation)
    root.option_add("*TCombobox*Listbox.background", COLORS["bg_tertiary"])
    root.option_add("*TCombobox*Listbox.foreground", COLORS["text_primary"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["row_selected"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["accent_blue"])
    root.option_add("*TCombobox*Listbox.font", FONTS["body"])

    # Treeview
    style.configure(
        "Treeview",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_primary"],
        fieldbackground=COLORS["bg_secondary"],
        borderwidth=0,
        font=FONTS["body"],
        rowheight=30,
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["bg_tertiary"],
        foreground=COLORS["text_secondary"],
        font=FONTS["section_label"],
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["row_selected"])],
        foreground=[("selected", COLORS["accent_blue"])],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["bg_hover"])],
    )

    # Combobox
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["bg_tertiary"],
        background=COLORS["bg_hover"],
        foreground=COLORS["text_primary"],
        arrowcolor=COLORS["text_secondary"],
        borderwidth=1,
        relief="flat",
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["bg_tertiary"]), ("focus", COLORS["bg_hover"])],
        foreground=[("readonly", COLORS["text_primary"])],
        bordercolor=[("focus", COLORS["border_focus"]), ("!focus", COLORS["border_subtle"])],
    )

    # Entry
    style.configure(
        "TEntry",
        fieldbackground=COLORS["bg_tertiary"],
        foreground=COLORS["text_primary"],
        borderwidth=1,
        relief="flat",
        insertcolor=COLORS["text_primary"],
        padding=4,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", COLORS["border_focus"]), ("!focus", COLORS["border_subtle"])],
        fieldbackground=[("focus", COLORS["bg_hover"])],
    )

    # Scrollbar
    style.configure(
        "TScrollbar",
        background=COLORS["bg_tertiary"],
        troughcolor=COLORS["bg_primary"],
        borderwidth=0,
        arrowcolor=COLORS["text_secondary"],
    )

    # Frame
    style.configure("TFrame", background=COLORS["bg_primary"])
    style.configure("Card.TFrame", background=COLORS["bg_secondary"])

    # Label
    style.configure(
        "TLabel",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_primary"],
        font=FONTS["body"],
    )
    style.configure("Secondary.TLabel", foreground=COLORS["text_secondary"])
    style.configure("Muted.TLabel", foreground=COLORS["text_muted"], font=FONTS["helper"])
    style.configure("Title.TLabel", font=FONTS["panel_title"])
    style.configure("AppTitle.TLabel", font=FONTS["app_title"], background=COLORS["bg_secondary"])
    style.configure("Value.TLabel", font=FONTS["value"])
    style.configure(
        "Gold.TLabel",
        font=FONTS["value"],
        foreground=COLORS["accent_gold"],
    )
    style.configure(
        "Turn.TLabel",
        font=FONTS["value"],
        foreground=COLORS["accent_green"],
        background=COLORS["bg_secondary"],
    )
