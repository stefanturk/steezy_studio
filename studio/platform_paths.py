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


def use_private_git(environ=None) -> bool:
    """Windows without Git: install.ps1 may have put a private MinGit in the
    engine folder. Put it on this process's PATH so `git` works for every
    update and install. True when it was added."""
    environ = os.environ if environ is None else environ
    if not is_windows():
        return False
    cmd = os.path.join(engine_dir(), "mingit", "cmd")
    if not os.path.exists(os.path.join(cmd, "git.exe")):
        return False
    path = environ.get("PATH", "")
    if cmd.lower() in (p.lower() for p in path.split(";")):
        return False
    environ["PATH"] = cmd + (";" + path if path else "")
    return True


def python_in(engine: str, windowed: bool = False) -> str:
    if is_windows():
        return ntpath.join(engine, "python", "pythonw.exe" if windowed else "python.exe")
    return posixpath.join(engine, "python", "bin", "python3")


def songs_only() -> bool:
    """True when this computer was set up without Beat Thief's instrument splitter
    (install.sh --songs-only): the Studio then leaves its 2GB of packages out of
    installs and updates. STEEZY_SONGS_ONLY=1 or a `songs_only` file next to the
    engine folder; delete the file to get the splitter on the next Update all."""
    if os.environ.get("STEEZY_SONGS_ONLY") == "1":
        return True
    return os.path.exists(os.path.join(os.path.dirname(engine_dir()), "songs_only"))


def apps_dir() -> str:
    """Where a Mac app gets built: the main /Applications folder (where people
    look for apps and where Launchpad shows them) when this user can write to
    it, which an admin account can, else the ~/Applications in their home folder.
    STEEZY_APPS_DIR overrides it (tests, and anyone who wants it elsewhere)."""
    d = os.environ.get("STEEZY_APPS_DIR")
    if d:
        return d
    if os.access("/Applications", os.W_OK):
        return "/Applications"
    return os.path.expanduser("~/Applications")


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
