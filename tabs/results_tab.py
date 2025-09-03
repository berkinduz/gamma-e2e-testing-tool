import platform
import tkinter as tk
from tkinter import ttk, scrolledtext


def build_results_tab(app) -> None:
    results_frame = tk.Frame(app.notebook, bg=app.colors["background"])
    app.notebook.add(results_frame, text="Results")

    results_content = tk.Frame(results_frame, bg=app.colors["background"])
    results_content.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    header_frame = tk.Frame(results_content, bg=app.colors["surface"])
    header_frame.pack(fill=tk.X, padx=app.spacing["md"], pady=app.spacing["md"])
    tk.Label(
        header_frame,
        text="Test Results & Artifacts",
        font=(app.fonts["default"], 14, "bold"),
        bg=app.colors["surface"],
        fg=app.colors["text_primary"],
    ).pack(side=tk.LEFT)
    refresh_btn = ttk.Button(
        header_frame,
        text="🔄 Refresh",
        command=app.refresh_results,
        style="Primary.TButton",
        cursor="hand2",
    )
    refresh_btn.pack(side=tk.RIGHT)

    content_frame = tk.Frame(results_content, bg=app.colors["background"])
    content_frame.pack(
        fill=tk.BOTH,
        expand=True,
        padx=app.spacing["md"],
        pady=(app.spacing["sm"], app.spacing["md"]),
    )

    left_frame = tk.Frame(content_frame, bg=app.colors["background"])
    left_frame.pack(
        side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, app.spacing["sm"])
    )
    tk.Label(
        left_frame,
        text="Test Summary",
        font=(app.fonts["default"], 12, "bold"),
        bg=app.colors["background"],
        fg=app.colors["text_primary"],
    ).pack(anchor=tk.W, pady=(0, app.spacing["sm"]))
    app.summary_text = scrolledtext.ScrolledText(
        left_frame,
        bg=app.colors["surface"],
        fg=app.colors["text_primary"],
        font=(app.fonts["mono"], 10),
        insertbackground=app.colors["primary"],
        selectbackground=app.colors["selection"],
        relief="flat",
        bd=0,
        padx=10,
        pady=10,
        wrap=tk.WORD,
    )
    app.summary_text.pack(fill=tk.BOTH, expand=True)

    right_frame = tk.Frame(content_frame, bg=app.colors["background"])
    right_frame.pack(
        side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(app.spacing["sm"], 0)
    )
    tk.Label(
        right_frame,
        text="Test Artifacts",
        font=(app.fonts["default"], 12, "bold"),
        bg=app.colors["background"],
        fg=app.colors["text_primary"],
    ).pack(anchor=tk.W, pady=(0, app.spacing["sm"]))

    app.artifacts_listbox = tk.Listbox(
        right_frame,
        bg=app.colors["surface"],
        fg=app.colors["text_primary"],
        font=(app.fonts["mono"], 10),
        selectbackground=app.colors["primary"],
        relief="flat",
        bd=0,
    )
    app.artifacts_listbox.pack(fill=tk.BOTH, expand=True, padx=(0, 10))
    app.artifacts_listbox.bind(
        "<Double-1>", lambda e: app.view_selected_artifact_button()
    )

    artifact_buttons = tk.Frame(right_frame, bg=app.colors["background"])
    artifact_buttons.pack(fill=tk.X, pady=(app.spacing["sm"], 0))
    (ttk.Button if platform.system() == "Darwin" else tk.Button)(
        artifact_buttons,
        text="📁 Open Folder",
        command=app.open_logs_folder,
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
    ).pack(side=tk.LEFT, padx=(0, 5))
    (ttk.Button if platform.system() == "Darwin" else tk.Button)(
        artifact_buttons,
        text="👁️ View Selected",
        command=app.view_selected_artifact_button,
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
    ).pack(side=tk.LEFT)
