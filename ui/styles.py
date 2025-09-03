from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import ttk


def apply_classic_overrides(root: tk.Tk, theme: Any) -> None:
    try:
        root.option_add("*Background", theme.colors["background"])
        root.option_add("*Foreground", theme.colors["text_primary"])
        root.option_add("*selectBackground", theme.colors["primary"])
        root.option_add("*selectForeground", theme.colors["text_primary"])
        root.option_add("*insertBackground", theme.colors["text_primary"])
        root.option_add("* troughColor", theme.colors["surface"])
    except Exception:
        pass


def setup_ttk_styles(root: tk.Tk, theme: Any) -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TFrame", background=theme.colors["background"])
