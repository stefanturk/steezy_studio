#!/usr/bin/env python3
"""Keep a Dock pin alive when an app moves.

The Dock remembers a pinned app by its path. When an app is deleted from there (an old copy swept
away after a rebuild landed somewhere else) the pin turns into a question mark and the person has to
find the app and pin it again. So before an old copy is removed, point its pin at the new copy.

    python3 dock_repin.py <old.app> <new.app>

Does nothing, quietly, if the old app isn't pinned, so it is safe to call on every build.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import urllib.parse

SECTIONS = ("persistent-apps", "persistent-others")


def file_url(path: str) -> str:
    return "file://" + urllib.parse.quote(os.path.abspath(path)) + "/"


def repoint(prefs: dict, old: str, new: str) -> int:
    """Point every pin of `old` at `new`, in place. Returns how many were changed.
    The pin's stored bookmark is dropped: it still names the old file, and the Dock would
    trust it over the new path."""
    old_url, new_url = file_url(old), file_url(new)
    label = os.path.splitext(os.path.basename(new))[0]
    changed = 0
    for section in SECTIONS:
        for item in prefs.get(section, []):
            tile = item.get("tile-data", {})
            data = tile.get("file-data", {})
            if data.get("_CFURLString", "").rstrip("/") != old_url.rstrip("/"):
                continue
            data["_CFURLString"] = new_url
            tile.pop("book", None)
            tile["file-label"] = tile.get("file-label") or label
            changed += 1
    return changed


def _run(*cmd, **kw):
    return subprocess.run(list(cmd), capture_output=True, timeout=20, **kw)


def repin(old: str, new: str) -> int:
    """Read the Dock's preferences, repoint, and write them back (restarting the Dock only if
    something changed). Never raises: a Dock that can't be updated must not fail a build."""
    try:
        if not os.path.isdir(new):
            return 0                     # never point a pin at something that isn't there
        out = _run("defaults", "export", "com.apple.dock", "-")
        if out.returncode != 0 or not out.stdout:
            return 0
        prefs = plistlib.loads(out.stdout)
        changed = repoint(prefs, old, new)
        if changed:
            back = _run("defaults", "import", "com.apple.dock", "-", input=plistlib.dumps(prefs))
            if back.returncode == 0:
                _run("killall", "Dock")
            else:
                return 0
        return changed
    except Exception:
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    n = repin(sys.argv[1], sys.argv[2])
    if n:
        print("Moved %d Dock pin(s) to %s" % (n, sys.argv[2]), file=sys.stderr)
