"""Where the engine lives and which interpreter to use, per operating system.

Everything reads sys.platform at call time so tests can pretend to be Windows.
"""
from __future__ import annotations

import os
import sys


def is_windows() -> bool:
    return sys.platform.startswith("win")


def engine_dir() -> str:
    env = os.environ.get("STEEZY_ENGINE_DIR")
    if env:
        return env
    if is_windows():
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local"),
                            "Steezy Studio", "engine")
    return os.path.expanduser("~/Library/Application Support/Steezy Studio/engine")


def python_in(engine: str, windowed: bool = False) -> str:
    if is_windows():
        return os.path.join(engine, "python", "pythonw.exe" if windowed else "python.exe")
    return os.path.join(engine, "python", "bin", "python3")
