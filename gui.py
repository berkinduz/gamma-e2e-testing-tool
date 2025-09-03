import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import subprocess
import threading
import queue
import json
import os
import time
import sys
from datetime import datetime
import platform
import shutil
import webbrowser
from PIL import Image, ImageTk
from ui.theme import load_theme
from ui.styles import apply_classic_overrides, setup_ttk_styles
from ui.icons import load_icons
from core.runner import (
    start_test,
    run_test_process,
    stop_test,
    consume_test_logs,
    create_test_summary,
    calculate_test_duration,
    add_log,
    clear_logs,
)
from core.history import (
    load_test_history,
    load_history_data,
    clear_all_logs,
)
from core.results import (
    refresh_results,
    open_logs_folder,
    view_selected_artifact,
    auto_refresh_all_tabs,
    refresh_results_detailed,
    view_selected_artifact_button,
    open_text_artifact_internally,
    open_file_externally,
)
from core.builder import (
    refresh_flows_for_project,
    _normalize_project_folder,
    refresh_all_project_combos,
    builder_create_new_project,
    builder_add_step,
    builder_remove_selected,
    builder_save_flow,
    builder_on_action_change,
    _validate_flow_data,
)
from core.utils import (
    _hex_to_rgb,
    _load_prefs,
    _save_prefs,
    _relative_luminance,
    contrast_on,
    load_theme_config,
    on_project_change,
    discover_projects,
    format_test_summary,
)
from ui.layout import (
    build_shell as layout_build_shell,
    build_header as layout_build_header,
)
from tabs.logs_tab import build_logs_tab
from tabs.results_tab import build_results_tab
from tabs.history_tab import build_history_tab
from tabs.builder_tab import build_builder_tab
from tabs.settings_tab import build_settings_tab
from dotenv import load_dotenv

# Global font fallback for compatibility
DEFAULT_FONT = "Inter"


class TestRunnerGUI:
    def __init__(self, root):
        # Load environment variables from .env if present
        try:
            load_dotenv(override=False)
        except Exception:
            pass
        self.root = root
        self.root.title("Gamma Test Runner")
        self.root.geometry("1400x800")
        self.root.minsize(1000, 700)

        # Discover projects dynamically from filesystem (generic)
        self.projects = self.discover_projects()

        # Simple preferences to remember last selections
        self.prefs_path = os.path.join(os.path.dirname(__file__), ".gamma_prefs.json")
        self.prefs = self._load_prefs()

        # Load theme configuration
        self.load_theme_config()

        # Configure main window
        self.root.configure(bg=self.colors["background"])

        # Configure styles
        self.setup_styles()

        # Test state
        self.test_process = None
        self.test_running = False
        self.log_queue = queue.Queue()
        self.auto_scroll_var = tk.BooleanVar(value=True)

        # Load icons
        self.load_icons()

        # Build brand-new layout (delegated to modules)
        self.build_shell()
        self.build_header()
        self.build_tabs()

        # Apply initial button states
        self.update_button_states()

        # Start log consumer
        self.root.after(100, lambda: self.consume_logs())

        # Load test history
        self.load_test_history()

    def build_shell(self):
        layout_build_shell(self)

    def build_header(self):
        layout_build_header(self)

        # Controls in sidebar
        default_project = (
            self.prefs.get("project")
            if self.prefs.get("project") in self.projects
            else next(iter(self.projects.keys()), "")
        )
        self.project_var = tk.StringVar(value=default_project)
        tk.Label(
            self.sidebar,
            text="Project",
            bg=self.colors["surface"],
            fg=self.colors["text_secondary"],
            font=(self.fonts["default"], 10),
        ).pack(anchor="w", padx=12, pady=(12, 2))
        self.project_combo = ttk.Combobox(
            self.sidebar,
            textvariable=self.project_var,
            values=list(self.projects.keys()),
            state="readonly",
        )
        self.project_combo.pack(fill=tk.X, padx=12)
        self.project_combo.bind(
            "<<ComboboxSelected>>", lambda e: self.on_project_change()
        )

        self.flow_var = tk.StringVar()
        tk.Label(
            self.sidebar,
            text="Flow",
            bg=self.colors["surface"],
            fg=self.colors["text_secondary"],
            font=(self.fonts["default"], 10),
        ).pack(anchor="w", padx=12, pady=(10, 2))
        self.flow_combo = ttk.Combobox(
            self.sidebar, textvariable=self.flow_var, values=[], state="readonly"
        )
        self.flow_combo.pack(fill=tk.X, padx=12)
        self.flow_combo.bind("<<ComboboxSelected>>", lambda e: self._save_prefs())
        self.flow_map = {}
        if default_project:
            self.refresh_flows_for_project(default_project)

        self.mode_var = tk.StringVar(value=self.prefs.get("mode", "headless"))
        tk.Label(
            self.sidebar,
            text="Mode",
            bg=self.colors["surface"],
            fg=self.colors["text_secondary"],
            font=(self.fonts["default"], 10),
        ).pack(anchor="w", padx=12, pady=(10, 2))
        mode_combo = ttk.Combobox(
            self.sidebar,
            textvariable=self.mode_var,
            values=["headless", "normal"],
            state="readonly",
        )
        mode_combo.pack(fill=tk.X, padx=12)
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._save_prefs())

        # Actions
        actions = tk.Frame(self.sidebar, bg=self.colors["surface"])
        actions.pack(fill=tk.X, padx=12, pady=12)
        is_macos = platform.system() == "Darwin"
        self.run_button = ttk.Button(
            actions,
            text="Run",
            command=self.start_test,
            style="Primary.TButton",
            cursor="hand2",
        )
        if is_macos:
            self.run_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        else:
            # Non-macOS: use original tk.Button styling
            for w in list(actions.children.values()):
                w.destroy()
            self.run_button = tk.Button(
                actions,
                text="Run",
                command=self.start_test,
                font=(self.fonts["default"], 10, "bold"),
                bg=self.colors["primary"],
                fg=self.contrast_on(self.colors["primary"]),
                bd=0,
                relief="flat",
                cursor="hand2",
            )
            self.run_button.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.stop_button = ttk.Button(
            actions,
            text="Stop",
            command=self.stop_test,
            style="Surface.TButton",
            cursor="hand2",
        )
        if is_macos:
            self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(8, 0))
        else:
            self.stop_button.destroy()
            self.stop_button = tk.Button(
                actions,
                text="Stop",
                command=self.stop_test,
                font=(self.fonts["default"], 10, "bold"),
                bg=self.colors["surface_light"],
                fg=self.colors["text_primary"],
                bd=0,
                relief="flat",
                cursor="hand2",
            )
            self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(8, 0))

        # Navigation
        nav = tk.Frame(self.sidebar, bg=self.colors["surface"])
        nav.pack(fill=tk.X, padx=12)

        def _nav(label):
            try:
                idx = {"Logs": 0, "Results": 1, "History": 2, "Create Test": 4}[label]
                self.notebook.select(idx)
            except Exception:
                pass

        for lbl in ["Logs", "Results", "History", "Create Test"]:
            if is_macos:
                ttk.Button(
                    nav,
                    text=lbl,
                    command=lambda l=lbl: _nav(l),
                    style="Sidebar.TButton",
                    cursor="hand2",
                ).pack(fill=tk.X, pady=4)
            else:
                tk.Button(
                    nav,
                    text=lbl,
                    command=lambda l=lbl: _nav(l),
                    bg=self.colors["surface_light"],
                    fg=self.colors["text_primary"],
                    bd=0,
                    relief="flat",
                    cursor="hand2",
                ).pack(fill=tk.X, pady=4)

        # Status at bottom
        self.status_label = tk.Label(
            self.sidebar,
            text="Ready",
            font=(self.fonts["default"], 11, "bold"),
            bg=self.colors["surface"],
            fg=self.colors["success"],
        )
        self.status_label.pack(side=tk.BOTTOM, anchor="w", padx=12, pady=12)

        # Content container
        self.content = tk.Frame(self.body, bg=self.colors["background"])
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def build_tabs(self):
        self.notebook = ttk.Notebook(self.content)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        build_logs_tab(self)
        build_results_tab(self)
        build_history_tab(self)
        build_settings_tab(self)
        build_builder_tab(self)

    def setup_settings_tab(self):
        return None

    def _hex_to_rgb(self, hex_color: str):
        return _hex_to_rgb(hex_color)

    def _show_tooltip(self, widget, text: str):
        try:
            if self._tooltip:
                self._tooltip.destroy()
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 30
            self._tooltip = tk.Toplevel(self.root)
            self._tooltip.wm_overrideredirect(True)
            self._tooltip.configure(bg=self.colors["surface_light"])
            label = tk.Label(
                self._tooltip,
                text=text,
                bg=self.colors["surface_light"],
                fg=self.colors["text_primary"],
                font=(self.fonts["default"], 9),
                padx=6,
                pady=3,
            )
            label.pack()
            self._tooltip.wm_geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _hide_tooltip(self):
        try:
            if self._tooltip:
                self._tooltip.destroy()
                self._tooltip = None
        except Exception:
            pass

    def _load_prefs(self):
        return _load_prefs(self)

    def _save_prefs(self):
        _save_prefs(self)

    def _validate_flow_data(self, flow_obj: dict):
        return _validate_flow_data(flow_obj)

    def _relative_luminance(self, hex_color: str) -> float:
        return _relative_luminance(hex_color)

    def contrast_on(self, bg_hex: str) -> str:
        """Return black or white depending on background for readable text."""
        return contrast_on(bg_hex, self.colors)

    def load_theme_config(self):
        """Load theme via theme module"""
        load_theme_config(self)

    # Theme switching removed (single dark theme)

    def on_project_change(self):
        """Handle project selection change"""
        on_project_change(self)

    def discover_projects(self):
        """Scan tests/projects/* for project folders and return config dict (generic)."""
        return discover_projects()

    def refresh_flows_for_project(self, project_name: str):
        """Populate flow combobox with python files under the project's directory"""
        refresh_flows_for_project(self, project_name)

    def update_button_states(self):
        """Update button appearance based on current state"""
        # Defer until buttons are created
        if not hasattr(self, "start_button") or not hasattr(self, "stop_button"):
            return
        has_flow = hasattr(self, "flow_var") and bool(self.flow_var.get())
        if not self.test_running:
            # Start button enabled only if a flow is selected
            self.start_button.config(
                state=("normal" if has_flow else "disabled"),
                bg=self.colors["surface"],
                activebackground=self.colors["surface_secondary"],
            )
            # Stop button disabled
            self.stop_button.config(
                state="disabled",
                bg=self.colors["surface"],
                activebackground=self.colors["surface_secondary"],
            )
        else:
            # Start button disabled
            self.start_button.config(
                state="disabled",
                bg=self.colors["surface"],
                activebackground=self.colors["surface_secondary"],
            )
            # Stop button enabled
            self.stop_button.config(
                state="normal",
                bg=self.colors["surface"],
                activebackground=self.colors["surface_secondary"],
            )

    def load_icons(self):
        """Load and prepare icon images"""
        try:
            # Try to load PNG icons with PIL
            if os.path.exists("assets/play-icon.png"):
                play_img = Image.open("assets/play-icon.png").resize(
                    (32, 32), Image.Resampling.LANCZOS
                )
                self.play_icon = ImageTk.PhotoImage(play_img)
            else:
                self.play_icon = None

            if os.path.exists("assets/stop-icon.png"):
                stop_img = Image.open("assets/stop-icon.png").resize(
                    (32, 32), Image.Resampling.LANCZOS
                )
                self.stop_icon = ImageTk.PhotoImage(stop_img)
            else:
                self.stop_icon = None

            if os.path.exists("assets/delete-icon.png"):
                delete_img = Image.open("assets/delete-icon.png").resize(
                    (32, 32), Image.Resampling.LANCZOS
                )
                self.delete_icon = ImageTk.PhotoImage(delete_img)
            else:
                self.delete_icon = None

            # Settings icon (for header)
            self.settings_icon = None
            for name in [
                "settings@2x.png",
                "settings.png",
                "settings-icon.png",
                "gear.png",
            ]:
                path = os.path.join("assets", name)
                if os.path.exists(path):
                    # macOS: larger settings icon; others keep compact size
                    icon_w = 48 if platform.system() == "Darwin" else 24
                    icon_h = 48 if platform.system() == "Darwin" else 24
                    s_img = Image.open(path).resize(
                        (icon_w, icon_h), Image.Resampling.LANCZOS
                    )
                    self.settings_icon = ImageTk.PhotoImage(s_img)
                    break

        except Exception as e:
            print(f"Error loading icons: {e}")
            # Fallback to None if icons not found
            self.play_icon = None
            self.stop_icon = None
            self.delete_icon = None
            self.settings_icon = None

    def setup_styles(self):
        """Configure modern styling"""
        # Configure ttk styles
        style = ttk.Style()
        style.theme_use("clam")

        # macOS focus/active color overrides for classic Tk widgets
        # On macOS, when a window gains focus, Tk can adjust widget colors
        # in a way that reduces contrast for custom dark themes. Enforce
        # consistent colors via the option database for tk.* widgets.
        # Delegate classic overrides and ttk styles
        apply_classic_overrides(self.root, load_theme())

        # Configure Notebook style for dark theme
        style.configure(
            "TNotebook",
            background=self.colors["background"],
            borderwidth=0,
            tabmargins=[0, 0, 0, 0],
        )

        style.configure(
            "TNotebook.Tab",
            background=self.colors["surface"],
            foreground=self.colors["text_primary"],
            padding=[16, 8],
            borderwidth=0,
            focuscolor="none",
        )

        style.map(
            "TNotebook.Tab",
            background=[
                ("selected", self.colors["surface"]),
                ("active", self.colors["surface_light"]),
            ],
            foreground=[
                ("selected", self.colors["text_primary"]),
                ("active", self.colors["text_primary"]),
            ],
        )
        # Add an underline indicator for selected tab using layout element padding
        # Hide notebook tab headers (we navigate via sidebar)
        try:
            style.layout("TNotebook.Tab", [])
        except Exception:
            pass

        # Configure Frame style
        style.configure("TFrame", background=self.colors["background"])

        # Configure Combobox style for dark theme
        style.configure(
            "TCombobox",
            fieldbackground=self.colors["surface"],
            background=self.colors["surface"],
            foreground=self.colors["text_primary"],
            borderwidth=1,
            relief="flat",
            padding=[8, 6],
        )

        # Chip-like compact combobox
        style.configure(
            "Chip.TCombobox",
            fieldbackground=self.colors["surface_light"],
            background=self.colors["surface_light"],
            foreground=self.colors["text_primary"],
            borderwidth=1,
            relief="flat",
            padding=[10, 6],
        )

        style.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", self.colors["surface"]),
                ("focus", self.colors["surface_light"]),
            ],
            background=[("readonly", self.colors["surface"])],
            foreground=[("readonly", self.colors["text_primary"])],
            bordercolor=[("focus", self.colors["primary"])],
        )

        style.map(
            "Chip.TCombobox",
            fieldbackground=[
                ("readonly", self.colors["surface_light"]),
                ("focus", self.colors["surface"]),
            ],
            background=[("readonly", self.colors["surface_light"])],
            foreground=[("readonly", self.colors["text_primary"])],
            bordercolor=[("focus", self.colors["primary"])],
        )

        # Configure Treeview style for dark theme
        style.configure(
            "Treeview",
            background=self.colors["surface"],
            foreground=self.colors["text_primary"],
            fieldbackground=self.colors["surface"],
            borderwidth=0,
            relief="flat",
        )

        style.configure(
            "Treeview.Heading",
            background=self.colors["surface_dark"],
            foreground=self.colors["text_primary"],
            borderwidth=1,
            relief="flat",
        )

        style.map(
            "Treeview",
            background=[("selected", self.colors["primary"])],
            foreground=[("selected", self.colors["text_primary"])],
        )

        style.map(
            "Treeview.Heading", background=[("active", self.colors["surface_light"])]
        )

        # Sidebar button style to avoid macOS Aqua overrides
        style.configure(
            "Sidebar.TButton",
            background=self.colors["surface_light"],
            foreground=self.colors["text_primary"],
            borderwidth=0,
            relief="flat",
            padding=[10, 6],
            focuscolor="none",
        )
        style.map(
            "Sidebar.TButton",
            background=[
                ("active", self.colors["surface_light"]),
                ("pressed", self.colors["surface_light"]),
                ("focus", self.colors["surface_light"]),
                ("!disabled", self.colors["surface_light"]),
            ],
            foreground=[
                ("active", self.colors["text_primary"]),
                ("pressed", self.colors["text_primary"]),
                ("disabled", self.colors["text_secondary"]),
            ],
            relief=[("pressed", "flat")],
        )

        # Header icon buttons (Run/Stop/Clear)
        style.configure(
            "HeaderIcon.TButton",
            background=self.colors["surface_dark"],
            foreground=self.colors["text_primary"],
            borderwidth=0,
            relief="flat",
            padding=[4, 4],
            focuscolor="none",
        )
        style.map(
            "HeaderIcon.TButton",
            background=[
                ("active", self.colors["surface_dark"]),
                ("pressed", self.colors["surface_dark"]),
                ("focus", self.colors["surface_dark"]),
            ],
            foreground=[("active", self.colors["text_primary"])],
            relief=[("pressed", "flat")],
        )

        # Generic action styles
        style.configure(
            "Primary.TButton",
            background=self.colors["primary"],
            foreground=self.contrast_on(self.colors["primary"]),
            borderwidth=0,
            relief="flat",
            padding=[10, 6],
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", self.colors["primary"]),
                ("pressed", self.colors["primary"]),
            ],
            foreground=[("active", self.contrast_on(self.colors["primary"]))],
        )

        style.configure(
            "Secondary.TButton",
            background=self.colors["secondary"],
            foreground=self.contrast_on(self.colors["secondary"]),
            borderwidth=0,
            relief="flat",
            padding=[10, 6],
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("active", self.colors["secondary"]),
                ("pressed", self.colors["secondary"]),
            ],
            foreground=[("active", self.contrast_on(self.colors["secondary"]))],
        )

        style.configure(
            "Surface.TButton",
            background=self.colors["surface_light"],
            foreground=self.colors["text_primary"],
            borderwidth=0,
            relief="flat",
            padding=[10, 6],
        )
        style.map(
            "Surface.TButton",
            background=[
                ("active", self.colors["surface_light"]),
                ("pressed", self.colors["surface_light"]),
            ],
            foreground=[("active", self.colors["text_primary"])],
        )

    def load_icons(self):
        """Load and resize icons from assets folder"""
        try:
            icon_size = (24, 24)  # 24x24 pixels

            # Load play icon
            play_img = Image.open("assets/play-icon.png")
            play_img = play_img.resize(icon_size, Image.Resampling.LANCZOS)
            self.play_icon = ImageTk.PhotoImage(play_img)

            # Load stop icon
            stop_img = Image.open("assets/stop-icon.png")
            stop_img = stop_img.resize(icon_size, Image.Resampling.LANCZOS)
            self.stop_icon = ImageTk.PhotoImage(stop_img)

            # Load delete icon
            delete_img = Image.open("assets/delete-icon.png")
            delete_img = delete_img.resize(icon_size, Image.Resampling.LANCZOS)
            self.delete_icon = ImageTk.PhotoImage(delete_img)

        except Exception as e:
            print(f"Error loading icons: {e}")
            # Fallback to text icons if image loading fails
            self.play_icon = None
            self.stop_icon = None
            self.delete_icon = None

    def setup_ui(self):
        """Setup main UI components with dark theme"""
        # Create main container with dark theme
        main_frame = tk.Frame(self.root, bg=self.colors["background"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Header with modern dark-slate styling
        header_frame = tk.Frame(main_frame, bg=self.colors["surface_dark"], height=72)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        # Title
        title_label = tk.Label(
            header_frame,
            text="Gamma",
            font=(self.fonts["default"], 18, "bold"),
            bg=self.colors["surface_dark"],
            fg=self.colors["text_primary"],
        )
        title_label.pack(side=tk.LEFT, padx=self.spacing["lg"], pady=self.spacing["md"])

        # Control panel - compact horizontal layout
        control_frame = tk.Frame(header_frame, bg=self.colors["surface_dark"])
        control_frame.pack(
            side=tk.LEFT, padx=self.spacing["md"], pady=self.spacing["sm"], expand=True
        )

        # Project selection
        project_frame = tk.Frame(control_frame, bg=self.colors["surface"])
        project_frame.pack(side="left", padx=(0, self.spacing["md"]))

        tk.Label(
            project_frame,
            text="Project:",
            bg=self.colors["surface"],
            fg=self.colors["text_primary"],
            font=(DEFAULT_FONT, 10),
        ).pack(side="left")
        # Default to first discovered project if available
        default_project = (
            self.prefs.get("project")
            if self.prefs.get("project") in self.projects
            else next(iter(self.projects.keys()), "")
        )
        self.project_var = tk.StringVar(value=default_project)
        self.project_combo = ttk.Combobox(
            project_frame,
            textvariable=self.project_var,
            values=list(self.projects.keys()),
            state="readonly",
            width=12,
            font=(DEFAULT_FONT, 10),
            style="Chip.TCombobox",
        )
        self.project_combo.pack(side="left", padx=(self.spacing["sm"], 0))
        self.project_combo.bind(
            "<<ComboboxSelected>>", lambda e: self.on_project_change()
        )

        # Flow selection (populated by project)
        flow_frame = tk.Frame(control_frame, bg=self.colors["surface"])
        flow_frame.pack(side="left", padx=(0, self.spacing["md"]))
        tk.Label(
            flow_frame,
            text="Flow:",
            bg=self.colors["surface"],
            fg=self.colors["text_primary"],
            font=(DEFAULT_FONT, 10),
        ).pack(side="left")
        self.flow_var = tk.StringVar()
        self.flow_combo = ttk.Combobox(
            flow_frame,
            textvariable=self.flow_var,
            values=[],
            state="readonly",
            width=22,
            font=(DEFAULT_FONT, 10),
            style="Chip.TCombobox",
        )
        self.flow_combo.pack(side="left", padx=(self.spacing["sm"], 0))
        self.flow_combo.bind("<<ComboboxSelected>>", lambda e: self._save_prefs())
        # Internal map: project -> {label: full_path}
        self.flow_map = {}
        # Initialize flow list for default project (if any)
        if default_project:
            self.refresh_flows_for_project(default_project)

        # Mode selection
        mode_frame = tk.Frame(control_frame, bg=self.colors["surface_dark"])
        mode_frame.pack(side=tk.LEFT, padx=(0, self.spacing["md"]))

        self.mode_var = tk.StringVar(value=self.prefs.get("mode", "headless"))
        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=["headless", "normal"],
            state="readonly",
            width=10,
            font=(self.fonts["default"], 11),
            style="Chip.TCombobox",
        )
        mode_combo.pack()
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._save_prefs())

        # Control buttons with icons only - no borders or backgrounds
        button_frame = tk.Frame(header_frame, bg=self.colors["surface_dark"])
        button_frame.pack(
            side=tk.RIGHT, padx=self.spacing["lg"], pady=self.spacing["md"]
        )

        # Theme selector removed (single dark theme)

        # Run button - borderless icon only
        if self.play_icon:
            self.run_button = ttk.Button(
                button_frame,
                image=self.play_icon,
                command=self.start_test,
                style="HeaderIcon.TButton",
                cursor="hand2",
            )
            self.run_button.tooltip = tk.Label(
                button_frame,
                text="Run test",
                bg=self.colors["surface_light"],
                fg=self.colors["text_primary"],
                bd=0,
            )
        else:
            self.run_button = ttk.Button(
                button_frame,
                text="▶",
                command=self.start_test,
                style="HeaderIcon.TButton",
                cursor="hand2",
            )

        self.run_button.pack(side=tk.LEFT, padx=self.spacing["sm"])
        # Simple tooltip bindings
        try:
            self.run_button.bind(
                "<Enter>", lambda e: self._show_tooltip(self.run_button, "Run test")
            )
            self.run_button.bind("<Leave>", lambda e: self._hide_tooltip())
        except Exception:
            pass

        # Stop button - borderless icon only
        if self.stop_icon:
            self.stop_button = ttk.Button(
                button_frame,
                image=self.stop_icon,
                command=self.stop_test,
                style="HeaderIcon.TButton",
                cursor="hand2",
            )
            self.stop_button.tooltip = tk.Label(
                button_frame,
                text="Stop test",
                bg=self.colors["surface_light"],
                fg=self.colors["text_primary"],
                bd=0,
            )
        else:
            self.stop_button = ttk.Button(
                button_frame,
                text="⏹",
                command=self.stop_test,
                style="HeaderIcon.TButton",
                cursor="hand2",
            )

        self.stop_button.pack(side=tk.LEFT, padx=self.spacing["sm"])
        try:
            self.stop_button.bind(
                "<Enter>", lambda e: self._show_tooltip(self.stop_button, "Stop test")
            )
            self.stop_button.bind("<Leave>", lambda e: self._hide_tooltip())
        except Exception:
            pass

        # Clear button - borderless icon only
        if self.delete_icon:
            self.clear_button = ttk.Button(
                button_frame,
                image=self.delete_icon,
                command=self.clear_logs,
                style="HeaderIcon.TButton",
                cursor="hand2",
            )
        else:
            self.clear_button = ttk.Button(
                button_frame,
                text="🗑",
                command=self.clear_logs,
                style="HeaderIcon.TButton",
                cursor="hand2",
            )

        self.clear_button.pack(side=tk.LEFT, padx=self.spacing["sm"])

        # Status indicator on the right
        status_frame = tk.Frame(header_frame, bg=self.colors["surface_dark"])
        status_frame.pack(
            side=tk.RIGHT, padx=self.spacing["lg"], pady=self.spacing["md"]
        )

        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            font=(self.fonts["default"], 14, "bold"),
            bg=self.colors["surface_dark"],
            fg=self.colors["success"],
        )
        self.status_label.pack()

        # Subtle divider under header for visual hierarchy
        divider = tk.Frame(main_frame, bg=self.colors["border"], height=1)
        divider.pack(fill=tk.X)

        # Create notebook for tabs - no borders
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    def setup_logs_tab(self):
        return None

    def setup_results_tab(self):
        return None

    def setup_history_tab(self):
        return None

    def update_button_states(self):
        """Update button states based on test status and selection availability"""
        # If buttons are not yet created (early init), skip
        if not hasattr(self, "start_button") or not hasattr(self, "stop_button"):
            return
        has_flow = hasattr(self, "flow_var") and bool(self.flow_var.get())
        if self.test_running:
            self.run_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.status_label.config(text="Running", fg=self.colors["warning"])
        else:
            self.run_button.config(state=("normal" if has_flow else "disabled"))
            self.stop_button.config(state="disabled")
            self.status_label.config(text="Ready", fg=self.colors["success"])

    def start_test(self):
        """Start the test execution"""
        start_test(self)

    def run_test_process(self):
        """Run the actual test process with proper artifact saving"""
        run_test_process(self)

    def create_test_summary(self, status, error_message=None, project_name=None):
        """Create a test summary file with proper artifacts"""
        create_test_summary(self, status, error_message, project_name)

    def calculate_test_duration(self, log_content, log_dir=None):
        """Calculate test duration from summary.json or log timestamps"""
        return calculate_test_duration(log_content, log_dir)

    def add_log(self, message, tag="info"):
        """Add a log message to the logs text widget"""
        add_log(self, message, tag)

    def stop_test(self):
        """Stop the running test"""
        stop_test(self)

    def clear_logs(self):
        """Clear the logs text widget"""
        clear_logs(self)

    def consume_logs(self):
        """Process log queue in main thread"""
        # Stop if window is closed or test is not running
        if not hasattr(self, "root") or not self.root.winfo_exists():
            return

        try:
            processed_count = 0
            # Only process if test is running or queue has items
            while processed_count < 20:  # Reduced limit
                try:
                    log_entry = self.log_queue.get_nowait()
                    message = log_entry["message"]
                    tag = log_entry.get("tag", "info")

                    # Stop if we see the "Test execution finished" message
                    if "Test execution finished" in message:
                        # Clear the queue and stop processing
                        while not self.log_queue.empty():
                            try:
                                self.log_queue.get_nowait()
                            except:
                                break
                        return

                    timestamp = datetime.now().strftime("%H:%M:%S")
                    formatted_message = f"[{timestamp}] {message}\n"

                    if hasattr(self, "logs_text") and self.logs_text.winfo_exists():
                        self.logs_text.insert(tk.END, formatted_message, tag)
                        if (
                            hasattr(self, "auto_scroll_var")
                            and self.auto_scroll_var.get()
                        ):
                            self.logs_text.see(tk.END)

                    processed_count += 1

                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error in consume_logs: {e}")

        # Only schedule next check if test is running or queue might have items
        if (
            hasattr(self, "root")
            and self.root.winfo_exists()
            and (self.test_running or not self.log_queue.empty())
        ):
            self.root.after(500, self.consume_logs)  # Increased to 500ms

    def load_test_history(self):
        """Load test execution history"""
        load_test_history(self)

    def refresh_results(self):
        """Refresh the results view"""
        refresh_results(self)

    def open_logs_folder(self):
        """Open the logs folder in file explorer"""
        open_logs_folder(self)

    def view_selected_artifact(self):
        """View the selected artifact file"""
        view_selected_artifact(self)

    def auto_refresh_all_tabs(self):
        """Automatically refresh both results and history tabs"""
        auto_refresh_all_tabs(self)

    def show_full_history_details(self, event):
        """Show full details for selected history item in a popup"""
        selection = self.history_tree.selection()
        if not selection:
            return

        # Get the selected item
        item = self.history_tree.item(selection[0])
        values = item["values"]

        if len(values) >= 7:
            date, time, project, mode, status, duration, details = values

            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title(f"Test Details - {date} {time}")
            popup.geometry("800x600")
            popup.configure(bg=self.colors["background"])

            # Header
            header_frame = tk.Frame(popup, bg=self.colors["surface"])
            header_frame.pack(fill="x", padx=10, pady=10)

            tk.Label(
                header_frame,
                text=f"Test Execution Details",
                font=(self.fonts["default"], 16, "bold"),
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
            ).pack()

            # Info frame
            info_frame = tk.Frame(popup, bg=self.colors["background"])
            info_frame.pack(fill="x", padx=10, pady=5)

            # Basic info
            info_text = f"""
📅 Date: {date}
⏰ Time: {time}
                🎯 Project: {project}
🖥️ Mode: {mode}
📊 Status: {status}
⏱️ Duration: {duration}
            """

            tk.Label(
                info_frame,
                text=info_text,
                font=(self.fonts["default"], 12),
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
                justify="left",
            ).pack(anchor="w")

            # Details frame
            details_frame = tk.Frame(popup, bg=self.colors["background"])
            details_frame.pack(fill="both", expand=True, padx=10, pady=5)

            tk.Label(
                details_frame,
                text="Full Details:",
                font=(self.fonts["default"], 12, "bold"),
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            ).pack(anchor="w")

            # Details text area
            details_text = scrolledtext.ScrolledText(
                details_frame,
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
                font=(self.fonts["mono"], 10),
                wrap=tk.WORD,
            )
            details_text.pack(fill="both", expand=True)
            details_text.insert(tk.END, details)

            # Try to load additional details from files
            try:
                # Find the test directory
                logs_dir = "logs"
                if os.path.exists(logs_dir):
                    test_dirs = [
                        d
                        for d in os.listdir(logs_dir)
                        if os.path.isdir(os.path.join(logs_dir, d)) and "checkout" in d
                    ]

                    # Find matching test directory
                    for test_dir in test_dirs:
                        if (
                            date.replace("-", "") in test_dir
                            and time.replace(":", "") in test_dir
                        ):
                            test_path = os.path.join(logs_dir, test_dir)

                            # Load error details if available
                            error_file = os.path.join(test_path, "error_details.txt")
                            if os.path.exists(error_file):
                                with open(error_file, "r") as f:
                                    error_content = f.read()
                                details_text.insert(tk.END, "\n\n" + "=" * 60 + "\n")
                                details_text.insert(
                                    tk.END, "ERROR DETAILS FROM FILE:\n"
                                )
                                details_text.insert(tk.END, "=" * 60 + "\n")
                                details_text.insert(tk.END, error_content)

                            # Load test log if available
                            log_file = os.path.join(test_path, "test_log.txt")
                            if os.path.exists(log_file):
                                with open(log_file, "r") as f:
                                    log_content = f.read()
                                details_text.insert(tk.END, "\n\n" + "=" * 60 + "\n")
                                details_text.insert(tk.END, "FULL TEST LOG:\n")
                                details_text.insert(tk.END, "=" * 60 + "\n")
                                details_text.insert(tk.END, log_content)
                            break
            except Exception as e:
                details_text.insert(
                    tk.END, f"\n\n❌ Error loading additional details: {str(e)}"
                )

            # Close button
            close_btn = ttk.Button(
                popup,
                text="Close",
                command=popup.destroy,
                style="Primary.TButton",
                cursor="hand2",
            )
            close_btn.pack(pady=10)

    def clear_logs(self):
        self.logs_text.delete(1.0, tk.END)
        if hasattr(self, "summary_text"):
            self.summary_text.delete(1.0, tk.END)
        if hasattr(self, "artifacts_listbox"):
            self.artifacts_listbox.delete(0, tk.END)

        # Add a subtle message
        self.logs_text.insert(tk.END, "Logs cleared. Ready for new test...\n", "info")

    def consume_logs(self):
        try:
            while True:
                try:
                    log_entry = self.log_queue.get_nowait()

                    # Handle both old string format and new dict format
                    if isinstance(log_entry, dict):
                        message = log_entry["message"]
                        tag = log_entry.get("tag", "info")
                    else:
                        message = log_entry
                        # Auto-detect tag based on content
                        if "✅" in message or "success" in message.lower():
                            tag = "success"
                        elif (
                            "❌" in message
                            or "error" in message.lower()
                            or "fail" in message.lower()
                        ):
                            tag = "error"
                        elif "⚠️" in message or "warning" in message.lower():
                            tag = "warning"
                        elif message.startswith("📅"):
                            tag = "timestamp"
                        else:
                            tag = "info"

                    # Insert with appropriate tag
                    self.logs_text.insert(tk.END, message + "\n", tag)

                    # Auto-scroll if enabled
                    if hasattr(self, "auto_scroll_var") and self.auto_scroll_var.get():
                        self.logs_text.see(tk.END)

                except queue.Empty:
                    break

            # Update UI if test finished
            if (
                not self.test_running
                and hasattr(self, "test_process")
                and self.test_process
                and self.test_process.poll() is not None
            ):
                self.test_finished()

        except Exception as e:
            pass
        finally:
            self.root.after(100, self.consume_logs)

    def open_logs_folder(self):
        open_logs_folder(self)

    def refresh_results(self):
        """Load and display latest test results with proper artifacts"""
        refresh_results_detailed(self)

    def view_selected_artifact_button(self):
        """View the selected artifact file (button handler)."""
        view_selected_artifact_button(self)

    def open_text_artifact_internally(self, file_path, title):
        """Metin tabanlı artifact'leri uygulama içinde yeni bir pencerede açar."""
        open_text_artifact_internally(self, file_path, title)

    def open_file_externally(self, file_path):
        """Artifact'i sistemin varsayılan uygulamasıyla harici olarak açar."""
        open_file_externally(self, file_path)

    def format_test_summary(self, summary):
        """Format test summary for display"""
        return format_test_summary(summary)

    def load_test_history(self):
        """Load test execution history"""
        load_test_history(self)

    def load_history_data(self):
        """Load test history data from logs directory with detailed information"""
        load_history_data(self)

    def clear_all_logs(self):
        """Delete all files and folders under the logs directory and refresh UI."""
        clear_all_logs(self)

    def consume_test_logs(self):
        """Consume test output in a separate thread"""
        consume_test_logs(self)

    def setup_builder_tab(self):
        return None

    def _normalize_project_folder(self, name: str) -> str:
        return _normalize_project_folder(name)

    def refresh_all_project_combos(self, select_project: str | None = None):
        refresh_all_project_combos(self, select_project)

    def builder_create_new_project(self):
        builder_create_new_project(self)

    def builder_add_step(self):
        builder_add_step(self)

    def builder_remove_selected(self):
        builder_remove_selected(self)

    def builder_save_flow(self):
        builder_save_flow(self)

    def _shorten_selector_for_name(self, selector: str) -> str:
        """Create a readable short label from a CSS selector without leaving dangling characters."""
        return _shorten_selector_for_name(selector)

    def builder_on_action_change(self):
        builder_on_action_change(self)


def main():
    root = tk.Tk()
    app = TestRunnerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
