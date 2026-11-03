#!/usr/bin/env python3
"""Steezy Studio's window: one tile per tool, open it, see its version.

Same shape as the other tools: pywebview shows ui/index.html and hands the
page this Api object. Every method returns plain data and none of them raises;
a problem with one tool is a message on its tile.

Run it with:  python3 -m studio.gui
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

from studio import registry

UI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "index.html")
APP_NAME = "Steezy Studio"
WINDOW_SIZE = (760, 640)
APP_DIRS = (os.path.expanduser("~/Applications"), "/Applications")


def _git(path: str, *args: str) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def version_of(path: str) -> dict:
    """Short commit, its date, whether the folder has local changes, and how
    many commits the last-fetched upstream is ahead (None if unknown). Offline."""
    sha = _git(path, "rev-parse", "--short", "HEAD")
    if sha is None:
        return {"sha": None, "date": None, "dirty": False, "behind": None}
    date = _git(path, "log", "-1", "--format=%cs") or ""
    dirty = bool(_git(path, "status", "--porcelain"))
    behind = _git(path, "rev-list", "--count", "HEAD..@{u}")
    return {"sha": sha, "date": date, "dirty": dirty, "behind": int(behind) if behind and behind.isdigit() else None}


def find_app(app_name: str, dirs=APP_DIRS) -> Optional[str]:
    for d in dirs:
        p = os.path.join(d, app_name)
        if os.path.isdir(p):
            return p
    return None


class Api:
    def __init__(self, registry_path: Optional[str] = None, root: Optional[str] = None, app_dirs=APP_DIRS):
        self._registry_path, self._root, self._app_dirs = registry_path, root, app_dirs

    def _tools(self):
        return registry.load_tools(self._registry_path, self._root)

    def list_tools(self) -> list:
        out = []
        for t in self._tools():
            item = {"id": t.id, "name": t.name, "state": t.state, "message": t.message,
                    "usable": t.usable, "version": None, "dirty": False, "behind": None, "app": None}
            if t.usable:
                item.update(version_of(t.path), app=find_app(t.app, self._app_dirs))
                item["version"] = item.pop("sha")
            out.append(item)
        return out

    def open_tool(self, tool_id: str) -> dict:
        for t in self._tools():
            if t.id != tool_id:
                continue
            if not t.usable:
                return {"ok": False, "message": t.message}
            app = find_app(t.app, self._app_dirs)
            if not app:
                return {"ok": False, "message": "%s hasn't been built yet. Press Update to build it." % t.name}
            try:
                subprocess.Popen(["open", app])
            except OSError as e:
                return {"ok": False, "message": "Couldn't open %s: %s" % (t.name, e)}
            return {"ok": True, "message": ""}
        return {"ok": False, "message": "Steezy Studio doesn't know that tool."}


def main():
    import webview  # imported here so the Api above stays testable without it

    api = Api()
    webview.create_window(APP_NAME, UI_FILE, js_api=api, width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
                          min_size=(520, 420))
    webview.start()


if __name__ == "__main__":
    main()
