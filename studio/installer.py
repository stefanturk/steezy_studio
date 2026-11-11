"""Install a tool from inside Steezy Studio: the Install button.

It is the same thing install.ps1 / install.sh do for a named tool: clone it
into the tools folder, then run the normal update path, which (with nothing to
pull) refreshes packages and builds: make_app.sh on a Mac, the Start-menu
shortcut on Windows. Nothing here raises; every outcome is an updater.Result.
"""
from __future__ import annotations

import os
import shutil
import stat
from typing import Callable

from studio import registry, updater

INSTALLED = "installed"
INSTALL_FAILED = "install_failed"
UNSUPPORTED = "unsupported"


def clone_url(tool: registry.Tool) -> str:
    """STEEZY_REPO_BASE (a folder of local repos) is the test hook, as in install.sh."""
    base = os.environ.get("STEEZY_REPO_BASE")
    if base:
        return os.path.join(base, os.path.splitext(os.path.basename(tool.repo.rstrip("/")))[0])
    return tool.repo


def default_clone(tool: registry.Tool) -> tuple:
    parent = os.path.dirname(tool.path)
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as e:
        return False, str(e)
    code, out = updater._run(["git", "clone", "--depth", "1", clone_url(tool), tool.path], parent, timeout=900)
    return code == 0, out[-400:]


def _remove_clone(path: str) -> None:
    """Undo a half install so the tile goes back to Install. git marks its
    object files read-only, which stops rmtree on Windows, hence the chmod."""
    def again(func, p, _):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=again)


def install_tool(tool: registry.Tool, *, clone: Callable = default_clone,
                 refresh: Callable = updater.default_refresh, build: Callable = updater.default_build) -> updater.Result:
    r = lambda status, msg="": updater.Result(tool.id, tool.name, status, msg)
    if tool.state == registry.UNSUPPORTED:
        return r(UNSUPPORTED, tool.message)
    if tool.state == registry.READY:
        return r(INSTALLED, "%s is already installed." % tool.name)
    if tool.state not in (registry.NOT_INSTALLED, registry.NO_ACCESS):
        return r(INSTALL_FAILED, tool.message)

    updater._phase("Downloading")
    ok, out = clone(tool)
    if not ok or not os.path.isdir(os.path.join(tool.path, ".git")):
        if tool.private:
            return r(INSTALL_FAILED, "%s is private. Ask Stefan to invite your GitHub account, then try again." % tool.name)
        return r(INSTALL_FAILED, "Couldn't download %s. Check your internet and try again. (%s)" % (tool.name, out[-200:]))

    # A half install is taken back out, so the tile shows Install again and a
    # retry starts clean (Update all would think it was finished).
    updater._phase(updater.PHASE_PACKAGES)
    ok, out = refresh(tool)
    if not ok:
        _remove_clone(tool.path)
        return r(INSTALL_FAILED, "Some of %s's packages didn't install, so nothing was kept. Press Install to try again. (%s)"
                 % (tool.name, out[-200:]))
    updater._phase("Building the app")
    ok, out = build(tool)
    if not ok:
        _remove_clone(tool.path)
        return r(INSTALL_FAILED, "%s didn't build, so nothing was kept. Press Install to try again. (%s)"
                 % (tool.name, out[-200:]))
    return r(INSTALLED, "%s is installed." % tool.name)
