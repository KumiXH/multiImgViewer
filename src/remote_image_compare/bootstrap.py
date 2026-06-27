from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_frozen_windows_dll_paths(
    *,
    base_dir: Path | None = None,
    is_windows: bool | None = None,
    add_dll_directory=None,
    environment: dict[str, str] | None = None,
) -> list[Path]:
    if is_windows is None:
        is_windows = sys.platform.startswith("win")
    if not is_windows:
        return []

    if base_dir is None:
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    if add_dll_directory is None:
        add_dll_directory = os.add_dll_directory
    if environment is None:
        environment = os.environ

    candidates = [
        Path(base_dir) / "PySide6",
        Path(base_dir) / "shiboken6",
    ]
    configured: list[Path] = []
    for directory in candidates:
        if not directory.is_dir():
            continue
        add_dll_directory(str(directory))
        configured.append(directory)

    if configured:
        path_parts = [str(path) for path in configured]
        current_path = environment.get("PATH", "")
        environment["PATH"] = os.pathsep.join([*path_parts, current_path]) if current_path else os.pathsep.join(path_parts)

    return configured
