"""Where the engine lives and which interpreter to use, per operating system.

Everything reads sys.platform at call time so tests can pretend to be Windows.
"""
from __future__ import annotations

import ntpath
import os
import posixpath
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
        return ntpath.join(engine, "python", "pythonw.exe" if windowed else "python.exe")
    return posixpath.join(engine, "python", "bin", "python3")


def os_name() -> str:
    """The registry's word for this OS: "windows" or "mac"."""
    return "windows" if is_windows() else "mac"


def no_window() -> dict:
    """subprocess kwargs that stop a console window flashing up for each git or
    pip call when the Studio runs under pythonw on Windows. Empty elsewhere."""
    if is_windows():
        import subprocess
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}
