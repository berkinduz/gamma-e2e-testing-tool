import os
import json
from datetime import datetime
from ui.theme import load_theme


def _hex_to_rgb(hex_color: str):
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


def _load_prefs(app) -> dict:
    try:
        if os.path.exists(app.prefs_path):
            with open(app.prefs_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_prefs(app) -> None:
    try:
        data = {
            "project": (app.project_var.get() if hasattr(app, "project_var") else ""),
            "flow": app.flow_var.get() if hasattr(app, "flow_var") else "",
            "mode": (app.mode_var.get() if hasattr(app, "mode_var") else "headless"),
        }
        with open(app.prefs_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _relative_luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)

    def _to_linear(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl = 0.2126 * _to_linear(r) + 0.7152 * _to_linear(g) + 0.0722 * _to_linear(b)
    return rl


def contrast_on(bg_hex: str, colors: dict) -> str:
    """Return black or white depending on background for readable text."""
    try:
        lum = _relative_luminance(bg_hex)
        # Threshold chosen for decent legibility across themes
        return "#000000" if lum > 0.5 else "#ffffff"
    except Exception:
        return colors.get("text_primary", "#ffffff")


def load_theme_config(app) -> None:
    """Load theme via theme module"""
    theme = load_theme()
    app.colors = theme.colors
    app.spacing = theme.spacing
    app.fonts = theme.fonts
    app.current_theme = theme.name


def on_project_change(app) -> None:
    """Handle project selection change"""
    project_name = app.project_var.get()
    if project_name in app.projects:
        project_config = app.projects[project_name]
        app.add_log(f"🔄 Switched to project: {project_config['name']}", "info")
        # Refresh available flows for this project
        try:
            app.refresh_flows_for_project(project_name)
        except Exception as e:
            app.add_log(f"Failed to refresh flows: {e}", "error")
        try:
            app._save_prefs()
        except Exception:
            pass
    else:
        app.add_log(f"⚠️ Unknown project: {project_name}", "warning")


def discover_projects() -> dict:
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
            discovered[entry] = {
                "name": entry,
                "script": default_script or os.path.join(project_dir, "main.py"),
                "dir": project_dir,
                "env_vars": env_vars,
            }
    return discovered


def format_test_summary(summary: dict) -> str:
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

        lines.append("")

    # Error details (if available)
    if summary.get("error"):
        lines.append("❌ ERROR DETAILS:")
        lines.append("-" * 20)
        lines.append(summary["error"])
        lines.append("")

    # Log summary
    log_lines = summary.get("logLines", 0)
    lines.append(f"📊 Log lines: {log_lines}")

    return "\n".join(lines)
