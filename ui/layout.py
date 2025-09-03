import os
import platform
import tkinter as tk
from PIL import Image, ImageTk


def build_shell(app) -> None:
    app.main_frame = tk.Frame(app.root, bg=app.colors["background"])
    app.main_frame.pack(fill=tk.BOTH, expand=True)


def build_header(app) -> None:
    app.header = tk.Frame(app.main_frame, bg=app.colors["surface_dark"], height=56)
    app.header.pack(fill=tk.X)
    app.header.pack_propagate(False)

    left = tk.Frame(app.header, bg=app.colors["surface_dark"])
    left.pack(side=tk.LEFT, padx=app.spacing["lg"], pady=app.spacing["xs"])
    try:
        if os.path.exists("assets/logo.png"):
            _logo_img = Image.open("assets/logo.png").resize(
                (48, 48), Image.Resampling.LANCZOS
            )
            app.logo_icon = ImageTk.PhotoImage(_logo_img)
            tk.Label(left, image=app.logo_icon, bg=app.colors["surface_dark"]).pack(
                side=tk.LEFT
            )
    except Exception:
        pass
    tk.Label(
        left,
        text="Gamma",
        font=(app.fonts["default"], 16, "bold"),
        bg=app.colors["surface_dark"],
        fg=app.colors["text_primary"],
    ).pack(side=tk.LEFT, padx=(8, 0))

    right_header = tk.Frame(app.header, bg=app.colors["surface_dark"])
    if platform.system() == "Darwin":
        right_header.pack(
            side=tk.RIGHT, padx=(app.spacing["lg"] + 8), pady=app.spacing["xs"]
        )
    else:
        right_header.pack(side=tk.RIGHT, padx=app.spacing["lg"], pady=app.spacing["xs"])

    if getattr(app, "settings_icon", None) is not None:
        if platform.system() == "Darwin":
            btn = tk.Label(
                right_header,
                image=app.settings_icon,
                bg=app.colors["surface_dark"],
                cursor="hand2",
            )
            btn.bind("<Button-1>", lambda e: app.notebook.select(3))
        else:
            btn = tk.Button(
                right_header,
                image=app.settings_icon,
                command=lambda: app.notebook.select(3),
                bg=app.colors["surface_dark"],
                bd=0,
                relief="flat",
                cursor="hand2",
                activebackground=app.colors["surface_dark"],
            )
    else:
        if platform.system() == "Darwin":
            btn = tk.Label(
                right_header,
                text="⚙",
                bg=app.colors["surface_dark"],
                fg=app.colors["text_primary"],
                font=(app.fonts["default"], 18, "bold"),
                cursor="hand2",
            )
            btn.bind("<Button-1>", lambda e: app.notebook.select(3))
        else:
            btn = tk.Button(
                right_header,
                text="⚙",
                command=lambda: app.notebook.select(3),
                font=(app.fonts["default"], 16, "bold"),
                bg=app.colors["surface_dark"],
                fg=app.colors["text_primary"],
                bd=0,
                relief="flat",
                cursor="hand2",
                activebackground=app.colors["surface_dark"],
            )
    btn.pack()
    try:
        btn.configure(
            highlightthickness=0,
            borderwidth=0,
            highlightbackground=app.colors["surface_dark"],
        )
    except Exception:
        pass

    app.body = tk.Frame(app.main_frame, bg=app.colors["background"])
    app.body.pack(fill=tk.BOTH, expand=True)

    app.sidebar = tk.Frame(app.body, bg=app.colors["surface"], width=260)
    app.sidebar.pack(side=tk.LEFT, fill=tk.Y)
    app.sidebar.pack_propagate(False)
