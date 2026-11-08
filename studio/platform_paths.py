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


def windows_app_identity(app_id: str) -> None:
    """Its own taskbar group on Windows, rather than Python's (see set_window_icon)."""
    if not is_windows():
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Steezy." + app_id)
    except Exception:
        pass


def set_window_icon(title: str, ico_path: str) -> bool:
    """Put ico_path on the top-level window called title, so the window and
    its taskbar button wear the app's icon instead of Python's. Windows only."""
    if not is_windows() or not os.path.exists(ico_path):
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return False
        for which, size in ((1, 0), (0, 16)):        # ICON_BIG, ICON_SMALL
            icon = user32.LoadImageW(None, ico_path, 1, size, size, 0x10 | (0x40 if size == 0 else 0))
            if icon:
                user32.SendMessageW(hwnd, 0x80, which, icon)   # WM_SETICON
        return True
    except Exception:
        return False
