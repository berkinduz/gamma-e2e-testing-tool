import platform
import tkinter as tk
from tkinter import ttk


def build_history_tab(app) -> None:
    history_frame = tk.Frame(app.notebook, bg=app.colors["background"])
    app.notebook.add(history_frame, text="History")

    history_content = tk.Frame(history_frame, bg=app.colors["background"])
    history_content.pack(
        fill=tk.BOTH, expand=True, padx=app.spacing["md"], pady=app.spacing["md"]
    )

    header_frame = tk.Frame(history_content, bg=app.colors["surface"])
    header_frame.pack(fill=tk.X, pady=(0, app.spacing["md"]))
    tk.Label(
        header_frame,
        text="Test Execution History",
        font=(app.fonts["default"], 14, "bold"),
        bg=app.colors["surface"],
        fg=app.colors["text_primary"],
    ).pack(side=tk.LEFT, padx=app.spacing["md"], pady=app.spacing["sm"])

    clear_logs_btn = (ttk.Button if platform.system() == "Darwin" else tk.Button)(
        header_frame,
        text="🧹 Clear All Logs",
        command=app.clear_all_logs,
        **(
            {"style": "Secondary.TButton", "cursor": "hand2"}
            if platform.system() == "Darwin"
            else {
                "bg": app.colors["secondary"],
                "fg": app.contrast_on(app.colors["secondary"]),
                "bd": 0,
                "relief": "flat",
                "cursor": "hand2",
            }
        )
    )
    clear_logs_btn.pack(
        side=tk.RIGHT,
        padx=(app.spacing["sm"], app.spacing["md"]),
        pady=app.spacing["sm"],
    )

    load_btn = (ttk.Button if platform.system() == "Darwin" else tk.Button)(
        header_frame,
        text=" Refresh",
        command=app.load_history_data,
        **(
            {"style": "Primary.TButton", "cursor": "hand2"}
            if platform.system() == "Darwin"
            else {
                "bg": app.colors["primary"],
                "fg": app.contrast_on(app.colors["primary"]),
                "bd": 0,
                "relief": "flat",
                "cursor": "hand2",
            }
        )
    )
    load_btn.pack(side=tk.RIGHT, padx=app.spacing["md"], pady=app.spacing["sm"])

    columns = ("Date", "Time", "Project", "Mode", "Status", "Duration", "Details")
    app.history_tree = ttk.Treeview(
        history_content, columns=columns, show="headings", height=15
    )
    column_widths = {
        "Date": 100,
        "Time": 80,
        "Project": 120,
        "Mode": 80,
        "Status": 80,
        "Duration": 80,
        "Details": 400,
    }
    for col in columns:
        app.history_tree.heading(col, text=col)
        app.history_tree.column(col, width=column_widths[col], anchor="center")

    scrollbar = ttk.Scrollbar(
        history_content, orient="vertical", command=app.history_tree.yview
    )
    app.history_tree.configure(yscrollcommand=scrollbar.set)
    app.history_tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    app.history_tree.bind("<Double-1>", app.show_full_history_details)
