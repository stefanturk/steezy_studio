"""Invite a friend to one of the private tool repos, from the Studio.

    python3 -m studio.invite <github-username> [tool_id ...]   (dry run unless --send)

Uses the signed-in `gh`. The repo owner is taken from each tool's registry URL,
so nothing is hard-coded. Nothing here raises: every outcome is a result dict.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from typing import Callable, Optional

from studio import registry

_USER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPO = re.compile(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$")


def gh_args(repo_url: str, username: str) -> Optional[list]:
    m = _REPO.search(repo_url or "")
    if not m or not _USER.match(username or ""):
        return None
    return ["gh", "api", "-X", "PUT", "repos/%s/%s/collaborators/%s" % (m.group(1), m.group(2), username),
            "-f", "permission=pull"]


def invite(username: str, tool_ids: Optional[list] = None, send: bool = False,
           tools: Optional[list] = None, runner: Optional[Callable] = None) -> list:
    """One result per private tool: {id, ok, sent, message, command}. Dry run by default."""
    tools = tools if tools is not None else registry.load_tools()
    default_runner = runner is None
    runner = runner or (lambda a: subprocess.run(a, capture_output=True, text=True, timeout=30))
    out = []
    for t in tools:
        if t.state == registry.BROKEN or not t.private:
            continue
        if tool_ids and t.id not in tool_ids:
            continue
        args = gh_args(t.repo, username)
        if args is None:
            out.append({"id": t.id, "ok": False, "sent": False, "command": None,
                        "message": "That doesn't look like a GitHub username."})
            continue
        if not send:
            out.append({"id": t.id, "ok": True, "sent": False, "command": args,
                        "message": "Would invite %s to %s (dry run)." % (username, t.name)})
            continue
        if default_runner and shutil.which("gh") is None:
            out.append({"id": t.id, "ok": False, "sent": False, "command": args,
                        "message": "The GitHub tool (gh) isn't installed or signed in."})
            continue
        try:
            r = runner(args)
            ok = r.returncode == 0
            msg = "Invited %s to %s." % (username, t.name) if ok else (r.stderr or "GitHub refused.").strip()[:200]
        except (OSError, subprocess.SubprocessError) as e:
            ok, msg = False, "Couldn't run gh: %s" % e
        out.append({"id": t.id, "ok": ok, "sent": ok, "command": args, "message": msg})
    return out


def main(argv: list) -> int:
    send = "--send" in argv
    rest = [a for a in argv if a != "--send"]
    if not rest:
        print(__doc__)
        return 2
    for r in invite(rest[0], rest[1:], send=send):
        print(("ok   " if r["ok"] else "FAIL ") + r["id"] + ": " + r["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
