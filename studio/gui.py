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
import threading
from typing import Optional

import sys

from studio import installer, invite, platform_paths, registry, share, updater

UI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "index.html")
APP_NAME = "Steezy Studio"
WINDOW_SIZE = (760, 640)
APP_DIRS = (os.path.expanduser("~/Applications"), "/Applications")


def _git(path: str, *args: str) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=10,
                           **platform_paths.no_window())
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


def app_for(t, app_dirs=APP_DIRS) -> Optional[str]:
    """Where the tool can be started from: the built .app on a Mac; on Windows the
    source folder, if the registry says how to run it."""
    if platform_paths.is_windows():
        return t.path if t.windows_run else None
    return find_app(t.app, app_dirs)


class Api:
    def __init__(self, registry_path: Optional[str] = None, root: Optional[str] = None, app_dirs=APP_DIRS):
        self._registry_path, self._root, self._app_dirs = registry_path, root, app_dirs
        self._lock = threading.Lock()
        self._running = False
        self._results: list = []
        self._update_kw: dict = {}      # tests inject refresh/build here
        self._studio_tool = None        # tests inject the Studio's own clone here
        self._install_kw: dict = {}     # tests inject clone/refresh/build here
        self._installing: Optional[str] = None
        self._working_on: Optional[str] = None   # the tool an update is on right now
        self._queued: set = set()                # tools an update hasn't reached yet

    def _tools(self):
        return registry.load_tools(self._registry_path, self._root)

    def list_tools(self) -> list:
        out = []
        for t in self._tools():
            item = {"id": t.id, "name": t.name, "state": t.state, "message": t.message,
                    "usable": t.usable, "version": None, "dirty": False, "behind": None, "app": None,
                    "installable": t.state in (registry.NOT_INSTALLED, registry.NO_ACCESS),
                    "installing": self._installing == t.id,
                    "updating": self._working_on == t.id, "waiting": t.id in self._queued,
                    "openable": False}
            if t.usable:
                item.update(version_of(t.path), app=app_for(t, self._app_dirs))
                item["version"] = item.pop("sha")
                # Open only once the tool is really there: not mid-install,
                # mid-update or still waiting its turn to update.
                item["openable"] = bool(item["app"]) and not (
                    item["installing"] or item["updating"] or item["waiting"])
            out.append(item)
        return out

    def needs_update(self) -> bool:
        """Whether anything is behind GitHub, or cloned but never built - what
        the page checks on launch to decide to update on its own."""
        st = self._studio()
        for t in self._tools() + ([st] if st else []):
            if not t.usable:
                continue
            if (version_of(t.path)["behind"] or 0) > 0:
                return True
            if t is not st and app_for(t, self._app_dirs) is None:
                return True
        return False

    def check_updates(self) -> dict:
        """Fetch every tool and the Studio itself (slow, so the page calls this
        after it has drawn), then say how far behind the Studio is."""
        st = self._studio()
        updater.fetch_quietly(self._tools() + ([st] if st else []))
        return dict(self.studio_status(), update_needed=self.needs_update())

    def _studio(self):
        return self._studio_tool or registry.studio_tool()

    def studio_status(self) -> dict:
        st = self._studio()
        if not st:
            return {"known": False, "behind": None}
        v = version_of(st.path)
        return {"known": True, "behind": v["behind"], "dirty": v["dirty"]}

    def open_tool(self, tool_id: str) -> dict:
        for t in self._tools():
            if t.id != tool_id:
                continue
            if not t.usable:
                return {"ok": False, "message": t.message}
            app = app_for(t, self._app_dirs)
            if not app:
                return {"ok": False, "message": "%s hasn't been built yet. Press Update to build it." % t.name}
            try:
                if platform_paths.is_windows():
                    py = platform_paths.python_in(platform_paths.engine_dir(), windowed=True)
                    subprocess.Popen([py, *t.windows_run], cwd=t.path)
                else:
                    subprocess.Popen(["open", app])
            except OSError as e:
                return {"ok": False, "message": "Couldn't open %s: %s" % (t.name, e)}
            return {"ok": True, "message": ""}
        return {"ok": False, "message": "Steezy Studio doesn't know that tool."}


    # ---- Share with friends
    def share_options(self) -> dict:
        return share.share_options(self._tools())

    def copy_text(self, text: str) -> dict:
        """Put text on the clipboard. The page falls back to its own copy if this says no."""
        cmd = ["clip"] if sys.platform.startswith("win") else ["pbcopy"]
        try:
            subprocess.run(cmd, input=str(text), text=True, timeout=5, check=True, **platform_paths.no_window())
        except (OSError, subprocess.SubprocessError):
            return {"ok": False}
        return {"ok": True}

    def invite_friend(self, username: str, tool_ids=None) -> list:
        """Really sends GitHub invites (the page asks Stefan to confirm first)."""
        return invite.invite(str(username or "").strip(), list(tool_ids or []) or None, send=True,
                             tools=self._tools())

    # ---- Update all: runs on a worker thread, the page polls update_status().
    def update_all(self) -> dict:
        with self._lock:
            if self._running:
                return {"started": False}
            self._running, self._results = True, []
        threading.Thread(target=self._do_update, daemon=True).start()
        return {"started": True}

    # A tool that couldn't update still opens, at the version it has.
    _KEEPS_OLD = (updater.NO_NETWORK, updater.SKIPPED_DIRTY, updater.SKIPPED_AHEAD,
                  updater.SKIPPED_DIVERGED, updater.BUILD_FAILED)

    def _do_update(self):
        tools, studio = self._tools(), self._studio()
        self._queued = {t.id for t in tools + ([studio] if studio else []) if t.usable}

        def started(t):
            self._queued.discard(t.id)
            self._working_on = t.id

        def finished(r):
            if r.status in self._KEEPS_OLD and r.id != "studio":
                r.message += " You can still open the version you have."
            self._working_on = None
            self._results.append(r.__dict__)

        try:
            updater.update_all(
                tools, on_result=finished, on_start=started,
                app_exists=lambda t: t.id == "studio" or app_for(t, self._app_dirs) is not None,
                studio=studio,
                **self._update_kw)
        finally:
            self._working_on, self._queued = None, set()
            self._running = False

    def update_status(self) -> dict:
        return {"running": self._running, "results": list(self._results), "installing": self._installing}

    # ---- Install one tool: same worker and polling as Update all, so only one
    # of the two runs at a time and a 2GB download never freezes the window.
    def install_tool(self, tool_id: str) -> dict:
        tool = next((t for t in self._tools() if t.id == tool_id), None)
        if tool is None:
            return {"started": False, "message": "Steezy Studio doesn't know that tool."}
        with self._lock:
            if self._running:
                return {"started": False, "message": "Wait for the current update or install to finish."}
            self._running, self._results, self._installing = True, [], tool.id
        threading.Thread(target=self._do_install, args=(tool,), daemon=True).start()
        return {"started": True, "message": ""}

    def _do_install(self, tool):
        try:
            try:
                res = installer.install_tool(tool, **self._install_kw)
            except Exception as e:  # never leave the page spinning
                res = updater.Result(tool.id, tool.name, installer.INSTALL_FAILED, "Unexpected problem: %s" % e)
            self._results.append(res.__dict__)
        finally:
            self._installing = None
            self._running = False


def main():
    import webview  # imported here so the Api above stays testable without it

    api = Api()
    platform_paths.windows_app_identity("studio")
    platform_paths.use_private_git()
    window = webview.create_window(APP_NAME, UI_FILE, js_api=api, width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
                                   min_size=(520, 420))
    ico = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico")
    window.events.shown += lambda: platform_paths.set_window_icon(APP_NAME, ico)
    webview.start()


if __name__ == "__main__":
    main()
