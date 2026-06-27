from __future__ import annotations

import json
from pathlib import Path

from remote_image_compare.services.runtime_paths import app_data_dir


def default_window_state_store_path() -> Path:
    return app_data_dir() / "window_state.json"


class WindowStateStore:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = (
            Path(storage_path) if storage_path is not None else default_window_state_store_path()
        )

    def load_window_size(self, window_key: str) -> tuple[int, int] | None:
        payload = self._read_payload()
        window_payload = payload.get("windows", {}).get(window_key)
        if not isinstance(window_payload, dict):
            return None
        width = window_payload.get("width")
        height = window_payload.get("height")
        if not isinstance(width, int) or not isinstance(height, int):
            return None
        return (width, height)

    def save_window_size(self, window_key: str, width: int, height: int) -> None:
        payload = self._read_payload()
        windows = payload.setdefault("windows", {})
        window_payload = windows.setdefault(window_key, {})
        window_payload["width"] = int(width)
        window_payload["height"] = int(height)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_window_position(self, window_key: str) -> tuple[int, int] | None:
        payload = self._read_payload()
        window_payload = payload.get("windows", {}).get(window_key)
        if not isinstance(window_payload, dict):
            return None
        x = window_payload.get("x")
        y = window_payload.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            return None
        return (x, y)

    def save_window_position(self, window_key: str, x: int, y: int) -> None:
        payload = self._read_payload()
        windows = payload.setdefault("windows", {})
        window_payload = windows.setdefault(window_key, {})
        window_payload["x"] = int(x)
        window_payload["y"] = int(y)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _read_payload(self) -> dict:
        if not self.storage_path.exists():
            return {"version": 1, "windows": {}}
        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"version": 1, "windows": {}}
        payload.setdefault("version", 1)
        payload.setdefault("windows", {})
        return payload
