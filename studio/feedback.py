"""Send a tester's note to the feedback sheet, and never lose one.

A note is posted as JSON to the Apps Script address in feedback_config.URL, which adds a
row to the shared Google Sheet. If that fails (offline, script down), the note is kept in
<state>/feedback_outbox.json and tried again with the next note or the next launch.

Nothing here raises: every function returns plain data for the page.
"""
from __future__ import annotations

import json
import os
import platform
import re
import urllib.request
import uuid
from typing import Callable, Optional

from studio import feedback_config, platform_paths

MAX_NOTE = 2000
LOG_LINES = 40
OUTBOX_MAX = 20
TIMEOUT = 25

# A tool's log on a Mac. Other systems don't keep one the Studio knows about.
LOG_FILES = {
    "beat_thief": "beat_thief.log",
    "ableton_loader": "ableton_loader.log",
    "session_sync": "SessionSync.log",
    "movie_maker": "movie_maker.log",
    "stage_lighting": "stage_lighting.log",
    "video_streamer": "video_streamer.log",
    "steezy_studio": "steezy_studio.log",
}


def enabled(url: Optional[str] = None) -> bool:
    return bool(feedback_config.URL if url is None else url)


def tester_id(state: Optional[str] = None) -> str:
    """A random id for this computer, so repeat notes can be told apart. Not tied to a person."""
    state = state or platform_paths.state_dir()
    path = os.path.join(state, "feedback_id")
    try:
        with open(path) as f:
            got = f.read().strip()
        if got:
            return got
    except OSError:
        pass
    new = uuid.uuid4().hex[:12]
    try:
        os.makedirs(state, exist_ok=True)
        with open(path, "w") as f:
            f.write(new)
    except OSError:
        pass
    return new


def scrub(text: str, home: Optional[str] = None) -> str:
    """Take the user's home folder (and so their name) out of log text."""
    home = home or os.path.expanduser("~")
    if home and home not in ("/", "~"):
        text = text.replace(home, "~")
    return re.sub(r"/Users/[^/\s]+", "/Users/~", text)


def log_tail(tool: str, lines: int = LOG_LINES, logs_dir: Optional[str] = None) -> str:
    name = LOG_FILES.get(tool)
    if not name:
        return ""
    logs_dir = logs_dir or os.path.expanduser("~/Library/Logs")
    try:
        with open(os.path.join(logs_dir, name), errors="replace") as f:
            tail = f.readlines()[-lines:]
    except OSError:
        return ""
    return scrub("".join(tail))[-6000:]


def build_payload(note: str, tool: str, include_log: bool, version: str, state: Optional[str] = None,
                  logs_dir: Optional[str] = None) -> dict:
    return {
        "token": feedback_config.TOKEN,
        "id": tester_id(state),
        "tool": (tool or "")[:40],
        "version": (version or "?")[:20],
        "os": "%s %s" % (platform.system(), platform.release()),
        "note": (note or "").strip()[:MAX_NOTE],
        "log": log_tail(tool, logs_dir=logs_dir) if include_log else "",
        "website": "",          # honeypot: the page leaves it empty, bots fill every field
    }


def _post(payload: dict, url: str) -> bool:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "text/plain;charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = json.loads(r.read().decode("utf-8", "replace") or "{}")
        return bool(body.get("ok"))
    except Exception:
        return False


def _outbox_path(state: Optional[str]) -> str:
    return os.path.join(state or platform_paths.state_dir(), "feedback_outbox.json")


def _load_outbox(state) -> list:
    try:
        with open(_outbox_path(state)) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save_outbox(state, items: list) -> None:
    path = _outbox_path(state)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if items:
            with open(path, "w") as f:
                json.dump(items[-OUTBOX_MAX:], f)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def pending(state: Optional[str] = None) -> int:
    return len(_load_outbox(state))


def flush(url: Optional[str] = None, state: Optional[str] = None,
          post: Optional[Callable[[dict, str], bool]] = None) -> int:
    """Try the saved notes again. Returns how many are still waiting."""
    url = feedback_config.URL if url is None else url
    post = post or _post
    left = _load_outbox(state)
    if not url or not left:
        return len(left)
    kept = []
    for i, item in enumerate(left):
        if not post(item, url):
            kept = left[i:]          # stop at the first failure: offline, so don't hammer it
            break
    _save_outbox(state, kept)
    return len(kept)


def send(note: str, tool: str, include_log: bool, version: str, *, url: Optional[str] = None,
         state: Optional[str] = None, logs_dir: Optional[str] = None,
         post: Optional[Callable[[dict, str], bool]] = None) -> dict:
    url = feedback_config.URL if url is None else url
    post = post or _post
    if not (note or "").strip():
        return {"ok": False, "message": "Write a note first."}
    if not url:
        return {"ok": False, "message": "Feedback isn't switched on yet."}
    payload = build_payload(note, tool, include_log, version, state, logs_dir)
    flush(url, state, post)
    if post(payload, url):
        return {"ok": True, "message": "Thanks! Sent."}
    items = _load_outbox(state)
    items.append(payload)
    _save_outbox(state, items)
    return {"ok": True, "message": "No connection right now. Your note is saved and will go next time."}
