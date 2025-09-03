import os
import json
import subprocess
import platform
import sys
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.scrolledtext as scrolledtext


def refresh_results(app) -> None:
    """Refresh the results view"""
    app.add_log("🔄 Results refreshed", "info")


def open_logs_folder(app) -> None:
    """Open the logs folder in file explorer"""
    try:
        logs_path = os.path.join(os.getcwd(), "logs")
        if os.path.exists(logs_path):
            if os.name == "nt":  # Windows
                os.startfile(logs_path)
            elif os.name == "posix":  # macOS and Linux
                subprocess.run(["open", logs_path])
        else:
            app.add_log("📁 Logs folder not found", "warning")
    except Exception as e:
        app.add_log(f"❌ Error opening logs folder: {str(e)}", "error")


def view_selected_artifact(app) -> None:
    """View the selected artifact file"""
    selection = app.artifacts_listbox.curselection()
    if not selection:
        return

    # Get the selected artifact name
    artifact_name = app.artifacts_listbox.get(selection[0])
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
                    app.add_log(f"❌ Error opening artifact: {str(e)}", "error")
            else:
                app.add_log(f"❌ Artifact not found: {clean_name}", "warning")


def auto_refresh_all_tabs(app) -> None:
    """Automatically refresh both results and history tabs"""
    try:
        # Refresh results tab
        app.refresh_results()
        # Refresh history tab
        app.load_history_data()
        app.add_log("🔄 Auto-refreshed results and history tabs", "info")
    except Exception as e:
        app.add_log(f"❌ Auto-refresh error: {str(e)}", "error")


def refresh_results_detailed(app) -> None:
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
                    app.add_log(f"❌ Error reading summary: {str(e)}", "error")

        # Update summary display
        if hasattr(app, "summary_text"):
            app.summary_text.delete(1.0, tk.END)

            if latest_summary:
                # Format summary nicely
                formatted_summary = app.format_test_summary(latest_summary)
                app.summary_text.insert(tk.END, formatted_summary)
            else:
                app.summary_text.insert(
                    tk.END,
                    "No test results available yet.\nRun a test to see results here.",
                )

        # Load artifacts with proper categorization
        if hasattr(app, "artifacts_listbox"):
            app.artifacts_listbox.delete(0, tk.END)

            if latest_dir:
                artifacts_path = os.path.join(logs_dir, latest_dir)
                if os.path.exists(artifacts_path):
                    artifacts = []
                    for item in os.listdir(artifacts_path):
                        if item.endswith((".png", ".html", ".json", ".log", ".txt")):
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
                        app.artifacts_listbox.insert(tk.END, artifact)

                    app.add_log(
                        f"📁 Loaded {len(artifacts)} artifacts from {latest_dir}",
                        "info",
                    )
                else:
                    app.add_log("📁 No artifacts found", "warning")
            else:
                app.add_log("📁 No test directory found", "warning")

    except Exception as e:
        app.add_log(f"❌ Error refreshing results: {str(e)}", "error")


def view_selected_artifact_button(app) -> None:
    """View the selected artifact file (button handler)."""
    selection = app.artifacts_listbox.curselection()
    if not selection:
        return
    artifact_name = app.artifacts_listbox.get(selection[0])
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
                        open_text_artifact_internally(app, artifact_path, clean_name)
                    else:
                        open_file_externally(app, artifact_path)
                except Exception as e:
                    app.add_log(f"❌ Error opening artifact: {str(e)}", "error")
            else:
                app.add_log(f"❌ Artifact not found: {clean_name}", "warning")


def open_text_artifact_internally(app, file_path, title) -> None:
    """Metin tabanlı artifact'leri uygulama içinde yeni bir pencerede açar."""
    popup = tk.Toplevel(app.root)
    popup.title(f"Artifact Görüntüle: {title}")
    popup.transient(app.root)  # Ana pencerenin üzerinde görünmesini sağlar
    popup.grab_set()  # Modal yapar, ana pencereye tıklanamaz

    text_frame = ttk.Frame(popup, padding=app.spacing["md"])
    text_frame.pack(fill="both", expand=True)

    text_widget = scrolledtext.ScrolledText(
        text_frame,
        wrap="word",
        font=(app.fonts["mono"], 10),
        bg=app.colors["surface_dark"],
        fg=app.colors["text_primary"],
        insertbackground=app.colors["text_primary"],
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
    close_button = (ttk.Button if platform.system() == "Darwin" else tk.Button)(
        popup,
        text="Kapat",
        command=popup.destroy,
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
    )
    close_button.pack(pady=app.spacing["sm"])

    popup.update_idletasks()
    # Popup'ı ana pencerenin ortasına hizala
    main_x = app.root.winfo_x()
    main_y = app.root.winfo_y()
    main_width = app.root.winfo_width()
    main_height = app.root.winfo_height()

    popup_width = popup.winfo_width()
    popup_height = popup.winfo_height()

    x = main_x + (main_width // 2) - (popup_width // 2)
    y = main_y + (main_height // 2) - (popup_height // 2)
    popup.geometry(f"+{x}+{y}")


def open_file_externally(app, file_path) -> None:
    """Artifact'i sistemin varsayılan uygulamasıyla harici olarak açar."""
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", file_path])
        else:  # Linux
            subprocess.run(["xdg-open", file_path])
        app.add_log(f"📁 Artifact harici olarak açıldı: {file_path}", "info")
    except Exception as e:
        app.add_log(f"❌ Artifact harici olarak açılırken hata oluştu: {e}", "error")
