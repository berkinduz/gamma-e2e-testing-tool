import os
import webbrowser
import tkinter as tk
from tkinter import ttk
from ui.theme import get_available_themes, switch_theme, load_theme


def build_settings_tab(app) -> None:
    try:
        settings_frame = tk.Frame(app.notebook, bg=app.colors["background"])
        app.notebook.add(settings_frame, text="Settings")

        body = tk.Frame(settings_frame, bg=app.colors["background"])
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Section: Theme Selection
        tk.Label(
            body,
            text="Theme Settings",
            bg=app.colors["background"],
            fg=app.colors["text_secondary"],
            font=(app.fonts["default"], 10, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        tk.Label(
            body,
            text="Theme",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=1, column=0, sticky="w")

        # Theme selection
        available_themes = get_available_themes()
        current_theme = load_theme().name.lower()
        theme_var = tk.StringVar(value=current_theme)

        theme_combo = ttk.Combobox(
            body,
            textvariable=theme_var,
            values=available_themes,
            state="readonly",
            width=20,
        )
        theme_combo.grid(row=1, column=1, sticky="w", padx=(8, 0))

        def on_theme_change(event=None):
            # Just update the variable, don't show popup yet
            selected_theme = theme_var.get()
            app.add_log(f"🎨 Theme selected: {selected_theme.title()}", "info")

        theme_combo.bind("<<ComboboxSelected>>", on_theme_change)

        # Section: Environment variables (per project)
        tk.Label(
            body,
            text="Environment Variables (per project)",
            bg=app.colors["background"],
            fg=app.colors["text_secondary"],
            font=(app.fonts["default"], 10, "bold"),
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(20, 6))
        tk.Label(
            body,
            text="User Agent",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=3, column=0, sticky="w")
        ua_var = tk.StringVar(
            value=os.getenv("{}_USER_AGENT".format(app.project_var.get().upper()), "")
        )
        ua_entry = tk.Entry(
            body,
            textvariable=ua_var,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        )
        ua_entry.grid(row=3, column=1, sticky="we", padx=(8, 0))

        tk.Label(
            body,
            text="Email (login)",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=4, column=0, sticky="w", pady=(6, 0))
        email_var = tk.StringVar(
            value=os.getenv("{}_EMAIL".format(app.project_var.get().upper()), "")
        )
        tk.Entry(
            body,
            textvariable=email_var,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        ).grid(row=4, column=1, sticky="we", padx=(8, 0), pady=(6, 0))

        tk.Label(
            body,
            text="Password (login)",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=5, column=0, sticky="w", pady=(6, 0))
        pw_var = tk.StringVar(
            value=os.getenv("{}_PASSWORD".format(app.project_var.get().upper()), "")
        )
        tk.Entry(
            body,
            textvariable=pw_var,
            show="*",
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        ).grid(row=5, column=1, sticky="we", padx=(8, 0), pady=(6, 0))

        # Section: Defaults (minimal)
        tk.Label(
            body,
            text="Defaults",
            bg=app.colors["background"],
            fg=app.colors["text_secondary"],
            font=(app.fonts["default"], 10, "bold"),
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(20, 6))

        # Section: Browser (normal mode)
        tk.Label(
            body,
            text="Browser (normal mode)",
            bg=app.colors["background"],
            fg=app.colors["text_secondary"],
            font=(app.fonts["default"], 10, "bold"),
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 6))
        tk.Label(
            body,
            text="Window Size (WxH)",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=8, column=0, sticky="w")
        bw_var = tk.StringVar(value=os.getenv("BROWSER_WIDTH", "1400"))
        bh_var = tk.StringVar(value=os.getenv("BROWSER_HEIGHT", "1000"))
        size_frame = tk.Frame(body, bg=app.colors["background"])
        size_frame.grid(row=8, column=1, sticky="w", padx=(8, 0))
        tk.Entry(
            size_frame,
            textvariable=bw_var,
            width=6,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        ).pack(side=tk.LEFT)
        tk.Label(
            size_frame,
            text="x",
            bg=app.colors["background"],
            fg=app.colors["text_secondary"],
        ).pack(side=tk.LEFT, padx=4)
        tk.Entry(
            size_frame,
            textvariable=bh_var,
            width=6,
            bg=app.colors["surface"],
            fg=app.colors["text_primary"],
            insertbackground=app.colors["text_primary"],
        ).pack(side=tk.LEFT)

        tk.Label(
            body,
            text="Open DevTools",
            bg=app.colors["background"],
            fg=app.colors["text_primary"],
        ).grid(row=9, column=0, sticky="w", pady=(6, 0))
        devtools_var = tk.BooleanVar(value=os.getenv("DEVTOOLS_OPEN", "0") == "1")
        ttk.Checkbutton(body, variable=devtools_var).grid(
            row=9, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )

        # Save/Close
        actions = tk.Frame(settings_frame, bg=app.colors["surface"])
        actions.pack(fill=tk.X)
        # Save feedback
        app.settings_status_var = tk.StringVar(value="")
        tk.Label(
            actions,
            textvariable=app.settings_status_var,
            bg=app.colors["surface"],
            fg=app.colors["text_secondary"],
            font=(app.fonts["default"], 10),
        ).pack(side=tk.LEFT, padx=12)

        def _save():
            # Check what changes were made
            current_theme = load_theme().name.lower()
            selected_theme = theme_var.get()
            theme_changed = current_theme != selected_theme

            # Check if any environment variables changed
            env_changed = False
            browser_changed = False
            try:
                prefix = app.project_var.get().upper().replace("-", "_")

                # Check project-specific environment variables
                project_current = {
                    f"{prefix}_USER_AGENT": os.getenv(f"{prefix}_USER_AGENT", ""),
                    f"{prefix}_EMAIL": os.getenv(f"{prefix}_EMAIL", ""),
                    f"{prefix}_PASSWORD": os.getenv(f"{prefix}_PASSWORD", ""),
                }
                project_new = {
                    f"{prefix}_USER_AGENT": ua_var.get().strip(),
                    f"{prefix}_EMAIL": email_var.get().strip(),
                    f"{prefix}_PASSWORD": pw_var.get().strip(),
                }
                env_changed = project_current != project_new

                # Check browser settings separately
                browser_current = {
                    "BROWSER_WIDTH": os.getenv("BROWSER_WIDTH", "1400"),
                    "BROWSER_HEIGHT": os.getenv("BROWSER_HEIGHT", "1000"),
                    "DEVTOOLS_OPEN": os.getenv("DEVTOOLS_OPEN", "0"),
                }
                browser_new = {
                    "BROWSER_WIDTH": bw_var.get().strip(),
                    "BROWSER_HEIGHT": bh_var.get().strip(),
                    "DEVTOOLS_OPEN": "1" if devtools_var.get() else "0",
                }
                browser_changed = browser_current != browser_new

            except Exception:
                pass

            # Persist to .env-like file minimally (append or create project overrides)
            try:
                lines = []
                target = ".env"
                if os.path.exists(target):
                    with open(target, "r", encoding="utf-8") as f:
                        lines = f.read().splitlines()
                prefix = app.project_var.get().upper().replace("-", "_")
                kv = {
                    f"{prefix}_USER_AGENT": ua_var.get().strip(),
                    f"{prefix}_EMAIL": email_var.get().strip(),
                    f"{prefix}_PASSWORD": pw_var.get().strip(),
                    "BROWSER_WIDTH": bw_var.get().strip(),
                    "BROWSER_HEIGHT": bh_var.get().strip(),
                    "DEVTOOLS_OPEN": "1" if devtools_var.get() else "0",
                    # Additional UI/environment settings can be appended here
                }
                # Replace or append
                for k, v in kv.items():
                    found = False
                    for i, line in enumerate(lines):
                        if line.startswith(k + "="):
                            lines[i] = f"{k}={v}"
                            found = True
                            break
                    if not found:
                        lines.append(f"{k}={v}")
                with open(target, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                # Reload env and refresh projects so changes apply immediately
                try:
                    from dotenv import load_dotenv as _ld

                    _ld(override=True)
                    app.projects = app.discover_projects()
                    app.refresh_all_project_combos(app.project_var.get())
                except Exception:
                    pass
                app.add_log("✅ Settings saved and applied", "success")

                # Log browser settings changes (no restart required)
                if browser_changed:
                    app.add_log(
                        "🌐 Browser settings updated (no restart required)", "info"
                    )

                # Visible feedback in settings
                try:
                    app.settings_status_var.set("Saved")
                    app.root.after(2000, lambda: app.settings_status_var.set(""))
                except Exception:
                    pass

                # Show restart popup if any changes require restart
                if theme_changed or env_changed:
                    import tkinter.messagebox as msgbox

                    # Apply theme change if needed
                    if theme_changed:
                        if switch_theme(selected_theme):
                            app.add_log(
                                f"🎨 Theme changed to: {selected_theme.title()}", "info"
                            )
                        else:
                            app.add_log(
                                f"❌ Failed to change theme to: {selected_theme}",
                                "error",
                            )

                    # Show generic restart popup
                    changes_list = []
                    if theme_changed:
                        changes_list.append(
                            f"• Theme changed to '{selected_theme.title()}'"
                        )
                    if env_changed:
                        changes_list.append("• Environment variables updated")

                    changes_text = "\n".join(changes_list)
                    msgbox.showinfo(
                        "Settings Saved",
                        f"Settings have been saved successfully!\n\n"
                        f"Changes made:\n{changes_text}\n\n"
                        "Please restart the application to see all changes.\n"
                        "The new settings will be applied on next startup.",
                    )

            except Exception as e:
                app.add_log(f"❌ Failed to save settings: {e}", "error")

        ttk.Button(
            actions,
            text="Save",
            command=_save,
            style="Primary.TButton",
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=8, pady=8)

        # Footer
        footer = tk.Frame(settings_frame, bg=app.colors["background"])
        footer.pack(fill=tk.X, pady=(4, 10))
        tk.Label(
            footer,
            text="Created by Berkin",
            bg=app.colors["background"],
            fg=app.colors["text_secondary"],
            font=(app.fonts["default"], 10),
        ).pack(side=tk.LEFT, padx=(12, 6))
        link = tk.Label(
            footer,
            text="berkin.tech/en/about",
            bg=app.colors["background"],
            fg=app.colors["secondary"],
            cursor="hand2",
        )
        link.pack(side=tk.LEFT)
        link.bind(
            "<Button-1>", lambda e: webbrowser.open("https://berkin.tech/en/about")
        )

        # Grid weights
        body.grid_columnconfigure(1, weight=1)
    except Exception as e:
        app.add_log(f"❌ Settings init failed: {e}", "error")
