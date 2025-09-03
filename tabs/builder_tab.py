import platform
import tkinter as tk
from tkinter import ttk


def build_builder_tab(app) -> None:
    try:
        builder_frame = tk.Frame(app.notebook, bg=app.colors["background"])
        app.notebook.add(builder_frame, text="Test Builder")

        header = tk.Frame(builder_frame, bg=app.colors["surface"])
        header.pack(fill=tk.X, padx=app.spacing["md"], pady=app.spacing["md"])
        tk.Label(
            header,
            text="Create New Flow",
            font=(app.fonts["default"], 14, "bold"),
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
        ).pack(side=tk.LEFT)
        (ttk.Button if platform.system() == "Darwin" else tk.Button)(
            header,
            text="➕ New Project",
            command=app.builder_create_new_project,
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
            ),
        ).pack(side=tk.RIGHT)

        form = tk.Frame(builder_frame, bg=app.colors["background"])
        form.pack(
            fill=tk.BOTH, expand=True, padx=app.spacing["md"], pady=app.spacing["md"]
        )

        tk.Label(
            form,
            text="Project",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=0, column=0, sticky="w")
        app.builder_project_var = tk.StringVar(
            value=list(app.projects.keys())[0] if app.projects else ""
        )
        app.builder_project_combo = ttk.Combobox(
            form,
            textvariable=app.builder_project_var,
            values=list(app.projects.keys()),
            state="readonly",
        )
        app.builder_project_combo.grid(row=0, column=1, sticky="we", padx=(8, 0))

        tk.Label(
            form,
            text="Flow name",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        app.builder_flow_var = tk.StringVar()
        app.builder_flow_entry = tk.Entry(
            form,
            textvariable=app.builder_flow_var,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        )
        app.builder_flow_entry.grid(
            row=1, column=1, sticky="we", padx=(8, 0), pady=(6, 0)
        )

        steps_frame = tk.LabelFrame(
            form,
            text="Steps",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        )
        steps_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        form.grid_rowconfigure(2, weight=1)
        form.grid_columnconfigure(1, weight=1)

        sf = tk.Frame(steps_frame, bg=app.colors["background"])
        sf.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            sf,
            text="Action",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=0, column=0, sticky="w")
        app.step_action_var = tk.StringVar(value="navigate")
        app.step_action_combo = ttk.Combobox(
            sf,
            textvariable=app.step_action_var,
            values=["navigate", "click", "fill", "wait"],
            state="readonly",
            width=12,
        )
        app.step_action_combo.grid(row=0, column=1, padx=(6, 12))
        app.step_action_combo.bind(
            "<<ComboboxSelected>>", lambda e: app.builder_on_action_change()
        )

        app.step_target_label = tk.Label(
            sf,
            text="Selector / URL",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        )
        app.step_target_label.grid(row=0, column=2, sticky="w")
        app.step_target_var = tk.StringVar()
        app.step_target_entry = tk.Entry(
            sf,
            textvariable=app.step_target_var,
            width=30,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        )
        app.step_target_entry.grid(row=0, column=3, padx=(6, 12))
        app.step_target_entry.bind("<Return>", lambda e: app.builder_add_step())

        app.step_value_label = tk.Label(
            sf,
            text="Value (only for fill)",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        )
        app.step_value_label.grid(row=0, column=4, sticky="w")
        app.step_value_var = tk.StringVar()
        app.step_value_entry = tk.Entry(
            sf,
            textvariable=app.step_value_var,
            width=20,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        )
        app.step_value_entry.grid(row=0, column=5, padx=(6, 12))
        app.step_value_entry.configure(state=tk.DISABLED)
        app.step_value_entry.bind("<Return>", lambda e: app.builder_add_step())
        app.step_value_spacer = tk.Frame(
            sf, width=200, height=1, bg=app.colors["background"]
        )
        app.step_value_spacer.grid(row=0, column=4, columnspan=2, sticky="w")

        tk.Label(
            sf,
            text="Timeout",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=0, column=6, sticky="w")
        app.step_timeout_var = tk.StringVar(value="40")
        app.step_timeout_entry = tk.Entry(
            sf,
            textvariable=app.step_timeout_var,
            width=6,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        )
        app.step_timeout_entry.grid(row=0, column=7, padx=(6, 12))
        app.step_timeout_entry.bind("<Return>", lambda e: app.builder_add_step())

        (ttk.Button if platform.system() == "Darwin" else tk.Button)(
            sf,
            text="Add Step",
            command=app.builder_add_step,
            **(
                {"style": "Primary.TButton", "cursor": "hand2"}
                if platform.system() == "Darwin"
                else {
                    "bg": app.colors["primary"],
                    "fg": app.contrast_on(app.colors["primary"]),
                    "activebackground": app.colors["surface_dark"],
                    "activeforeground": app.colors["text_primary"],
                    "bd": 0,
                }
            ),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        app.builder_on_action_change()

        app.steps_listbox = tk.Listbox(
            steps_frame,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            selectbackground=app.colors["primary"],
        )
        app.steps_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        btns = tk.Frame(steps_frame, bg=app.colors["background"])
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        (ttk.Button if platform.system() == "Darwin" else tk.Button)(
            btns,
            text="Remove Selected",
            command=app.builder_remove_selected,
            **(
                {"style": "Secondary.TButton", "cursor": "hand2"}
                if platform.system() == "Darwin"
                else {
                    "bg": app.colors["secondary"],
                    "fg": app.contrast_on(app.colors["secondary"]),
                    "activebackground": app.colors["surface_dark"],
                    "activeforeground": app.colors["text_primary"],
                    "bd": 0,
                }
            ),
        ).pack(side=tk.LEFT, padx=(10, 0))

        save_frame = tk.Frame(form, bg=app.colors["background"])
        save_frame.grid(row=3, column=0, columnspan=3, sticky="we", pady=(10, 0))
        app.builder_error_var = tk.StringVar()
        app.builder_error_label = tk.Label(
            save_frame,
            textvariable=app.builder_error_var,
            bg=app.colors["background"],
            fg=app.colors["danger"],
        )
        app.builder_error_label.pack(side=tk.LEFT, padx=(0, 10))
        app.builder_error_var.set("")
        (ttk.Button if platform.system() == "Darwin" else tk.Button)(
            save_frame,
            text="Save Flow",
            command=app.builder_save_flow,
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
            ),
        ).pack(side=tk.LEFT)
        app.builder_status_var = tk.StringVar()
        tk.Label(
            save_frame,
            textvariable=app.builder_status_var,
            bg=app.colors["background"],
            fg=app.colors["text_secondary"],
        ).pack(side=tk.LEFT, padx=(10, 0))

    except Exception as e:
        app.add_log(f"❌ Error initializing Test Builder: {e}", "error")
