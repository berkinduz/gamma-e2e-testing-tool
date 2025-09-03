from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class Theme:
    name: str
    colors: dict
    spacing: dict
    fonts: dict


def _load_json_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_theme(theme_name: str = None) -> Theme:
    """Load theme configuration from config/theme_config.json with sensible defaults."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    cfg_path = os.path.join(root_dir, "config", "theme_config.json")
    cfg = _load_json_config(cfg_path)

    # Get current theme name
    if theme_name is None:
        theme_name = cfg.get("current_theme", "dark")

    # Get theme data
    themes = cfg.get("themes", {})
    theme_data = themes.get(theme_name, {})

    # Get user customizations
    user_customizations = cfg.get("user_customizations", {})
    user_overrides = (
        user_customizations.get("overrides", {})
        if user_customizations.get("enabled", False)
        else {}
    )

    # Default fallback theme
    default_theme = {
        "name": "Dark Slate",
        "colors": {
            "background": "#0b1220",
            "surface": "#111827",
            "surface_light": "#1f2937",
            "surface_dark": "#0a0f1a",
            "surface_secondary": "#2a3443",
            "primary": "#3b82f6",
            "secondary": "#22d3ee",
            "accent": "#f59e0b",
            "success": "#10b981",
            "warning": "#fbbf24",
            "danger": "#ef4444",
            "text_primary": "#e5e7eb",
            "text_secondary": "#9ca3af",
            "text_muted": "#4b5563",
            "border": "#1f2937",
            "selection": "#1f2937",
        },
        "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
        "fonts": {"default": "Inter", "mono": "JetBrains Mono"},
    }

    # Merge theme data with defaults
    theme_data = {**default_theme, **theme_data}

    # Apply user customizations if enabled
    if user_customizations.get("enabled", False):
        colors = {**theme_data.get("colors", {}), **user_overrides.get("colors", {})}
        spacing = {**theme_data.get("spacing", {}), **user_overrides.get("spacing", {})}
        fonts = {**theme_data.get("fonts", {}), **user_overrides.get("fonts", {})}
    else:
        colors = theme_data.get("colors", default_theme["colors"])
        spacing = theme_data.get("spacing", default_theme["spacing"])
        fonts = theme_data.get("fonts", default_theme["fonts"])

    name = theme_data.get("name", theme_name)
    return Theme(name=name, colors=colors, spacing=spacing, fonts=fonts)


def get_available_themes() -> list:
    """Get list of available theme names."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    cfg_path = os.path.join(root_dir, "config", "theme_config.json")
    cfg = _load_json_config(cfg_path)

    themes = cfg.get("themes", {})
    return list(themes.keys())


def save_theme_config(config: dict) -> bool:
    """Save theme configuration to config/theme_config.json."""
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        cfg_path = os.path.join(root_dir, "config", "theme_config.json")

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def switch_theme(theme_name: str) -> bool:
    """Switch to a different theme."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    cfg_path = os.path.join(root_dir, "config", "theme_config.json")
    cfg = _load_json_config(cfg_path)

    # Check if theme exists
    themes = cfg.get("themes", {})
    if theme_name not in themes:
        return False

    # Update current theme
    cfg["current_theme"] = theme_name

    # Save config
    return save_theme_config(cfg)
