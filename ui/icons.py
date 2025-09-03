from __future__ import annotations

import os
from PIL import Image, ImageTk


def load_icons(app) -> None:
    try:
        app.play_icon = None
        app.stop_icon = None
        app.delete_icon = None
        app.settings_icon = None

        def _load(name: str, size: tuple[int, int]):
            path = os.path.join("assets", name)
            if os.path.exists(path):
                img = Image.open(path).resize(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            return None

        app.play_icon = _load("play-icon.png", (32, 32))
        app.stop_icon = _load("stop-icon.png", (32, 32))
        app.delete_icon = _load("delete-icon.png", (32, 32))

        # settings icon can vary
        for n in ["settings@2x.png", "settings.png", "settings-icon.png", "gear.png"]:
            icon = _load(n, (48, 48))
            if icon is not None:
                app.settings_icon = icon
                break
    except Exception:
        app.play_icon = None
        app.stop_icon = None
        app.delete_icon = None
        app.settings_icon = None
