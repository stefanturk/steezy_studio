"""The list of tools Steezy Studio knows about, and what state each is in.

Nothing here raises for a bad or missing tool: every problem becomes a state
the launcher can show greyed out with a plain sentence ("ask Stefan"), never
an error dialog.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Optional

from studio import platform_paths

DEFAULT_REGISTRY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "registry.json")
DEFAULT_ROOT = os.path.expanduser("~/Desktop/Python")


def configured_root() -> str:
    """Where tools live: the folder the friend installer wrote to `tools_dir`
    beside the engine, else Stefan's ~/Desktop/Python."""
    engine = platform_paths.engine_dir()
    try:
        with open(os.path.join(os.path.dirname(engine), "tools_dir")) as f:
            p = f.read().strip()
        if p:
            return p
    except OSError:
        pass
    return DEFAULT_ROOT

def studio_path() -> Optional[str]:
    """The git clone Steezy Studio itself updates from. On Windows it runs from
    source, so that is where this file lives. On a Mac the app carries a copy, so
    make_app.sh records the clone in `studio_dir` beside the engine."""
    if platform_paths.is_windows():
        p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    else:
        try:
            with open(os.path.join(os.path.dirname(platform_paths.engine_dir()), "studio_dir")) as f:
                p = f.read().strip()
        except OSError:
            return None
    return p if p and os.path.isdir(os.path.join(p, ".git")) else None


def studio_tool(path: Optional[str] = None) -> Optional["Tool"]:
    path = path or studio_path()
    if not path:
        return None
    return Tool(id="studio", name="Steezy Studio", repo="", folder=os.path.basename(path), path=path,
                build=["./make_app.sh"], app="Steezy Studio.app", platforms=["mac", "windows"])


READY = "ready"
NOT_INSTALLED = "not_installed"      # folder missing
NOT_GIT = "not_git"                  # folder there, but not a git checkout
NO_ACCESS = "no_access"              # GitHub says this account can't see the repo
BROKEN = "broken"                    # registry entry unusable
UNSUPPORTED = "unsupported"          # no version for this OS yet

_REQUIRED = ("id", "name", "repo", "folder", "build", "app")


@dataclass
class Tool:
    id: str
    name: str
    repo: str
    folder: str
    path: str
    build: list
    app: str
    platforms: list
    private: bool = False
    windows_run: list = None      # argv after pythonw to start the tool on Windows
    # Windows has no build step, so pip does all of it: these requirement files in
    # order, then `pip install -e .` if set. (On a Mac the tool's own build script decides.)
    windows_requirements: list = None
    windows_pip_editable: bool = False
    state: str = READY
    message: str = ""

    @property
    def usable(self) -> bool:
        return self.state == READY


def _broken(raw: object, why: str) -> Tool:
    d = raw if isinstance(raw, dict) else {}
    name = str(d.get("name") or d.get("id") or "Unknown tool")
    return Tool(id=str(d.get("id") or name), name=name, repo="", folder="", path="", build=[],
                app="", platforms=[], state=BROKEN, message="Steezy Studio can't read this one. Ask Stefan. (%s)" % why)


def load_tools(registry_path: Optional[str] = None, root: Optional[str] = None,
               has_access: Optional[Callable[[Tool], bool]] = None) -> list:
    """Every tool in the registry with its state filled in. Never raises.

    has_access(tool) -> bool is the network check (can this GitHub account see
    the repo?); it is only asked about tools that are not installed, and a
    check that itself fails is treated as "can't tell", not "no access".
    """
    registry_path = registry_path or DEFAULT_REGISTRY
    root = os.path.expanduser(root or os.environ.get("STEEZY_TOOLS_DIR") or configured_root())
    try:
        with open(registry_path) as f:
            entries = json.load(f)["tools"]
        if not isinstance(entries, list):
            raise ValueError("tools is not a list")
    except (OSError, ValueError, KeyError, TypeError) as e:
        return [_broken({"id": "registry", "name": "Tool list"}, "registry: %s" % e)]

    tools = []
    seen = set()
    for raw in entries:
        if not isinstance(raw, dict):
            tools.append(_broken(raw, "entry is not an object"))
            continue
        missing = [k for k in _REQUIRED if not raw.get(k)]
        if missing:
            tools.append(_broken(raw, "missing " + ", ".join(missing)))
            continue
        if raw["id"] in seen:
            tools.append(_broken(raw, "duplicate id"))
            continue
        build = raw["build"]
        if not (isinstance(build, list) and all(isinstance(a, str) for a in build)):
            tools.append(_broken(raw, "build must be a list of strings"))
            continue
        seen.add(raw["id"])
        t = Tool(id=raw["id"], name=raw["name"], repo=raw["repo"], folder=raw["folder"],
                 path=os.path.join(root, raw["folder"]), build=build, app=raw["app"],
                 platforms=list(raw.get("platforms") or ["mac"]), private=bool(raw.get("private", False)),
                 windows_run=list(raw.get("windows_run") or []),
                 windows_requirements=[str(r) for r in (raw.get("windows_requirements") or ["requirements.txt"])],
                 windows_pip_editable=bool(raw.get("windows_pip_editable", False)))
        if platform_paths.os_name() not in t.platforms:
            t.state = UNSUPPORTED
            t.message = "%s is %s only for now." % (t.name, " and ".join(
                {"mac": "Mac", "windows": "Windows"}.get(p, p) for p in t.platforms) or "not available")
        elif not os.path.isdir(t.path):
            t.state = NOT_INSTALLED
            t.message = "%s isn't on this computer yet. Press Install." % t.name
            if has_access is not None:
                try:
                    if not has_access(t):
                        t.state = NO_ACCESS
                        t.message = "%s is private. Ask Stefan for access." % t.name
                except Exception:
                    pass
        elif not os.path.exists(os.path.join(t.path, ".git")):
            t.state = NOT_GIT
            t.message = "%s wasn't installed with git, so it can't update itself. Ask Stefan." % t.name
        tools.append(t)
    return tools
