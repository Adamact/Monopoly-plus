"""Custom themed widgets for Monopoly Plus."""
from __future__ import annotations

import tkinter as tk
from theme import COLORS, FONTS


# ---------------------------------------------------------------------------
# StyledButton
# ---------------------------------------------------------------------------
BUTTON_STYLES = {
    "primary": {
        "bg": COLORS["accent_green"],
        "fg": "#1a1d23",
        "hover_bg": COLORS["accent_green_hover"],
        "active_bg": "#00b848",
    },
    "secondary": {
        "bg": COLORS["bg_tertiary"],
        "fg": COLORS["text_primary"],
        "hover_bg": COLORS["bg_hover"],
        "active_bg": COLORS["border_subtle"],
    },
    "danger": {
        "bg": COLORS["accent_red"],
        "fg": "#ffffff",
        "hover_bg": COLORS["accent_red_hover"],
        "active_bg": "#d32f2f",
    },
    "ghost": {
        "bg": COLORS["bg_secondary"],
        "fg": COLORS["text_secondary"],
        "hover_bg": COLORS["bg_tertiary"],
        "active_bg": COLORS["bg_hover"],
    },
}


class StyledButton(tk.Button):
    """Flat button with hover effect."""

    def __init__(self, parent, text: str, command=None, style: str = "secondary", **kwargs):
        colors = BUTTON_STYLES.get(style, BUTTON_STYLES["secondary"])
        self._colors = colors
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=colors["bg"],
            fg=colors["fg"],
            activebackground=colors["active_bg"],
            activeforeground=colors["fg"],
            font=FONTS["body"],
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=14,
            pady=5,
            **kwargs,
        )
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event):
        self.config(bg=self._colors["hover_bg"])

    def _on_leave(self, _event):
        self.config(bg=self._colors["bg"])


# ---------------------------------------------------------------------------
# DiceFace
# ---------------------------------------------------------------------------
_PIP_POSITIONS = {
    1: [(32, 32)],
    2: [(20, 20), (44, 44)],
    3: [(20, 20), (32, 32), (44, 44)],
    4: [(20, 20), (44, 20), (20, 44), (44, 44)],
    5: [(20, 20), (44, 20), (32, 32), (20, 44), (44, 44)],
    6: [(20, 20), (44, 20), (20, 32), (44, 32), (20, 44), (44, 44)],
}


class DiceFace(tk.Canvas):
    """64x64 canvas that draws a dice face with pips."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            width=64,
            height=64,
            bg=COLORS["bg_secondary"],
            highlightthickness=0,
            **kwargs,
        )
        self._value = 1
        self._pip_color = COLORS["text_primary"]
        self._draw()

    @property
    def value(self) -> int:
        return self._value

    def set_value(self, val: int, pip_color: str | None = None):
        self._value = max(1, min(6, val))
        self._pip_color = pip_color or COLORS["text_primary"]
        self._draw()

    def flash_gold(self, val: int):
        self.set_value(val, pip_color=COLORS["accent_gold"])

    def _draw(self):
        self.delete("all")
        # Rounded rectangle background
        self._rounded_rect(2, 2, 62, 62, 10, fill=COLORS["bg_tertiary"], outline=COLORS["border_subtle"])
        # Pips
        for x, y in _PIP_POSITIONS.get(self._value, []):
            self.create_oval(x - 5, y - 5, x + 5, y + 5, fill=self._pip_color, outline="")

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
            x1 + r, y1,
        ]
        self.create_polygon(points, smooth=True, **kwargs)


# ---------------------------------------------------------------------------
# ToastOverlay
# ---------------------------------------------------------------------------
_TOAST_STYLES = {
    "success": (COLORS["success_bg"], COLORS["accent_green"]),
    "error": (COLORS["error_bg"], COLORS["accent_red"]),
    "info": (COLORS["info_bg"], COLORS["accent_blue"]),
}


class ToastOverlay:
    """Non-blocking notification toasts positioned at the top-right of the root window."""

    def __init__(self, root: tk.Tk):
        self._root = root
        self._active: list[tk.Frame] = []

    def show(self, message: str, toast_type: str = "info", duration_ms: int | None = None):
        bg, accent = _TOAST_STYLES.get(toast_type, _TOAST_STYLES["info"])
        if duration_ms is None:
            duration_ms = 4000 if toast_type == "error" else 2500

        toast = tk.Frame(
            self._root,
            bg=bg,
            highlightbackground=accent,
            highlightthickness=1,
            padx=12,
            pady=8,
        )

        # Accent bar on the left
        bar = tk.Frame(toast, bg=accent, width=4)
        bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        tk.Label(
            toast,
            text=message,
            bg=bg,
            fg=COLORS["text_primary"],
            font=FONTS["body"],
            wraplength=340,
            justify="left",
        ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Close button
        close_btn = tk.Label(
            toast,
            text="\u00d7",
            bg=bg,
            fg=COLORS["text_muted"],
            font=FONTS["body"],
            cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, padx=(8, 0))
        close_btn.bind("<Button-1>", lambda _e: self._dismiss(toast))

        # Position at top-right, stacked below existing toasts
        y_offset = 8
        for active in self._active:
            if active.winfo_exists():
                y_offset += active.winfo_reqheight() + 6
        toast.place(relx=1.0, x=-12, y=y_offset, anchor="ne")

        self._active.append(toast)
        self._root.after(duration_ms, lambda: self._dismiss(toast))

    def _dismiss(self, toast: tk.Frame):
        if toast in self._active:
            self._active.remove(toast)
        if toast.winfo_exists():
            toast.destroy()
        # Reposition remaining toasts
        y_offset = 8
        for active in self._active:
            if active.winfo_exists():
                active.place(relx=1.0, x=-12, y=y_offset, anchor="ne")
                y_offset += active.winfo_reqheight() + 6
