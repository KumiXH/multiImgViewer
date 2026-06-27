from __future__ import annotations

import sys
from pathlib import Path


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def app_data_dir() -> Path:
    return application_root() / ".remote_image_compare"
