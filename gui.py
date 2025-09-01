import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
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
from PIL import Image, ImageTk
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
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # Discover projects dynamically from filesystem (generic)
        self.projects = self.discover_projects()

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

        # Setup UI
        self.setup_ui()
        self.setup_logs_tab()
        self.setup_results_tab()
        self.setup_history_tab()
        self.setup_builder_tab()

        # Apply initial button states
        self.update_button_states()

        # Start log consumer
        self.consume_logs()

        # Load test history
        self.load_test_history()

    def _hex_to_rgb(self, hex_color: str):
        try:
            hex_color = hex_color.lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join([c * 2 for c in hex_color])
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        except Exception:
            return (0, 0, 0)

    def _relative_luminance(self, hex_color: str) -> float:
        r, g, b = self._hex_to_rgb(hex_color)

        def _to_linear(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        rl = 0.2126 * _to_linear(r) + 0.7152 * _to_linear(g) + 0.0722 * _to_linear(b)
        return rl

    def contrast_on(self, bg_hex: str) -> str:
        """Return black or white depending on background for readable text."""
        try:
            lum = self._relative_luminance(bg_hex)
            # Threshold chosen for decent legibility across themes
            return "#000000" if lum > 0.5 else "#ffffff"
        except Exception:
            return self.colors.get("text_primary", "#ffffff")

    def load_theme_config(self):
        """Load theme configuration from JSON file"""
        try:
            with open("config/theme_config.json", "r") as f:
                config = json.load(f)
                self.colors = config["colors"]
                self.spacing = config["spacing"]
                self.fonts = config["fonts"]
        except Exception as e:
            print(f"Error loading theme config: {e}")
            # Fallback to default Dracula colors
            self.colors = {
                "background": "#282a36",
                "surface": "#44475a",
                "surface_light": "#6272a4",
                "surface_dark": "#21222c",
                "primary": "#bd93f9",
                "secondary": "#8be9fd",
                "accent": "#ffb86c",
                "success": "#50fa7b",
                "warning": "#f1fa8c",
                "danger": "#ff5555",
                "text_primary": "#f8f8f2",
                "text_secondary": "#6272a4",
                "text_muted": "#44475a",
                "border": "#6272a4",
                "selection": "#44475a",
            }
            self.spacing = {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32}
            self.fonts = {"default": "Arial", "mono": "Monaco"}

    def on_project_change(self):
        """Handle project selection change"""
        project_name = self.project_var.get()
        if project_name in self.projects:
            project_config = self.projects[project_name]
            self.add_log(f"🔄 Switched to project: {project_config['name']}", "info")
            # Refresh available flows for this project
            try:
                self.refresh_flows_for_project(project_name)
            except Exception as e:
                self.add_log(f"Failed to refresh flows: {e}", "error")
        else:
            self.add_log(f"⚠️ Unknown project: {project_name}", "warning")

    def discover_projects(self):
        """Scan tests/projects/* for project folders and return config dict (generic)."""
        projects_root = os.path.join("tests", "projects")
        discovered = {}
        if os.path.isdir(projects_root):
            for entry in sorted(os.listdir(projects_root)):
                project_dir = os.path.join(projects_root, entry)
                if not os.path.isdir(project_dir):
                    continue
                # Build env var keys from folder name (normalize to A-Z_)
                env_prefix = entry.upper().replace("-", "_").replace(" ", "_")
                env_vars = {
                    f"{env_prefix}_EMAIL": os.getenv(f"{env_prefix}_EMAIL", ""),
                    f"{env_prefix}_PASSWORD": os.getenv(f"{env_prefix}_PASSWORD", ""),
                    f"{env_prefix}_USER_AGENT": os.getenv(
                        f"{env_prefix}_USER_AGENT",
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    ),
                }
                # Default script: first .py file if exists
                default_script = None
                for fn in sorted(os.listdir(project_dir)):
                    if fn.endswith(".py") and fn != "__init__.py":
                        default_script = os.path.join(project_dir, fn)
                        break
                discovered[entry.upper()] = {
                    "name": entry.upper(),
                    "script": default_script or "",
                    "dir": project_dir,
                    "env_vars": env_vars,
                }
        return discovered

    def refresh_flows_for_project(self, project_name: str):
        """Populate flow combobox with python files under the project's directory"""
        project_cfg = self.projects.get(project_name)
        if not project_cfg:
            return
        flow_dir = project_cfg.get("dir")
        flows = []
        label_to_path = {}
        if flow_dir and os.path.isdir(flow_dir):
            for fn in sorted(os.listdir(flow_dir)):
                # Support Python tests and JSON test definitions
                if (fn.endswith(".py") or fn.endswith(".json")) and fn != "__init__.py":
                    label = os.path.splitext(fn)[0]
                    full_path = os.path.join(flow_dir, fn)
                    flows.append(label)
                    label_to_path[label] = full_path
        if hasattr(self, "flow_combo"):
            self.flow_combo["values"] = flows
            current = getattr(self, "flow_var", tk.StringVar()).get()
            if current in flows:
                self.flow_combo.set(current)
            elif flows:
                self.flow_combo.set(flows[0])
        # Save map for run resolution
        self.flow_map[project_name] = label_to_path

    def update_button_states(self):
        """Update button appearance based on current state"""
        if not self.test_running:
            # Start button enabled
            self.start_button.config(
                state="normal",
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

        except Exception as e:
            print(f"Error loading icons: {e}")
            # Fallback to None if icons not found
            self.play_icon = None
            self.stop_icon = None
            self.delete_icon = None

    def setup_styles(self):
        """Configure modern styling"""
        # Configure ttk styles
        style = ttk.Style()
        style.theme_use("clam")

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
            padding=[20, 10],
            borderwidth=0,
            focuscolor="none",
        )

        style.map(
            "TNotebook.Tab",
            background=[
                ("selected", self.colors["primary"]),
                ("active", self.colors["surface_light"]),
            ],
            foreground=[
                ("selected", self.colors["text_primary"]),
                ("active", self.colors["text_primary"]),
            ],
        )

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

        # Header with dark styling - no borders
        header_frame = tk.Frame(main_frame, bg=self.colors["surface_dark"], height=80)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        # Title
        title_label = tk.Label(
            header_frame,
                            text="Gamma",
            font=(self.fonts["default"], 20, "bold"),
            bg=self.colors["surface_dark"],
            fg=self.colors["text_primary"],
        )
        title_label.pack(side=tk.LEFT, padx=self.spacing["lg"], pady=self.spacing["lg"])

        # Control panel - compact settings
        control_frame = tk.Frame(header_frame, bg=self.colors["surface_dark"])
        control_frame.pack(
            side=tk.LEFT, padx=self.spacing["lg"], pady=self.spacing["md"], expand=True
        )

        # Project selection
        project_frame = tk.Frame(control_frame, bg=self.colors["surface"])
        project_frame.pack(side="left", padx=self.spacing["md"])

        tk.Label(
            project_frame,
            text="Project:",
            bg=self.colors["surface"],
            fg=self.colors["text_primary"],
            font=(DEFAULT_FONT, 10),
        ).pack(side="left")
        # Default to first discovered project if available
        default_project = next(iter(self.projects.keys()), "PROJECT")
        self.project_var = tk.StringVar(value=default_project)
        project_combo = ttk.Combobox(
            project_frame,
            textvariable=self.project_var,
            values=list(self.projects.keys()),
            state="readonly",
            width=12,
            font=(DEFAULT_FONT, 10),
        )
        project_combo.pack(side="left", padx=(self.spacing["sm"], 0))
        project_combo.bind("<<ComboboxSelected>>", lambda e: self.on_project_change())

        # Flow selection (populated by project)
        flow_frame = tk.Frame(control_frame, bg=self.colors["surface"])
        flow_frame.pack(side="left", padx=self.spacing["md"])
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
        )
        self.flow_combo.pack(side="left", padx=(self.spacing["sm"], 0))
        # Internal map: project -> {label: full_path}
        self.flow_map = {}
        self.refresh_flows_for_project(self.project_var.get())

        # Mode selection
        mode_frame = tk.Frame(control_frame, bg=self.colors["surface_dark"])
        mode_frame.pack(side=tk.LEFT, padx=self.spacing["md"])

        self.mode_var = tk.StringVar(value="headless")
        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=["headless", "normal"],
            state="readonly",
            width=10,
            font=(self.fonts["default"], 11),
        )
        mode_combo.pack()

        # Control buttons with icons only - no borders or backgrounds
        button_frame = tk.Frame(header_frame, bg=self.colors["surface_dark"])
        button_frame.pack(
            side=tk.RIGHT, padx=self.spacing["lg"], pady=self.spacing["md"]
        )

        # Run button - borderless icon only
        if self.play_icon:
            self.run_button = tk.Button(
                button_frame,
                image=self.play_icon,
                command=self.start_test,
                bg=self.colors["surface_dark"],
                fg=self.colors["text_primary"],
                bd=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                activebackground=self.colors["surface_dark"],
            )
        else:
            self.run_button = tk.Button(
                button_frame,
                text="▶",
                command=self.start_test,
                font=(self.fonts["default"], 18),
                bg=self.colors["surface_dark"],
                fg=self.colors["success"],
                bd=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                activebackground=self.colors["surface_dark"],
            )

        self.run_button.pack(side=tk.LEFT, padx=self.spacing["sm"])

        # Stop button - borderless icon only
        if self.stop_icon:
            self.stop_button = tk.Button(
                button_frame,
                image=self.stop_icon,
                command=self.stop_test,
                bg=self.colors["surface_dark"],
                fg=self.colors["text_primary"],
                bd=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                activebackground=self.colors["surface_dark"],
            )
        else:
            self.stop_button = tk.Button(
                button_frame,
                text="⏹",
                command=self.stop_test,
                font=(self.fonts["default"], 18),
                bg=self.colors["surface_dark"],
                fg=self.colors["warning"],
                bd=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                activebackground=self.colors["surface_dark"],
            )

        self.stop_button.pack(side=tk.LEFT, padx=self.spacing["sm"])

        # Clear button - borderless icon only
        if self.delete_icon:
            self.clear_button = tk.Button(
                button_frame,
                image=self.delete_icon,
                command=self.clear_logs,
                bg=self.colors["surface_dark"],
                fg=self.colors["text_primary"],
                bd=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                activebackground=self.colors["surface_dark"],
            )
        else:
            self.clear_button = tk.Button(
                button_frame,
                text="🗑",
                command=self.clear_logs,
                font=(self.fonts["default"], 18),
                bg=self.colors["surface_dark"],
                fg=self.colors["danger"],
                bd=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                activebackground=self.colors["surface_dark"],
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

        # Create notebook for tabs - no borders
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    def setup_logs_tab(self):
        """Create dark-themed logs tab"""
        logs_frame = tk.Frame(self.notebook, bg=self.colors["background"])
        self.notebook.add(logs_frame, text="Logs")

        # Logs container
        logs_container = tk.Frame(logs_frame, bg=self.colors["background"])
        logs_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Logs text area with dark terminal styling
        self.logs_text = scrolledtext.ScrolledText(
            logs_container,
            bg=self.colors["surface_dark"],
            fg=self.colors["text_primary"],
            font=(self.fonts["mono"], 11),
            insertbackground=self.colors["primary"],
            selectbackground=self.colors["selection"],
            relief="flat",
            bd=0,
            padx=15,
            pady=15,
            wrap=tk.WORD,
        )
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Configure text tags for colored output
        self.logs_text.tag_configure("info", foreground=self.colors["secondary"])
        self.logs_text.tag_configure("success", foreground=self.colors["success"])
        self.logs_text.tag_configure("warning", foreground=self.colors["warning"])
        self.logs_text.tag_configure("error", foreground=self.colors["danger"])
        self.logs_text.tag_configure(
            "timestamp", foreground=self.colors["text_secondary"]
        )

    def setup_results_tab(self):
        """Create functional results tab with test summary and artifacts"""
        results_frame = tk.Frame(self.notebook, bg=self.colors["background"])
        self.notebook.add(results_frame, text="Results")

        # Results content
        results_content = tk.Frame(results_frame, bg=self.colors["background"])
        results_content.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Results header
        header_frame = tk.Frame(results_content, bg=self.colors["surface"])
        header_frame.pack(fill=tk.X, padx=self.spacing["md"], pady=self.spacing["md"])

        tk.Label(
            header_frame,
            text="Test Results & Artifacts",
            font=(self.fonts["default"], 14, "bold"),
            bg=self.colors["surface"],
            fg=self.colors["text_primary"],
        ).pack(side=tk.LEFT)

        # Refresh button
        refresh_btn = tk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self.refresh_results,
            font=(self.fonts["default"], 10),
            bg=self.colors["primary"],
            fg=self.contrast_on(self.colors["primary"]),
            bd=0,
            relief="flat",
            cursor="hand2",
        )
        refresh_btn.pack(side=tk.RIGHT)

        # Split view: Summary on left, Artifacts on right
        content_frame = tk.Frame(results_content, bg=self.colors["background"])
        content_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=self.spacing["md"],
            pady=(0, self.spacing["md"]),
        )

        # Left side - Test Summary
        left_frame = tk.Frame(content_frame, bg=self.colors["background"])
        left_frame.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, self.spacing["sm"])
        )

        tk.Label(
            left_frame,
            text="Test Summary",
            font=(self.fonts["default"], 12, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text_primary"],
        ).pack(anchor=tk.W, pady=(0, self.spacing["sm"]))

        self.summary_text = scrolledtext.ScrolledText(
            left_frame,
            bg=self.colors["surface"],
            fg=self.colors["text_primary"],
            font=(self.fonts["mono"], 10),
            insertbackground=self.colors["primary"],
            selectbackground=self.colors["selection"],
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
            wrap=tk.WORD,
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)

        # Right side - Artifacts
        right_frame = tk.Frame(content_frame, bg=self.colors["background"])
        right_frame.pack(
            side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(self.spacing["sm"], 0)
        )

        tk.Label(
            right_frame,
            text="Test Artifacts",
            font=(self.fonts["default"], 12, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text_primary"],
        ).pack(anchor=tk.W, pady=(0, self.spacing["sm"]))

        # Artifacts listbox
        self.artifacts_listbox = tk.Listbox(
            right_frame,
            bg=self.colors["surface"],
            fg=self.colors["text_primary"],
            font=(self.fonts["mono"], 10),
            selectbackground=self.colors["primary"],
            relief="flat",
            bd=0,
        )
        self.artifacts_listbox.pack(fill=tk.BOTH, expand=True, padx=(0, 10))

        # Artifacts listbox'a çift tıklama event'ini bağla
        self.artifacts_listbox.bind(
            "<Double-1>", lambda e: self.view_selected_artifact_button()
        )

        # Artifacts buttons
        artifact_buttons = tk.Frame(right_frame, bg=self.colors["background"])
        artifact_buttons.pack(fill=tk.X, pady=(self.spacing["sm"], 0))

        tk.Button(
            artifact_buttons,
            text="📁 Open Folder",
            command=self.open_logs_folder,
            font=(self.fonts["default"], 9),
            bg=self.colors["secondary"],
            fg=self.contrast_on(self.colors["secondary"]),
            bd=0,
            relief="flat",
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(
            artifact_buttons,
            text="👁️ View Selected",
            command=self.view_selected_artifact_button,
            font=(self.fonts["default"], 9),
            bg=self.colors["secondary"],
            fg=self.contrast_on(self.colors["secondary"]),
            bd=0,
            relief="flat",
            cursor="hand2",
        ).pack(side=tk.LEFT)

    def setup_history_tab(self):
        """Create dark-themed history tab with proper table"""
        history_frame = tk.Frame(self.notebook, bg=self.colors["background"])
        self.notebook.add(history_frame, text="History")

        # History content
        history_content = tk.Frame(history_frame, bg=self.colors["background"])
        history_content.pack(
            fill=tk.BOTH, expand=True, padx=self.spacing["md"], pady=self.spacing["md"]
        )

        # History header
        header_frame = tk.Frame(history_content, bg=self.colors["surface"])
        header_frame.pack(fill=tk.X, pady=(0, self.spacing["md"]))

        tk.Label(
            header_frame,
            text="Test Execution History",
            font=(self.fonts["default"], 14, "bold"),
            bg=self.colors["surface"],
            fg=self.colors["text_primary"],
        ).pack(side=tk.LEFT, padx=self.spacing["md"], pady=self.spacing["sm"])

        # Clear all logs button
        clear_logs_btn = tk.Button(
            header_frame,
            text="🧹 Clear All Logs",
            command=self.clear_all_logs,
            font=(self.fonts["default"], 10),
            bg=self.colors["secondary"],
            fg=self.contrast_on(self.colors["secondary"]),
            bd=0,
            relief="flat",
            cursor="hand2",
        )
        clear_logs_btn.pack(
            side=tk.RIGHT,
            padx=(self.spacing["sm"], self.spacing["md"]),
            pady=self.spacing["sm"],
        )

        # Load history button
        load_btn = tk.Button(
            header_frame,
            text=" Refresh",
            command=self.load_history_data,
            font=(self.fonts["default"], 10),
            bg=self.colors["primary"],
            fg=self.contrast_on(self.colors["primary"]),
            bd=0,
            relief="flat",
            cursor="hand2",
        )
        load_btn.pack(side=tk.RIGHT, padx=self.spacing["md"], pady=self.spacing["sm"])

        # Create Treeview for table display
        columns = ("Date", "Time", "Project", "Mode", "Status", "Duration", "Details")
        self.history_tree = ttk.Treeview(
            history_content, columns=columns, show="headings", height=15
        )

        # Configure column widths and headings - wider Details column
        column_widths = {
            "Date": 100,
            "Time": 80,
            "Project": 120,
            "Mode": 80,
            "Status": 80,
            "Duration": 80,
            "Details": 400,  # Much wider for full error details
        }

        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=column_widths[col], anchor="center")

        # Scrollbar for the table
        scrollbar = ttk.Scrollbar(
            history_content, orient="vertical", command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        # Pack the table and scrollbar
        self.history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind double-click to show full details
        self.history_tree.bind("<Double-1>", self.show_full_history_details)

    def update_button_states(self):
        """Update button states based on test status"""
        if self.test_running:
            self.run_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.status_label.config(text="Running", fg=self.colors["warning"])
        else:
            self.run_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.status_label.config(text="Ready", fg=self.colors["success"])

    def start_test(self):
        """Start the test execution"""
        if self.test_running:
            return

        self.test_running = True

        # Update button states
        self.update_button_states()

        # Clear logs
        self.logs_text.delete(1.0, tk.END)

        # Clear banner will be logged by the process itself

        # Start test in thread
        test_thread = threading.Thread(target=self.run_test_process, daemon=True)
        test_thread.start()

    def run_test_process(self):
        """Run the actual test process with proper artifact saving"""
        try:
            # Set environment variables
            env = os.environ.copy()
            env["HEADLESS"] = "1" if self.mode_var.get() == "headless" else "0"
            env["CONSOLE_MIN_LEVEL"] = "WARNING"

            # Get project and script details
            project_name = self.project_var.get()
            project_config = self.projects.get(project_name)

            if not project_config:
                self.add_log(
                    f"❌ Project '{project_name}' not found in configuration.", "error"
                )
                self.test_running = False
                self.update_button_states()
                return

            # Determine script: either selected flow file or default script
            selected_flow = self.flow_var.get() if hasattr(self, "flow_var") else ""
            script_path = project_config["script"]
            if selected_flow:
                # Resolve label to full path via flow_map
                script_path = self.flow_map.get(project_name, {}).get(
                    selected_flow, project_config["script"]
                )

            # Check if script exists
            if not os.path.exists(script_path):
                self.add_log(
                    f"❌ Test script '{script_path}' not found for project '{project_name}'.",
                    "error",
                )
                self.test_running = False
                self.update_button_states()
                return

            env["PROJECT"] = project_name  # Set the generic project for the test script
            # Ensure project root is on PYTHONPATH for 'tests' package imports
            try:
                project_root = os.path.abspath(os.path.dirname(__file__))
                existing_pp = env.get("PYTHONPATH", "")
                sep = ":" if os.name != "nt" else ";"
                env["PYTHONPATH"] = (
                    project_root
                    if not existing_pp
                    else f"{project_root}{sep}{existing_pp}"
                )
            except Exception:
                pass
            # Only set non-empty values from project_config to avoid overriding real envs with blanks
            for key, value in project_config["env_vars"].items():
                if isinstance(value, str) and value.strip() == "":
                    continue
                if value is None:
                    continue
                env[key] = value

            # Log test start
            # Single start log
            self.add_log(
                f"🚀 Starting {project_name} project test in {self.mode_var.get()} mode...",
                "info",
            )
            self.add_log(
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "timestamp"
            )
            self.add_log("-" * 50, "info")

            # Determine runner: json vs python
            cmd = ["python3", script_path]
            if script_path.endswith(".json"):
                cmd = ["python3", "tests/json_runner.py", script_path, project_name]

            # Run the test
            self.test_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Start log consumer thread
            self.log_thread = threading.Thread(
                target=self.consume_test_logs, daemon=True
            )
            self.log_thread.start()

        except Exception as e:
            self.add_log(f"❌ Error: {str(e)}", "error")
            self.test_running = False
            self.update_button_states()

    def create_test_summary(self, status, error_message=None, project_name=None):
        """Create a test summary file with proper artifacts"""
        try:
            # Prefer run dir printed by the test (RUN_DIR: ...)
            logs_text = self.logs_text.get(1.0, tk.END)
            log_dir = None
            for line in logs_text.split("\n"):
                if "RUN_DIR:" in line:
                    candidate = line.split("RUN_DIR:")[1].strip()
                    if os.path.isdir(candidate):
                        log_dir = candidate
                        break

            # Fallback to timestamped dir if RUN_DIR not found
            test_start_time = datetime.now()
            if not log_dir:
                timestamp = test_start_time.strftime("%Y%m%d-%H%M%S")
                log_dir = f"logs/{timestamp}-checkout"
                os.makedirs(log_dir, exist_ok=True)

            # Get logs from the text widget
            log_content = self.logs_text.get(1.0, tk.END).strip()

            # Calculate test duration from summary or logs
            duration = self.calculate_test_duration(log_content, log_dir)

            # Create summary data with error details
            summary = {
                "status": status,
                "project": project_name or self.project_var.get(),
                "mode": self.mode_var.get(),
                "headless": self.mode_var.get() == "headless",
                "durationSec": duration,
                "timestamp": test_start_time.isoformat(),
                "logLines": len(log_content.split("\n")) if log_content else 0,
                "error": error_message if error_message else None,
            }

            # Save summary.json
            summary_path = os.path.join(log_dir, "summary.json")
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)

            # Save raw logs
            log_path = os.path.join(log_dir, "test_log.txt")
            with open(log_path, "w") as f:
                f.write(log_content)

            # Save test artifacts if test failed
            if status == "failed" and error_message:
                # Create error details file
                error_path = os.path.join(log_dir, "error_details.txt")
                with open(error_path, "w") as f:
                    f.write(f"Test failed at: {test_start_time.isoformat()}\n")
                    f.write(f"Error: {error_message}\n")
                    f.write(f"Project: {project_name or self.project_var.get()}\n")
                    f.write(f"Mode: {self.mode_var.get()}\n")
                    f.write(f"Duration: {duration:.1f} seconds\n")
                    f.write("\nFull Log:\n")
                    f.write("-" * 50 + "\n")
                    f.write(log_content)

            self.add_log(f"📁 Test results saved to: {log_dir}", "info")

            # Auto-refresh both results and history tabs
            self.root.after(1000, self.auto_refresh_all_tabs)

        except Exception as e:
            self.add_log(f"❌ Error saving test summary: {str(e)}", "error")

    def calculate_test_duration(self, log_content, log_dir=None):
        """Calculate test duration from summary.json or log timestamps"""
        try:
            # First try to get duration from summary.json
            if log_dir:
                summary_path = os.path.join(log_dir, "summary.json")
                if os.path.exists(summary_path):
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                        steps = summary.get("steps", [])
                        if steps:
                            # Calculate total duration from first start to last end
                            start_times = [
                                step.get("start", 0)
                                for step in steps
                                if "start" in step
                            ]
                            end_times = [
                                step.get("end", 0) for step in steps if "end" in step
                            ]
                            if start_times and end_times:
                                first_start = min(start_times)
                                last_end = max(end_times)
                                if first_start and last_end:
                                    return max(last_end - first_start, 1)

            # Fallback to log parsing
            lines = log_content.split("\n")
            timestamps = []

            for line in lines:
                if line.startswith("[") and "]" in line:
                    time_str = line.split("]")[0][1:]  # Extract time part
                    try:
                        # Parse HH:MM:SS format
                        time_parts = time_str.split(":")
                        if len(time_parts) == 3:
                            hours = int(time_parts[0])
                            minutes = int(time_parts[1])
                            seconds = int(time_parts[2])
                            total_seconds = hours * 3600 + minutes * 60 + seconds
                            timestamps.append(total_seconds)
                    except:
                        continue

            if len(timestamps) >= 2:
                duration = timestamps[-1] - timestamps[0]
                # Handle day rollover (rough estimate)
                if duration < 0:
                    duration += 24 * 3600
                return max(duration, 1)  # At least 1 second
            else:
                return 1  # Default duration

        except:
            return 1  # Default duration

    def add_log(self, message, tag="info"):
        """Add a log message to the logs text widget"""
        if not hasattr(self, "logs_text") or not self.logs_text.winfo_exists():
            return

        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}\n"

            self.logs_text.insert(tk.END, formatted_message, tag)
            if hasattr(self, "auto_scroll_var") and self.auto_scroll_var.get():
                self.logs_text.see(tk.END)
            self.root.update_idletasks()
        except Exception as e:
            print(f"Error in add_log: {e}")  # Debug print instead of GUI log

    def stop_test(self):
        """Stop the running test"""
        if self.test_process and self.test_running:
            try:
                self.test_process.terminate()
                self.add_log("🛑 Test stopped by user", "warning")
                self.status_label.config(text="Stopped", fg=self.colors["warning"])
            except:
                pass

        self.test_running = False
        self.update_button_states()

    def clear_logs(self):
        """Clear the logs text widget"""
        self.logs_text.delete(1.0, tk.END)
        self.add_log("🗑️ Logs cleared", "info")

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
        # Placeholder for loading test history
        self.add_log("📊 Ready to run tests", "info")

    def refresh_results(self):
        """Refresh the results view"""
        self.add_log("🔄 Results refreshed", "info")

    def open_logs_folder(self):
        """Open the logs folder in file explorer"""
        try:
            logs_path = os.path.join(os.getcwd(), "logs")
            if os.path.exists(logs_path):
                if os.name == "nt":  # Windows
                    os.startfile(logs_path)
                elif os.name == "posix":  # macOS and Linux
                    subprocess.run(["open", logs_path])
            else:
                self.add_log("📁 Logs folder not found", "warning")
        except Exception as e:
            self.add_log(f"❌ Error opening logs folder: {str(e)}", "error")

    def view_selected_artifact(self):
        """View the selected artifact file"""
        selection = self.artifacts_listbox.curselection()
        if not selection:
            return

        # Get the selected artifact name
        artifact_name = self.artifacts_listbox.get(selection[0])
        # Remove emoji prefix
        clean_name = (
            artifact_name.split(" ", 1)[1] if " " in artifact_name else artifact_name
        )

        # Find the latest test directory
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            test_dirs = [
                d
                for d in os.listdir(logs_dir)
                if os.path.isdir(os.path.join(logs_dir, d)) and "checkout" in d
            ]

            if test_dirs:
                latest_dir = sorted(test_dirs, reverse=True)[0]
                artifact_path = os.path.join(logs_dir, latest_dir, clean_name)

                if os.path.exists(artifact_path):
                    try:
                        if clean_name.endswith(".png"):
                            # Open image with default viewer
                            if platform.system() == "Darwin":  # macOS
                                subprocess.run(["open", artifact_path])
                            elif platform.system() == "Windows":
                                subprocess.run(["explorer", artifact_path])
                            else:  # Linux
                                subprocess.run(["xdg-open", artifact_path])
                        elif clean_name.endswith(".html"):
                            # Open HTML in browser
                            if platform.system() == "Darwin":  # macOS
                                subprocess.run(["open", artifact_path])
                            elif platform.system() == "Windows":
                                subprocess.run(["explorer", artifact_path])
                            else:  # Linux
                                subprocess.run(["xdg-open", artifact_path])
                        else:
                            # Open text files with default editor
                            if platform.system() == "Darwin":  # macOS
                                subprocess.run(["open", artifact_path])
                            elif platform.system() == "Windows":
                                subprocess.run(["explorer", artifact_path])
                            else:  # Linux
                                subprocess.run(["xdg-open", artifact_path])
                    except Exception as e:
                        self.add_log(f"❌ Error opening artifact: {str(e)}", "error")
                else:
                    self.add_log(f"❌ Artifact not found: {clean_name}", "warning")

    def auto_refresh_all_tabs(self):
        """Automatically refresh both results and history tabs"""
        try:
            # Refresh results tab
            self.refresh_results()
            # Refresh history tab
            self.load_history_data()
            self.add_log("🔄 Auto-refreshed results and history tabs", "info")
        except Exception as e:
            self.add_log(f"❌ Auto-refresh error: {str(e)}", "error")

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
            close_btn = tk.Button(
                popup,
                text="Close",
                command=popup.destroy,
                bg=self.colors["primary"],
                fg=self.contrast_on(self.colors["primary"]),
                font=(self.fonts["default"], 10),
                bd=0,
                relief="flat",
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
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["open", logs_dir])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", logs_dir])
            else:  # Linux
                subprocess.run(["xdg-open", logs_dir])

    def refresh_results(self):
        """Load and display latest test results with proper artifacts"""
        try:
            # Find latest test directory
            logs_dir = "logs"
            latest_summary = None
            latest_dir = None

            if os.path.exists(logs_dir):
                # Get all test directories
                test_dirs = [
                    d
                    for d in os.listdir(logs_dir)
                    if os.path.isdir(os.path.join(logs_dir, d)) and "checkout" in d
                ]

                if test_dirs:
                    # Sort by name (timestamp-based) and get latest
                    test_dirs.sort(reverse=True)
                    latest_dir = test_dirs[0]
                    summary_file = os.path.join(logs_dir, latest_dir, "summary.json")

                    try:
                        if os.path.exists(summary_file):
                            with open(summary_file, "r") as f:
                                latest_summary = json.load(f)
                    except Exception as e:
                        self.add_log(f"❌ Error reading summary: {str(e)}", "error")

            # Update summary display
            if hasattr(self, "summary_text"):
                self.summary_text.delete(1.0, tk.END)

                if latest_summary:
                    # Format summary nicely
                    formatted_summary = self.format_test_summary(latest_summary)
                    self.summary_text.insert(tk.END, formatted_summary)
                else:
                    self.summary_text.insert(
                        tk.END,
                        "No test results available yet.\nRun a test to see results here.",
                    )

            # Load artifacts with proper categorization
            if hasattr(self, "artifacts_listbox"):
                self.artifacts_listbox.delete(0, tk.END)

                if latest_dir:
                    artifacts_path = os.path.join(logs_dir, latest_dir)
                    if os.path.exists(artifacts_path):
                        artifacts = []
                        for item in os.listdir(artifacts_path):
                            if item.endswith(
                                (".png", ".html", ".json", ".log", ".txt")
                            ):
                                # Add emoji based on file type
                                if item.endswith(".png"):
                                    display_name = f"🖼️ {item}"
                                elif item.endswith(".html"):
                                    display_name = f"📄 {item}"
                                elif item.endswith(".json"):
                                    display_name = f"📊 {item}"
                                elif item.endswith(".txt"):
                                    display_name = f"📝 {item}"
                                else:
                                    display_name = f"📁 {item}"
                                artifacts.append(display_name)

                        for artifact in sorted(artifacts):
                            self.artifacts_listbox.insert(tk.END, artifact)

                        self.add_log(
                            f"📁 Loaded {len(artifacts)} artifacts from {latest_dir}",
                            "info",
                        )
                    else:
                        self.add_log("📁 No artifacts found", "warning")
                else:
                    self.add_log("📁 No test directory found", "warning")

        except Exception as e:
            self.add_log(f"❌ Error refreshing results: {str(e)}", "error")

    def view_selected_artifact_button(self):
        """View the selected artifact file (button handler)."""
        selection = self.artifacts_listbox.curselection()
        if not selection:
            return
        artifact_name = self.artifacts_listbox.get(selection[0])
        clean_name = (
            artifact_name.split(" ", 1)[1] if " " in artifact_name else artifact_name
        )
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            test_dirs = [
                d
                for d in os.listdir(logs_dir)
                if os.path.isdir(os.path.join(logs_dir, d)) and "checkout" in d
            ]
            if test_dirs:
                latest_dir = sorted(test_dirs, reverse=True)[0]
                artifact_path = os.path.join(logs_dir, latest_dir, clean_name)
                if os.path.exists(artifact_path):
                    try:
                        if clean_name.endswith((".txt", ".log", ".json")):
                            self.open_text_artifact_internally(
                                artifact_path, clean_name
                            )
                        else:
                            self.open_file_externally(artifact_path)
                    except Exception as e:
                        self.add_log(f"❌ Error opening artifact: {str(e)}", "error")
                else:
                    self.add_log(f"❌ Artifact not found: {clean_name}", "warning")

    def open_text_artifact_internally(self, file_path, title):
        """Metin tabanlı artifact'leri uygulama içinde yeni bir pencerede açar."""
        popup = tk.Toplevel(self.root)
        popup.title(f"Artifact Görüntüle: {title}")
        popup.transient(self.root)  # Ana pencerenin üzerinde görünmesini sağlar
        popup.grab_set()  # Modal yapar, ana pencereye tıklanamaz

        text_frame = ttk.Frame(popup, padding=self.spacing["md"])
        text_frame.pack(fill="both", expand=True)

        text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap="word",
            font=(self.fonts["mono"], 10),
            bg=self.colors["surface_dark"],
            fg=self.colors["text_primary"],
            insertbackground=self.colors["text_primary"],
        )
        text_widget.pack(fill="both", expand=True)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                text_widget.insert(tk.END, content)
            text_widget.config(state="disabled")  # Sadece okunabilir yap
        except Exception as e:
            text_widget.insert(tk.END, f"Dosya okunurken hata oluştu: {e}")
            text_widget.config(state="disabled")

        # Kapatma butonu ekle
        close_button = tk.Button(
            popup,
            text="Kapat",
            command=popup.destroy,
            font=(self.fonts["default"], 10),
            bg=self.colors["secondary"],
            fg=self.contrast_on(self.colors["secondary"]),
            bd=0,
            relief="flat",
            cursor="hand2",
        )
        close_button.pack(pady=self.spacing["sm"])

        popup.update_idletasks()
        # Popup'ı ana pencerenin ortasına hizala
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()

        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()

        x = main_x + (main_width // 2) - (popup_width // 2)
        y = main_y + (main_height // 2) - (popup_height // 2)
        popup.geometry(f"+{x}+{y}")

    def open_file_externally(self, file_path):
        """Artifact'i sistemin varsayılan uygulamasıyla harici olarak açar."""
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", file_path])
            self.add_log(f"📁 Artifact harici olarak açıldı: {file_path}", "info")
        except Exception as e:
            self.add_log(
                f"❌ Artifact harici olarak açılırken hata oluştu: {e}", "error"
            )

    def format_test_summary(self, summary):
        """Format test summary for display"""
        lines = []
        lines.append("🔍 TEST EXECUTION SUMMARY")
        lines.append("=" * 40)
        lines.append("")

        # Basic info
        status = summary.get("status", "unknown")
        status_emoji = "✅" if status == "ok" else "❌"
        lines.append(f"Status: {status_emoji} {status.upper()}")

        # Project and mode
        project = summary.get("project", "Unknown")
        mode = summary.get("mode", "Unknown")
        lines.append(f"Project: 🎯 {project}")

        if summary.get("headless"):
            lines.append("Mode: 🕶️ Headless")
        else:
            lines.append("Mode: 🖥️ Normal")

        # Timing info
        duration = summary.get("durationSec", 0)
        lines.append(f"Duration: ⏱️ {duration:.1f}s")

        # Timestamp
        timestamp = summary.get("timestamp", "Unknown")
        if timestamp != "Unknown":
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"Timestamp: 📅 {formatted_time}")
            except:
                lines.append(f"Timestamp: 📅 {timestamp}")

        lines.append("")

        # Steps summary (if available)
        if summary.get("steps"):
            lines.append("📋 TEST STEPS:")
            lines.append("-" * 20)

            for i, step in enumerate(summary["steps"], 1):
                step_status = step.get("status", "unknown")
                step_emoji = "✅" if step_status == "ok" else "❌"
                step_name = step.get("name", "Unknown Step")
                step_duration = step.get("durationSec", 0)

                lines.append(f"{i:2d}. {step_emoji} {step_name} ({step_duration:.1f}s)")

                if step.get("note"):
                    lines.append(f"     💬 {step['note']}")

        # Error info
        if summary.get("error"):
            lines.append("")
            lines.append("❌ ERROR DETAILS:")
            lines.append("-" * 20)
            lines.append(summary["error"])

        # Log info
        log_lines = summary.get("logLines", 0)
        if log_lines > 0:
            lines.append("")
            lines.append(f"📊 Log Lines: {log_lines}")

        return "\n".join(lines)

    def load_test_history(self):
        """Load test execution history"""
        # Placeholder for loading test history
        self.add_log("📊 Ready to run tests", "info")

    def load_history_data(self):
        """Load test history data from logs directory with detailed information"""
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        if not os.path.exists(logs_dir):
            return

        # Clear existing data
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Get all test directories
        test_dirs = []
        for item in os.listdir(logs_dir):
            item_path = os.path.join(logs_dir, item)
            if os.path.isdir(item_path) and item.endswith("-checkout"):
                test_dirs.append(item)

        # Sort by date/time (newest first)
        test_dirs.sort(reverse=True)

        for test_dir in test_dirs:
            summary_path = os.path.join(logs_dir, test_dir, "summary.json")
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, "r") as f:
                        summary = json.load(f)

                    # Parse datetime from directory name (format: 20250821-203515-checkout)
                    date_str = test_dir.replace("-checkout", "")
                    date_obj = datetime.strptime(date_str, "%Y%m%d-%H%M%S")

                    date = date_obj.strftime("%Y-%m-%d")
                    time = date_obj.strftime("%H:%M:%S")

                    # Extract test details from summary
                    project = summary.get("project", "GOOGLE")
                    mode = summary.get("mode", "headless")

                    # Get status with proper mapping
                    status = "Failed"
                    if summary.get("status") == "ok":
                        status = "Success"
                    elif summary.get("status") == "success":
                        status = "Success"

                    # Get duration
                    duration = summary.get("durationSec", 0)
                    duration_str = f"{duration:.1f}s"

                    # Create detailed error information
                    details = ""
                    if status == "Failed":
                        error = summary.get("error", "Unknown error")
                        if error:
                            # Truncate long error messages but keep important parts
                            if len(error) > 80:
                                details = error[:77] + "..."
                            else:
                                details = error
                        else:
                            details = "No error details available"
                    else:
                        details = "Test completed successfully"

                    # Insert into treeview
                    self.history_tree.insert(
                        "",
                        "end",
                        values=(date, time, project, mode, status, duration_str, details),
                    )

                except Exception as e:
                    print(f"Error loading summary from {test_dir}: {e}")
                    # Insert error row with more context
                    try:
                        date_str = test_dir.replace("-checkout", "")
                        date_obj = datetime.strptime(date_str, "%Y%m%d-%H%M%S")
                        date = date_obj.strftime("%Y-%m-%d")
                        time = date_obj.strftime("%H:%M:%S")
                    except:
                        date = test_dir[:10]
                        time = test_dir[11:19]

                    self.history_tree.insert(
                        "",
                        "end",
                        values=(
                            date,
                            time,
                            "GOOGLE",
                            "headless",
                            "Error",
                            "0s",
                            f"Failed to load summary: {str(e)[:50]}",
                        ),
                    )

    def clear_all_logs(self):
        """Delete all files and folders under the logs directory and refresh UI."""
        try:
            logs_dir = os.path.join(os.path.dirname(__file__), "logs")
            if os.path.exists(logs_dir):
                for name in os.listdir(logs_dir):
                    path = os.path.join(logs_dir, name)
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path, ignore_errors=True)
                        else:
                            try:
                                os.remove(path)
                            except Exception:
                                pass
                    except Exception:
                        pass
                self.add_log("🧹 All logs cleared", "info")
            else:
                self.add_log("📁 Logs folder not found", "warning")
        except Exception as e:
            self.add_log(f"❌ Error clearing logs: {e}", "error")
        # Refresh History and Results tabs after clearing
        try:
            self.load_history_data()
            self.refresh_results()
        except Exception:
            pass

    def consume_test_logs(self):
        """Consume test output in a separate thread"""
        try:
            test_failed = False
            error_message = None

            for line in iter(self.test_process.stdout.readline, ""):
                if line:
                    line_text = line.strip()

                    # Detect test failures using stricter rules to avoid false positives like
                    # "Network errors saved" (which is informational).
                    normalized = line_text.strip()
                    lower = normalized.lower()
                    is_explicit_fail = (
                        normalized.startswith("✗")
                        or normalized.startswith("❌")
                        or "] ERROR" in normalized
                        or normalized.startswith("ERROR")
                        or " critical step failed" in lower
                        or "selector" in lower
                        and "not found" in lower
                        or "timeout" in lower
                        and ("failed" in lower or "selector" in lower)
                    )
                    if is_explicit_fail:
                        test_failed = True
                        error_message = line_text
                        self.add_log(line_text, "error")
                        # Do NOT kill the subprocess; let the test engine finish and write artifacts
                    elif "warning" in line_text.lower():
                        self.add_log(line_text, "warning")
                    else:
                        self.add_log(line_text, "info")

            # Wait for completion (let the engine write artifacts in finally)
            self.test_process.wait()

            # Determine final status
            if test_failed or self.test_process.returncode != 0:
                self.add_log("❌ Test failed!", "error")
                self.status_label.config(text="Failed", fg=self.colors["danger"])
                test_status = "failed"
            else:
                self.add_log("✅ Test completed successfully!", "success")
                self.status_label.config(text="Completed", fg=self.colors["success"])
                test_status = "ok"

            # Create test summary
            project_name = self.project_var.get()  # Get project name for summary
            self.create_test_summary(test_status, error_message, project_name)

            # Update UI
            self.test_running = False
            self.update_button_states()
            self.refresh_results()

        except Exception as e:
            self.add_log(f"❌ Error in log consumer: {str(e)}", "error")
            self.test_running = False
            self.update_button_states()

    def setup_builder_tab(self):
        """Create a Test Builder tab to create JSON flows from the GUI"""
        try:
            builder_frame = tk.Frame(self.notebook, bg=self.colors["background"])
            self.notebook.add(builder_frame, text="Test Builder")

            # Header
            header = tk.Frame(builder_frame, bg=self.colors["surface"])
            header.pack(fill=tk.X, padx=self.spacing["md"], pady=self.spacing["md"])
            tk.Label(
                header,
                text="Create New Flow",
                font=(self.fonts["default"], 14, "bold"),
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
            ).pack(side=tk.LEFT)

            # Form container
            form = tk.Frame(builder_frame, bg=self.colors["background"])
            form.pack(
                fill=tk.BOTH,
                expand=True,
                padx=self.spacing["md"],
                pady=self.spacing["md"],
            )

            # Project select
            tk.Label(
                form,
                text="Project",
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            ).grid(row=0, column=0, sticky="w")
            self.builder_project_var = tk.StringVar(
                value=list(self.projects.keys())[0] if self.projects else ""
            )
            self.builder_project_combo = ttk.Combobox(
                form,
                textvariable=self.builder_project_var,
                values=list(self.projects.keys()),
                state="readonly",
            )
            self.builder_project_combo.grid(row=0, column=1, sticky="we", padx=(8, 0))

            # Flow name
            tk.Label(
                form,
                text="Flow name",
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            ).grid(row=1, column=0, sticky="w", pady=(6, 0))
            self.builder_flow_var = tk.StringVar()
            self.builder_flow_entry = tk.Entry(
                form,
                textvariable=self.builder_flow_var,
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
                insertbackground=self.colors["text_primary"],
            )
            self.builder_flow_entry.grid(
                row=1, column=1, sticky="we", padx=(8, 0), pady=(6, 0)
            )

            # Steps list
            steps_frame = tk.LabelFrame(
                form,
                text="Steps",
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            )
            steps_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
            form.grid_rowconfigure(2, weight=1)
            form.grid_columnconfigure(1, weight=1)

            # Step form
            sf = tk.Frame(steps_frame, bg=self.colors["background"])
            sf.pack(fill=tk.X, padx=10, pady=10)

            tk.Label(
                sf,
                text="Action",
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            ).grid(row=0, column=0, sticky="w")
            self.step_action_var = tk.StringVar(value="navigate")
            self.step_action_combo = ttk.Combobox(
                sf,
                textvariable=self.step_action_var,
                values=["navigate", "click", "fill", "wait"],
                state="readonly",
                width=12,
            )
            self.step_action_combo.grid(row=0, column=1, padx=(6, 12))
            self.step_action_combo.bind(
                "<<ComboboxSelected>>", lambda e: self.builder_on_action_change()
            )

            self.step_target_label = tk.Label(
                sf,
                text="Selector / URL",
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            )
            self.step_target_label.grid(row=0, column=2, sticky="w")
            self.step_target_var = tk.StringVar()
            self.step_target_entry = tk.Entry(
                sf,
                textvariable=self.step_target_var,
                width=40,
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
                insertbackground=self.colors["text_primary"],
            )
            self.step_target_entry.grid(row=0, column=3, padx=(6, 12))
            # Enter key adds step for quick input
            self.step_target_entry.bind("<Return>", lambda e: self.builder_add_step())

            self.step_value_label = tk.Label(
                sf,
                text="Value (only for fill)",
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            )
            self.step_value_label.grid(row=0, column=4, sticky="w")
            self.step_value_var = tk.StringVar()
            self.step_value_entry = tk.Entry(
                sf,
                textvariable=self.step_value_var,
                width=20,
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
                insertbackground=self.colors["text_primary"],
            )
            self.step_value_entry.grid(row=0, column=5, padx=(6, 12))
            self.step_value_entry.configure(state=tk.DISABLED)
            self.step_value_entry.bind("<Return>", lambda e: self.builder_add_step())
            # Spacer to keep layout stable when value is hidden
            self.step_value_spacer = tk.Frame(
                sf, width=200, height=1, bg=self.colors["background"]
            )
            # Initially show spacer (since value is hidden by default)
            self.step_value_spacer.grid(row=0, column=4, columnspan=2, sticky="w")

            tk.Label(
                sf,
                text="Timeout",
                bg=self.colors["background"],
                fg=self.colors["text_primary"],
            ).grid(row=0, column=6, sticky="w")
            self.step_timeout_var = tk.StringVar(value="40")
            self.step_timeout_entry = tk.Entry(
                sf,
                textvariable=self.step_timeout_var,
                width=6,
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
                insertbackground=self.colors["text_primary"],
            )
            self.step_timeout_entry.grid(row=0, column=7, padx=(6, 12))
            self.step_timeout_entry.bind("<Return>", lambda e: self.builder_add_step())

            # Add Step button below the form for consistent visibility
            tk.Button(
                sf,
                text="Add Step",
                command=self.builder_add_step,
                bg=self.colors["primary"],
                fg=self.contrast_on(self.colors["primary"]),
                activebackground=self.colors["surface_dark"],
                activeforeground=self.colors["text_primary"],
                bd=0,
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

            # Initialize contextual labels/states
            self.builder_on_action_change()

            self.steps_listbox = tk.Listbox(
                steps_frame,
                bg=self.colors["surface"],
                fg=self.colors["text_primary"],
                selectbackground=self.colors["primary"],
            )
            self.steps_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            btns = tk.Frame(steps_frame, bg=self.colors["background"])
            btns.pack(fill=tk.X, padx=10, pady=(0, 10))
            tk.Button(
                btns,
                text="Remove Selected",
                command=self.builder_remove_selected,
                bg=self.colors["secondary"],
                fg=self.contrast_on(self.colors["secondary"]),
                activebackground=self.colors["surface_dark"],
                activeforeground=self.colors["text_primary"],
                bd=0,
            ).pack(side=tk.LEFT, padx=(10, 0))

            # Save area
            save_frame = tk.Frame(form, bg=self.colors["background"])
            save_frame.grid(row=3, column=0, columnspan=3, sticky="we", pady=(10, 0))
            # Error display (validation)
            self.builder_error_var = tk.StringVar()
            self.builder_error_label = tk.Label(
                save_frame,
                textvariable=self.builder_error_var,
                bg=self.colors["background"],
                fg=self.colors["danger"],
            )
            self.builder_error_label.pack(side=tk.LEFT, padx=(0, 10))
            self.builder_error_var.set("")
            tk.Button(
                save_frame,
                text="Save Flow",
                command=self.builder_save_flow,
                bg=self.colors["success"],
                fg=self.contrast_on(self.colors["success"]),
                activebackground=self.colors["surface_dark"],
                activeforeground=self.colors["text_primary"],
                bd=0,
            ).pack(side=tk.LEFT)
            self.builder_status_var = tk.StringVar()
            tk.Label(
                save_frame,
                textvariable=self.builder_status_var,
                bg=self.colors["background"],
                fg=self.colors["text_secondary"],
            ).pack(side=tk.LEFT, padx=(10, 0))

        except Exception as e:
            self.add_log(f"❌ Error initializing Test Builder: {e}", "error")

    def builder_add_step(self):
        try:
            action = self.step_action_var.get().strip()
            target = self.step_target_var.get().strip()
            value = self.step_value_var.get().strip()
            timeout = self.step_timeout_var.get().strip()
            # Reset previous error
            if hasattr(self, "builder_error_var"):
                self.builder_error_var.set("")
            # Validations
            if action == "navigate" and not target:
                if hasattr(self, "builder_error_var"):
                    self.builder_error_var.set("❌ URL is required for navigate action")
                else:
                    self.builder_status_var.set("URL is required for navigate")
                return
            if action in ("click", "fill", "wait") and not target:
                if hasattr(self, "builder_error_var"):
                    self.builder_error_var.set(
                        "❌ Selector is required for click/fill/wait actions"
                    )
                else:
                    self.builder_status_var.set("Selector is required")
                return
            if action == "fill" and not value:
                if hasattr(self, "builder_error_var"):
                    self.builder_error_var.set("❌ Value is required for fill action")
                else:
                    self.builder_status_var.set("Value is required for fill")
                return
            try:
                timeout_int = int(timeout) if timeout else 40
            except ValueError:
                timeout_int = 40

            # Generate name & artifact_tag (robust for selectors like [data-attr])
            short = self._shorten_selector_for_name(target)
            if action == "navigate":
                name = f"Navigate to {target[:50]}"
            else:
                name = f"{action.capitalize()} {short}"
            slug = name.lower().replace(" ", "-").replace("/", "-")[:40]

            step = {
                "name": name,
                "action": action,
                ("url" if action == "navigate" else "selector"): target,
            }
            if action == "fill":
                step["value"] = value
            step["timeout"] = timeout_int
            step["critical"] = True
            step["artifact_tag"] = slug

            # Render in listbox
            self.steps_listbox.insert(tk.END, json.dumps(step))
            self.builder_status_var.set("✅ Step added successfully")
            if hasattr(self, "builder_error_var"):
                self.builder_error_var.set("")
            # Clear inputs for next step
            self.step_target_var.set("")
            if action == "fill":
                self.step_value_var.set("")
            # Focus back to selector/url for fast entry
            try:
                self.step_target_entry.focus_set()
            except Exception:
                pass
        except Exception as e:
            if hasattr(self, "builder_error_var"):
                self.builder_error_var.set(f"❌ Failed to add step: {e}")
            else:
                self.builder_status_var.set(f"Failed to add step: {e}")

    def builder_remove_selected(self):
        try:
            sel = self.steps_listbox.curselection()
            if not sel:
                return
            self.steps_listbox.delete(sel[0])
            self.builder_status_var.set("Removed")
        except Exception as e:
            self.builder_status_var.set(f"Failed to remove: {e}")

    def builder_save_flow(self):
        try:
            project = self.builder_project_var.get().strip()
            flow = self.builder_flow_var.get().strip()
            # Reset error
            if hasattr(self, "builder_error_var"):
                self.builder_error_var.set("")
            # Basic validations
            if not project or not flow:
                if hasattr(self, "builder_error_var"):
                    self.builder_error_var.set("❌ Project and flow name are required")
                else:
                    self.builder_status_var.set("Project and flow name are required")
                return
            steps = []
            for i in range(self.steps_listbox.size()):
                raw = self.steps_listbox.get(i)
                steps.append(json.loads(raw))
            if not steps:
                if hasattr(self, "builder_error_var"):
                    self.builder_error_var.set(
                        "❌ At least one step is required before saving"
                    )
                else:
                    self.builder_status_var.set("At least one step is required")
                return

            flow_obj = {"PROJECT_CONFIG": {"name": project}, "TEST_STEPS": steps}
            project_dir = os.path.join("tests", "projects", project)
            os.makedirs(project_dir, exist_ok=True)
            file_path = os.path.join(project_dir, f"{flow}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(flow_obj, f, ensure_ascii=False, indent=2)

            self.builder_status_var.set(f"✅ Saved: {os.path.basename(file_path)}")
            if hasattr(self, "builder_error_var"):
                self.builder_error_var.set("")
            # Refresh flows in header ONLY if builder project matches current header project
            current_project = self.project_var.get()
            if current_project == project:
                self.refresh_flows_for_project(project)
        except Exception as e:
            if hasattr(self, "builder_error_var"):
                self.builder_error_var.set(f"❌ Failed to save: {e}")
            else:
                self.builder_status_var.set(f"Failed to save: {e}")

    def _shorten_selector_for_name(self, selector: str) -> str:
        """Create a readable short label from a CSS selector without leaving dangling characters.
        Examples:
        - '#btn-primary > span' -> '#btn-primary'
        - '.card .title' -> '.card'
        - "[data-test='submit']" -> "[data-test='submit']"
        - 'div[role=button]' -> 'div[role=button]'
        - '' or None -> ''
        """
        try:
            if not selector:
                return ""
            import re

            s = selector.strip()
            # Prefer id or class token at start
            m = re.match(r"^[#.][A-Za-z0-9_-]+", s)
            if m:
                return m.group(0)
            # Attribute selector at start: capture up to matching ]
            m = re.match(r"^\[[^\]]{1,60}\]", s)
            if m:
                return m.group(0)
            # Tag with attribute: capture like div[role=button]
            m = re.match(r"^[A-Za-z0-9_-]+\[[^\]]{1,60}\]", s)
            if m:
                return m.group(0)
            # Otherwise take first token until space, '>' or ','
            cut = re.split(r"\s|>|,", s, maxsplit=1)[0]
            return cut[:60]
        except Exception:
            return (selector or "")[:30]

    def builder_on_action_change(self):
        try:
            action = self.step_action_var.get().strip()
            if action == "navigate":
                self.step_target_label.configure(text="URL")
                # Hide value field, show spacer so Add button stays visible
                try:
                    self.step_value_label.grid_remove()
                    self.step_value_entry.grid_remove()
                    self.step_value_spacer.grid(
                        row=0, column=4, columnspan=2, sticky="w"
                    )
                except Exception:
                    pass
            elif action == "fill":
                self.step_target_label.configure(text="Selector")
                # Show value field
                try:
                    self.step_value_spacer.grid_remove()
                    self.step_value_label.grid(row=0, column=4, sticky="w")
                    self.step_value_entry.grid(row=0, column=5, padx=(6, 12))
                except Exception:
                    pass
                self.step_value_entry.configure(state=tk.NORMAL)
            else:
                self.step_target_label.configure(text="Selector")
                # Hide value field, show spacer so Add button stays visible
                try:
                    self.step_value_label.grid_remove()
                    self.step_value_entry.grid_remove()
                    self.step_value_spacer.grid(
                        row=0, column=4, columnspan=2, sticky="w"
                    )
                except Exception:
                    pass
        except Exception:
            pass


def main():
    root = tk.Tk()
    app = TestRunnerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
