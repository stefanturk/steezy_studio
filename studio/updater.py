"""Update all: for each tool, fetch, fast-forward, refresh packages, rebuild.

The rules, learned from Beat Thief's update.sh:
  * only ever `git pull --ff-only`; a folder with local changes, local
    commits, or a diverged history is left exactly as it is and the reason is
    reported, never clobbered;
  * one tool failing (no network, build error) never stops the others;
  * rebuild only when something changed or the app is missing.

Nothing here raises. Every outcome is a Result.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

from studio import platform_paths, registry

UPDATED = "updated"
UP_TO_DATE = "up_to_date"
SKIPPED_DIRTY = "skipped_dirty"
SKIPPED_AHEAD = "skipped_ahead"
SKIPPED_DIVERGED = "skipped_diverged"
NO_NETWORK = "no_network"
BUILD_FAILED = "build_failed"
UNAVAILABLE = "unavailable"
WOULD_UPDATE = "would_update"      # dry run only


@dataclass
class Result:
    id: str
    name: str
    status: str
    message: str = ""


def _run(cmd: list, cwd: str, timeout: int = 1800, env: Optional[dict] = None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
                           **platform_paths.no_window())
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except OSError as e:
        return 127, str(e)


def _git(path: str, *args: str, timeout: int = 60):
    return _run(["git", *args], path, timeout)


def engine_python() -> Optional[str]:
    p = os.environ.get("STEEZY_PYTHON")
    if not p:
        p = platform_paths.python_in(platform_paths.engine_dir())
    return p if os.access(p, os.X_OK) else None


def default_refresh(tool: registry.Tool) -> tuple:
    """pip-install the tool's packages into the engine Python. On a Mac that is
    requirements.txt (the build script does the rest); on Windows there is no
    build step, so it is every file in windows_requirements, then `pip install
    -e .` if the tool asks for it. (True, message) on success."""
    py = engine_python()
    if not py:
        return True, "no engine Python, so no packages to refresh"
    pip = [py, "-m", "pip", "install", "--quiet", "--prefer-binary", "--upgrade"]
    steps = []
    files = (tool.windows_requirements or ["requirements.txt"]) if platform_paths.is_windows() else ["requirements.txt"]
    for name in files:
        if os.path.exists(os.path.join(tool.path, name)):
            steps.append(pip + ["-r", name])
    if platform_paths.is_windows() and tool.windows_pip_editable:
        steps.append(pip + ["-e", "."])
    if not steps:
        return True, "no packages to refresh"
    for cmd in steps:
        code, out = _run(cmd, tool.path, timeout=3600)
        if code != 0:
            return False, out[-400:]
    return True, "packages up to date"


def windows_shortcut(tool: registry.Tool) -> tuple:
    """Start-menu shortcut that runs the tool with the engine's pythonw, the
    same one install.ps1 makes, with the tool's icon.ico when its repo has
    one. Skipped when STEEZY_SKIP_SHORTCUTS=1."""
    if os.environ.get("STEEZY_SKIP_SHORTCUTS") == "1" or not tool.windows_run:
        return True, "no shortcut"
    pyw = platform_paths.python_in(platform_paths.engine_dir(), windowed=True)
    args = subprocess.list2cmdline(tool.windows_run)
    ps = ("$d = Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs'; "
          "$l = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d ($env:SZ_NAME + '.lnk'))); "
          "$l.TargetPath = $env:SZ_TARGET; $l.Arguments = $env:SZ_ARGS; $l.WorkingDirectory = $env:SZ_DIR; "
          "if ($env:SZ_ICON) { $l.IconLocation = $env:SZ_ICON + ',0' }; $l.Save()")
    ico = os.path.join(tool.path, "icon.ico")
    env = dict(os.environ, SZ_NAME=tool.name, SZ_TARGET=pyw, SZ_ARGS=args, SZ_DIR=tool.path,
               SZ_ICON=ico if os.path.exists(ico) else "")
    code, out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], tool.path, timeout=60, env=env)
    return code == 0, out[-400:]


def default_build(tool: registry.Tool) -> tuple:
    if platform_paths.is_windows():
        # Tools run from source; the only "build" is the Start-menu shortcut.
        ok, out = windows_shortcut(tool)
        return True, "nothing to build on Windows" + ("" if ok else " (couldn't make the Start-menu shortcut: %s)" % out)
    env = dict(os.environ)
    py = engine_python()
    if py:
        env["PYTHON"] = py
    code, out = _run(tool.build, tool.path, env=env)
    return code == 0, out[-400:]


def update_tool(tool: registry.Tool, *, fetch: bool = True, dry_run: bool = False,
                refresh: Callable = default_refresh, build: Callable = default_build,
                app_exists: Callable[[registry.Tool], bool] = lambda t: True) -> Result:
    r = lambda status, msg="": Result(tool.id, tool.name, status, msg)
    if not tool.usable:
        return r(UNAVAILABLE, tool.message)

    if fetch and not dry_run:
        code, out = _git(tool.path, "fetch", "--quiet")
        if code != 0:
            return r(NO_NETWORK, "Couldn't reach GitHub, so %s was left as it is." % tool.name)

    dirty = bool(_git(tool.path, "status", "--porcelain")[1])
    counts = _git(tool.path, "rev-list", "--left-right", "--count", "HEAD...@{u}")
    if counts[0] != 0:
        return r(UP_TO_DATE, "No upstream to compare with.")
    ahead, behind = (int(x) for x in counts[1].split())

    if behind and ahead:
        return r(SKIPPED_DIVERGED, "%s has its own commits and GitHub has new ones. Left alone." % tool.name)
    if behind and dirty:
        return r(SKIPPED_DIRTY, "%s has changes that aren't saved to git, so the update was skipped." % tool.name)
    if not behind:
        if ahead:
            return r(SKIPPED_AHEAD, "%s has commits that aren't on GitHub yet. Nothing to update." % tool.name)
        if app_exists(tool):
            return r(UP_TO_DATE, "Already the latest.")
        # Up to date but never built: fall through to build.
    if dry_run:
        return r(WOULD_UPDATE, "%d new commit(s) would be pulled." % behind if behind else "Would build the app.")

    if behind:
        code, out = _git(tool.path, "pull", "--ff-only", "--quiet", timeout=300)
        if code != 0:
            return r(SKIPPED_DIVERGED, "Couldn't fast-forward %s. Left alone. (%s)" % (tool.name, out[-200:]))
    ok, out = refresh(tool)
    if not ok:
        return r(BUILD_FAILED, "Updated the code but couldn't refresh packages. %s" % out)
    ok, out = build(tool)
    if not ok:
        return r(BUILD_FAILED, "Updated the code but the rebuild failed, so the old app is still there. %s" % out)
    return r(UPDATED, "Updated and rebuilt." if behind else "Built.")


def fetch_quietly(tools: list) -> None:
    """git fetch each usable tool so "newer" counts are real. Never raises."""
    for t in tools:
        if t.usable:
            _git(t.path, "fetch", "--quiet")


def update_all(tools: list, on_result: Optional[Callable[[Result], None]] = None,
               on_start: Optional[Callable[[registry.Tool], None]] = None, **kw) -> list:
    results = []
    studio = kw.pop("studio", None)
    for t in list(tools) + ([studio] if studio else []):
        if on_start:
            on_start(t)
        try:
            res = update_tool(t, **kw)
            if t is studio and res.status == UPDATED:
                res.message = "Steezy Studio itself was updated. Quit and reopen it to use the new version."
        except Exception as e:  # last line of defence: one tool never stops the rest
            res = Result(t.id, t.name, BUILD_FAILED, "Unexpected problem: %s" % e)
        results.append(res)
        if on_result:
            on_result(res)
    return results
