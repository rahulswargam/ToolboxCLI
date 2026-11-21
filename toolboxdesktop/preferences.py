"""Readable per-user preferences, written atomically outside the install folder."""
from __future__ import annotations
import json
import os
from pathlib import Path


class Preferences:
    def __init__(self, folder=None):
        self.folder = Path(folder) if folder else Path(os.environ.get("APPDATA", Path.home() / ".config")) / "RahulsToolbox" / "settings"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "preferences.json"
        self.data = {"theme": "auto", "favorites": ["merge_pdf", "sign_pdf", "remove_duplicates"], "history": []}
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    self.data.update(saved)
            except (ValueError, OSError):
                backup = self.folder / "preferences.invalid.json"
                if not backup.exists():
                    backup.write_bytes(self.path.read_bytes())
        elif folder is None:
            self._migrate()
        if self.data.get("theme") not in ("dark", "light", "auto"):
            self.data["theme"] = "auto"
        if not isinstance(self.data.get("favorites"), list):
            self.data["favorites"] = []
        self.data["favorites"] = [item for item in self.data["favorites"] if isinstance(item, str)]
        if not isinstance(self.data.get("history"), list):
            self.data["history"] = []
        self.data["history"] = [row for row in self.data["history"] if isinstance(row, list) and len(row) == 3 and all(isinstance(item, str) for item in row)][:100]
        if "output" in self.data and not isinstance(self.data["output"], str):
            del self.data["output"]
        self.save()

    def _migrate(self):
        from PySide6.QtCore import QSettings
        old = QSettings("RahulSwargam", "ToolboxDesktop")
        for key in ("output", "favorites"):
            if old.contains(key):
                self.data[key] = old.value(key)
        try:
            self.data["history"] = json.loads(old.value("history", "[]"))
        except (TypeError, ValueError):
            pass

    def value(self, key, default=None):
        return self.data.get(key, default)

    def setValue(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)
