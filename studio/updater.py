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
import shutil
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
SKIPPED_OPEN = "skipped_open"      # opened while it waited its turn
GIT_PROBLEM = "git_problem"        # git itself failed (not network, not local changes)
UNSIGNED = "unsigned"              # the new commit isn't signed by a trusted key: left on GitHub


@dataclass
class Result:
    id: str
    name: str
    status: str
    message: str = ""


phase_hook: Optional[Callable[[str], None]] = None   # the Studio's window sets this to show what it's doing


def _phase(text: str) -> None:
    if phase_hook:
        try:
            phase_hook(text)
        except Exception:
            pass


PHASE_PACKAGES = "Installing packages (the big ones take a while)"


def _run(cmd: list, cwd: str, timeout: int = 1800, env: Optional[dict] = None, merge: bool = True):
    """(exit code, output). merge=False returns stdout only, for output that gets parsed, so a
    warning on stderr can't be mistaken for it. Never asks for a password (a private repo without
    access fails at once instead of waiting on a prompt nobody sees), and odd bytes never raise."""
    # Windows without Git: install.ps1's private MinGit goes on PATH. For every command, not just
    # `git`, because pip installs packages straight from GitHub (music-detector) and runs git itself.
    platform_paths.use_private_git()
    env = dict(os.environ if env is None else env, GIT_TERMINAL_PROMPT="0")
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=env, stdin=subprocess.DEVNULL, **platform_paths.no_window())
        return r.returncode, (r.stdout if not merge else r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except OSError as e:
        return 127, str(e)


def _git(path: str, *args: str, timeout: int = 60, merge: bool = True):
    return _run(["git", *args], path, timeout, merge=merge)


def _last_line(out: str) -> str:
    """The line of git's output worth showing: its first fatal/error line (the rest is boilerplate
    like "Please make sure you have the correct access rights"), else the last line."""
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    for l in lines:
        if l.startswith(("fatal:", "error:")):
            return l[:200]
    return lines[-1][:200] if lines else ""


def engine_python() -> Optional[str]:
    p = os.environ.get("STEEZY_PYTHON")
    if not p:
        p = platform_paths.python_in(platform_paths.engine_dir())
    return p if os.access(p, os.X_OK) else None


def constraint_args() -> list:
    """["-c", <engine>/constraints.txt] so pip can't move a shared package off
    the pinned set. The engine's copy is refreshed from the Studio clone each
    time (that is how a changed pin reaches tools whose build scripts only know
    the engine folder); with neither, no constraint rather than a failed install."""
    dest = os.path.join(platform_paths.engine_dir(), "constraints.txt")
    st = registry.studio_path()
    src = os.path.join(st, "constraints.txt") if st else ""
    try:
        if src and os.path.exists(src):
            with open(src, "rb") as f:
                want = f.read()
            have = None
            if os.path.exists(dest):
                with open(dest, "rb") as f:
                    have = f.read()
            if want != have:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(want)
    except OSError:
        pass
    return ["-c", dest] if os.path.exists(dest) else []


def requirement_files(tool: registry.Tool) -> list:
    """The requirement files to install for this tool: its list, minus the
    instrument splitter's when this computer was set up songs-only."""
    files = list(tool.windows_requirements or ["requirements.txt"])
    if platform_paths.songs_only():
        files = [f for f in files if "splitter" not in f]
    return files


# PyPI's Windows torch is the processor-only build, so an NVIDIA card would sit unused. PyTorch's
# own CUDA 12.1 wheels (same version numbers, "+cu121") work with any driver from 2023 on and fall
# back to the processor if the driver is older. Only used when nvidia-smi says there is a card.
CUDA_INDEX = "https://download.pytorch.org/whl/cu121"


def cuda_index_args(requirements_file: str) -> list:
    if "splitter" in requirements_file and platform_paths.is_windows() and shutil.which("nvidia-smi"):
        return ["--extra-index-url", CUDA_INDEX]
    return []


def default_refresh(tool: registry.Tool) -> tuple:
    """pip-install the tool's packages into the engine Python: every file in the
    tool's requirements list (so Beat Thief gets its instrument splitter on a Mac
    too), then, on Windows only, `pip install -e .` if the tool asks for it.
    (True, message) on success."""
    py = engine_python()
    if not py:
        return True, "no engine Python, so no packages to refresh"
    # --no-warn-script-location: the engine's Scripts folder is never on PATH and
    # needn't be (tools run as `python -m`), so pip's PATH warning is only noise.
    pip = [py, "-m", "pip", "install", "--quiet", "--prefer-binary", "--upgrade", "--no-warn-script-location"]
    pip += constraint_args()
    steps = []
    for name in requirement_files(tool):
        if os.path.exists(os.path.join(tool.path, name)):
            steps.append(pip + cuda_index_args(name) + ["-r", name])
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
    dest = platform_paths.apps_dir()
    studio = registry.studio_path()
    if studio and os.path.isfile(os.path.join(studio, "build", "lib.sh")):
        env["STEEZY_BUILD"] = os.path.join(studio, "build")     # shared icon / destination helpers
    code, out = _run(list(tool.build) + [dest], tool.path, env=env)
    if code == 0:
        _remove_old_copy(tool, dest)
    return code == 0, out[-400:]


def _remove_old_copy(tool: registry.Tool, dest: str) -> None:
    """Earlier builds went into ~/Applications. Now the app is in `dest`, a second
    copy there would sit beside it, and the Dock stays pinned to whichever one it
    was dragged from, so the old one goes."""
    old = os.path.join(os.path.expanduser("~/Applications"), tool.app)
    if os.path.abspath(os.path.dirname(old)) != os.path.abspath(dest) and os.path.isdir(old) \
            and os.path.isdir(os.path.join(dest, tool.app)):
        _repin_dock(old, os.path.join(dest, tool.app))
        shutil.rmtree(old, ignore_errors=True)


def _repin_dock(old: str, new: str) -> None:
    """Point a Dock pin of the old copy at the new one before the old one goes, or the pin turns
    into a question mark. Mac only; never raises."""
    if platform_paths.is_windows() or os.environ.get("STEEZY_SKIP_DOCK") == "1":
        return
    try:
        script = os.path.join(registry.studio_path() or "", "build", "dock_repin.py")
        if os.path.isfile(script):
            subprocess.run(["/usr/bin/python3", script, old, new], capture_output=True, timeout=30)
    except Exception:
        pass


def _requirements_stamp(tool: registry.Tool) -> str:
    """Where we note which requirement files a tool's packages were last installed from."""
    return os.path.join(platform_paths.engine_dir(), "refreshed", tool.id + ".sha")


def _requirements_hash(tool: registry.Tool) -> str:
    import hashlib
    h = hashlib.sha256()
    for name in requirement_files(tool):
        try:
            with open(os.path.join(tool.path, name), "rb") as f:
                h.update(name.encode() + b"\0" + f.read())
        except OSError:
            pass
    st = registry.studio_path()            # the shared pins: a changed pin must reach every tool
    if st:
        try:
            with open(os.path.join(st, "constraints.txt"), "rb") as f:
                h.update(b"constraints\0" + f.read())
        except OSError:
            pass
    return h.hexdigest()


def _packages_stale(tool: registry.Tool) -> bool:
    """True when the tool's requirement files differ from what was last installed
    (or nothing was recorded, e.g. installs made before this check existed)."""
    if not engine_python():
        return False
    try:
        with open(_requirements_stamp(tool)) as f:
            return f.read().strip() != _requirements_hash(tool)
    except OSError:
        return True


def _record_packages(tool: registry.Tool) -> None:
    try:
        p = _requirements_stamp(tool)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(_requirements_hash(tool))
    except OSError:
        pass


def _build_stamp(tool: registry.Tool) -> str:
    return os.path.join(platform_paths.engine_dir(), "refreshed", tool.id + ".buildfail")


def _head(tool: registry.Tool) -> Optional[str]:
    code, out = _git(tool.path, "rev-parse", "HEAD", merge=False)
    return out if code == 0 and out else None


def build_failed_at(tool: registry.Tool) -> Optional[str]:
    """The commit this tool's last build failed at, or None. A launch doesn't retry a build that
    failed at the same code (it would only fail again, for minutes, every time); new code, or
    pressing Update, does."""
    try:
        with open(_build_stamp(tool)) as f:
            return f.read().strip() or None
    except OSError:
        return None


def _record_build_failure(tool: registry.Tool) -> None:
    try:
        p = _build_stamp(tool)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(_head(tool) or "")
    except OSError:
        pass


def _clear_build_failure(tool: registry.Tool) -> None:
    try:
        os.remove(_build_stamp(tool))
    except OSError:
        pass


def signers_file() -> Optional[str]:
    """The keys an update must be signed by: allowed_signers beside the running Studio's own code (in the app
    bundle, or the source folder on Windows). Never the copy being downloaded, so changing who is trusted
    takes an update that is itself signed by someone already trusted."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allowed_signers")
    return p if os.path.isfile(p) else None


def verify_upstream(tool: registry.Tool) -> tuple:
    """(ok, why) for the newest commit on GitHub (@{u}): signed by a trusted key? Only that commit is
    checked, because its signature covers all the history under it.
    Windows without ssh-keygen (the private MinGit has none) can't check and lets it through, saying so."""
    if os.environ.get("STEEZY_SKIP_SIGNATURE_CHECK") == "1":
        return True, ""
    f = signers_file()
    if not f:
        return False, "this copy of Steezy Studio has no list of trusted signers"
    if not shutil.which("ssh-keygen"):
        return True, "not checked (no ssh-keygen on this computer)"
    code, out = _git(tool.path, "-c", "gpg.format=ssh", "-c", "gpg.ssh.allowedSignersFile=" + f,
                     "verify-commit", "@{u}")
    return code == 0, _last_line(out)


def update_tool(tool: registry.Tool, *, fetch: bool = True, dry_run: bool = False,
                refresh: Callable = default_refresh, build: Callable = default_build,
                app_exists: Callable[[registry.Tool], bool] = lambda t: True) -> Result:
    r = lambda status, msg="": Result(tool.id, tool.name, status, msg)
    if not tool.usable:
        return r(UNAVAILABLE, tool.message)

    if fetch and not dry_run:
        _phase("Checking for updates")
        code, out = _git(tool.path, "fetch", "--quiet")
        if code != 0:
            why = _last_line(out)
            return r(NO_NETWORK, "Couldn't reach GitHub, so %s was left as it is.%s"
                     % (tool.name, " (git: %s)" % why if why else ""))

    # Untracked files don't count: only edits to files git knows would be at risk from a pull.
    code, out = _git(tool.path, "status", "--porcelain", "--untracked-files=no", merge=False)
    if code != 0:
        return r(GIT_PROBLEM, "git couldn't read %s's folder, so it was left as it is. (git: %s)"
                 % (tool.name, _last_line(out) or "exit %d" % code))
    dirty = bool(out)
    counts = _git(tool.path, "rev-list", "--left-right", "--count", "HEAD...@{u}", merge=False)
    if counts[0] != 0:
        return r(UP_TO_DATE, "No upstream to compare with.")
    try:
        ahead, behind = (int(x) for x in counts[1].split())
    except ValueError:
        return r(GIT_PROBLEM, "git gave an answer Steezy Studio didn't understand for %s: %s"
                 % (tool.name, _last_line(counts[1])))

    if behind and ahead:
        return r(SKIPPED_DIVERGED, "%s has its own commits and GitHub has new ones. Left alone." % tool.name)
    if behind and dirty:
        return r(SKIPPED_DIRTY, "%s has changes that aren't saved to git, so the update was skipped." % tool.name)
    if not behind:
        if ahead:
            return r(SKIPPED_AHEAD, "%s has commits that aren't on GitHub yet. Nothing to update." % tool.name)
        if app_exists(tool):
            if refresh is default_refresh and _packages_stale(tool):
                # Same code, but its packages were never installed from these requirement
                # files (a newly required package, or an install from before we tracked it).
                if dry_run:
                    return r(WOULD_UPDATE, "Would install missing packages.")
                _phase(PHASE_PACKAGES)
                ok, out = refresh(tool)
                if not ok:
                    return r(BUILD_FAILED, "Couldn't install %s's packages. %s" % (tool.name, out))
                _record_packages(tool)
                return r(UPDATED, "Installed missing packages.")
            return r(UP_TO_DATE, "Already the latest.")
        # Up to date but never built: fall through to build.
    if dry_run:
        return r(WOULD_UPDATE, "%d new commit(s) would be pulled." % behind if behind else "Would build the app.")

    if behind:
        ok, why = verify_upstream(tool)
        if not ok:
            return r(UNSIGNED, "The new version of %s isn't signed by Stefan, so it wasn't installed. "
                               "Tell Stefan. (%s)" % (tool.name, why or "no signature"))
        _phase("Downloading the new code")
        code, out = _git(tool.path, "pull", "--ff-only", "--quiet", timeout=300)
        if code != 0:
            return r(SKIPPED_DIVERGED, "Couldn't fast-forward %s. Left alone. (%s)" % (tool.name, out[-200:]))
    _phase(PHASE_PACKAGES)
    ok, out = refresh(tool)
    if not ok:
        return r(BUILD_FAILED, "Updated the code but couldn't refresh packages. %s" % out)
    if refresh is default_refresh:
        _record_packages(tool)
    _phase("Building the app")
    ok, out = build(tool)
    if not ok:
        _record_build_failure(tool)
        return r(BUILD_FAILED, "Updated the code but the rebuild failed, so the old app is still there. %s" % out)
    _clear_build_failure(tool)
    return r(UPDATED, "Updated and rebuilt." if behind else "Built.")


def fetch_quietly(tools: list) -> None:
    """git fetch each usable tool so "newer" counts are real. Never raises."""
    for t in tools:
        if t.usable:
            _git(t.path, "fetch", "--quiet")


def update_all(tools: list, on_result: Optional[Callable[[Result], None]] = None,
               on_start: Optional[Callable[[registry.Tool], None]] = None,
               skip: Optional[Callable[[registry.Tool], bool]] = None, **kw) -> list:
    """The Studio's own clone goes first: the tools' builds copy shared files from it (build/lib.sh,
    build/pi_or_mac.py), so a fix there reaches the apps in the same run. `skip(tool)` -> True passes a
    tool by (it was opened while waiting its turn, and a running app is never rebuilt underneath it)."""
    results = []
    studio = kw.pop("studio", None)
    for t in ([studio] if studio else []) + list(tools):
        if skip is not None and skip(t):
            res = Result(t.id, t.name, SKIPPED_OPEN, "Opened before its turn, so it wasn't updated this time. "
                                                     "It will be next time.")
            results.append(res)
            if on_result:
                on_result(res)
            continue
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
