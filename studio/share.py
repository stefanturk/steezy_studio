"""Copy-pasteable install commands for friends, built from registry.json.

One place decides what a friend types, so the Share panel, the README and the
tests can't drift apart. Nothing here touches the network.
"""
from __future__ import annotations

from typing import Optional

RAW = "https://raw.githubusercontent.com/stefanturk/steezy_studio/main/"
MAC, WINDOWS = "mac", "windows"


def mac_command(tool_ids: Optional[list] = None) -> str:
    """`bash -c "$(curl ...)" _ beat_thief session_sync`; no ids = the whole Studio."""
    cmd = 'bash -c "$(curl -fsSL %sinstall.sh)"' % RAW
    if tool_ids:
        cmd += " _ " + " ".join(tool_ids)
    return cmd


def windows_command(tool_ids: Optional[list] = None) -> str:
    cmd = "& ([scriptblock]::Create((irm %sinstall.ps1)))" % RAW
    if tool_ids:
        cmd += " " + " ".join(tool_ids)
    return cmd


def command(platform: str, tool_ids: Optional[list] = None) -> str:
    return windows_command(tool_ids) if platform == WINDOWS else mac_command(tool_ids)


def share_options(tools: list) -> dict:
    """The data the Share panel shows. `tools` are registry.Tool objects.

    Broken registry entries are left out: there is nothing to install.
    """
    usable = [t for t in tools if t.state != "broken"]
    rows = []
    for t in usable:
        rows.append({
            "id": t.id, "name": t.name, "private": bool(getattr(t, "private", False)),
            "commands": {p: command(p, [t.id]) for p in (MAC, WINDOWS) if p in t.platforms},
            "platforms": list(t.platforms),
        })
    return {
        "studio": {p: command(p) for p in (MAC, WINDOWS)},
        "tools": rows,
        "windows_ready": WINDOWS_READY,
    }


# Flipped to True once install.ps1 exists and is tested (Session 5).
WINDOWS_READY = False
