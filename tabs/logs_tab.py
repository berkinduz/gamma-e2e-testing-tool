import tkinter as tk
from tkinter import scrolledtext


def build_logs_tab(app) -> None:
    logs_frame = tk.Frame(app.notebook, bg=app.colors["background"])
    app.notebook.add(logs_frame, text="Logs")

    logs_container = tk.Frame(logs_frame, bg=app.colors["background"])
    logs_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    app.logs_text = scrolledtext.ScrolledText(
        logs_container,
        bg=app.colors["surface_dark"],
        fg=app.colors["text_primary"],
        font=(app.fonts["mono"], 11),
        insertbackground=app.colors["primary"],
        selectbackground=app.colors["selection"],
        relief="flat",
        bd=0,
        padx=15,
        pady=15,
        wrap=tk.WORD,
    )
    app.logs_text.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    app.logs_text.tag_configure("info", foreground=app.colors["secondary"])
    app.logs_text.tag_configure("success", foreground=app.colors["success"])
    app.logs_text.tag_configure("warning", foreground=app.colors["warning"])
    app.logs_text.tag_configure("error", foreground=app.colors["danger"])
    app.logs_text.tag_configure("timestamp", foreground=app.colors["text_secondary"])
    app.logs_text.tag_configure(
        "link", foreground=app.colors["secondary"], underline=True
    )
    app.logs_text.tag_bind("link", "<Button-1>", lambda e: app.notebook.select(1))
    app.logs_text.tag_bind(
        "link", "<Enter>", lambda e: app.logs_text.config(cursor="hand2")
    )
    app.logs_text.tag_bind(
        "link", "<Leave>", lambda e: app.logs_text.config(cursor="xterm")
    )
