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


_SECRET = re.compile(r"(?i)\b([\w-]*(?:token|password|passwd|secret|api[_-]?key)[\w-]*)(\s*[:=]\s*)"
                     r"(\"[^\"]*\"|'[^']*'|\S+)")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
_names_cache: Optional[tuple] = None


def _this_computer() -> tuple:
    """(login name, [names this computer goes by]): its host name, the short form, and on a Mac the
    "Computer Name" people see (often "Stefan's MacBook Pro"). Best effort, worked out once."""
    global _names_cache
    if _names_cache is None:
        import getpass
        import socket
        try:
            user = getpass.getuser()
        except Exception:
            user = ""
        names = set()
        try:
            host = socket.gethostname()
            names.update({host, host.split(".")[0]})
        except OSError:
            pass
        if not platform_paths.is_windows():
            try:
                import subprocess
                for key in ("ComputerName", "LocalHostName"):
                    r = subprocess.run(["scutil", "--get", key], capture_output=True, text=True, timeout=3)
                    if r.returncode == 0 and r.stdout.strip():
                        names.add(r.stdout.strip())
            except Exception:
                pass
        _names_cache = (user, sorted((n for n in names if len(n) >= 3), key=len, reverse=True))
    return _names_cache


def _public_ip(m: "re.Match") -> str:
    import ipaddress
    try:
        ip = ipaddress.ip_address(m.group(0))
    except ValueError:
        return m.group(0)                   # a time like 12:30:45, a version number...
    return "x.x.x.x" if ip.is_global else m.group(0)


def scrub(text: str, home: Optional[str] = None, user: Optional[str] = None, host: Optional[str] = None) -> str:
    """Take what identifies the person, or could be misused, out of log text before it is sent: their
    home folder and login name, this computer's names, email addresses, passwords/tokens and public IP
    addresses. Addresses on the local network (192.168.x, 10.x, the Pi's) stay: they help fix bugs."""
    home = home or os.path.expanduser("~")
    if home and home not in ("/", "~"):
        text = text.replace(home, "~")
    text = re.sub(r"/Users/[^/\s]+", "/Users/~", text)
    text = re.sub(r"(?i)\b([A-Z]:\\Users\\)[^\\\s]+", r"\1~", text)
    if user is None or host is None:
        me, names = _this_computer()
        user = me if user is None else user
        names = names if host is None else [host]
    else:
        names = [host]
    for n in names:
        if n:
            text = re.sub(re.escape(n), "~computer", text, flags=re.IGNORECASE)
    if user and user not in ("root",):
        text = re.sub(r"(?<![\w'-])%s(?![\w-])" % re.escape(user), "~user", text)
    text = _GITHUB_TOKEN.sub("~token", text)
    text = _SECRET.sub(lambda m: m.group(1) + m.group(2) + "~hidden", text)
    text = _EMAIL.sub("~email", text)
    text = _IPV4.sub(_public_ip, text)
    return _IPV6.sub(_public_ip, text)


def _tail_text(path: str, max_bytes: int) -> str:
    """The last `max_bytes` of a file, starting on a whole line. Reads only that much, however big."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        data = f.read()
    if size > max_bytes:
        data = data.split(b"\n", 1)[1] if b"\n" in data else data
    return data.decode("utf-8", "replace")


def log_tail(tool: str, lines: int = LOG_LINES, logs_dir: Optional[str] = None) -> str:
    name = LOG_FILES.get(tool)
    if not name:
        return ""
    logs_dir = logs_dir or os.path.expanduser("~/Library/Logs")
    try:
        tail = _tail_text(os.path.join(logs_dir, name), 64_000).splitlines()[-lines:]
    except OSError:
        return ""
    return scrub("\n".join(tail))[-6000:]


def trim_logs(logs_dir: Optional[str] = None, limit: int = 5_000_000, keep: int = 1_000_000) -> None:
    """Keep the Steezy apps' logs from growing forever: one over `limit` bytes is cut down to its
    newest `keep` bytes, in place (an app that is running keeps appending to the same file). Never raises."""
    logs_dir = logs_dir or os.path.expanduser("~/Library/Logs")
    for name in set(LOG_FILES.values()):
        path = os.path.join(logs_dir, name)
        try:
            if os.path.getsize(path) <= limit:
                continue
            tail = _tail_text(path, keep).encode("utf-8", "replace")
            with open(path, "r+b") as f:
                f.write(tail)
                f.truncate()
        except OSError:
            continue


def build_payload(note: str, tool: str, include_log: bool, version: str, state: Optional[str] = None,
                  logs_dir: Optional[str] = None) -> dict:
    return {
        "token": feedback_config.TOKEN,
        "id": tester_id(state),
        "tool": (tool or "")[:40],
        "version": (version or "?")[:20],
        "os": "%s %s" % (platform.system(), platform.release()),
        "note": clean_note(note)[:MAX_NOTE],
        "log": log_tail(tool, logs_dir=logs_dir) if include_log else "",
        "website": "",          # honeypot: the page leaves it empty, bots fill every field
    }


REJECTED = "rejected"      # the sheet answered and said no (wrong token, empty note): retrying can't help


def _post(payload: dict, url: str):
    """True when the sheet took it; REJECTED when it answered no; False when it should be tried later
    (no connection, the script down, or today's cap reached)."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "text/plain;charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = json.loads(r.read().decode("utf-8", "replace") or "{}")
    except Exception:
        return False
    if not isinstance(body, dict):
        return False
    if body.get("ok"):
        return True
    return False if body.get("full") else REJECTED


def clean_note(note) -> str:
    """The note as the sheet will see it: JavaScript's trim() there also strips U+FEFF, which
    Python's strip() keeps, so a note of only that used to be refused there and retried forever."""
    return str(note or "").replace("﻿", "").replace("​", "").strip()


_sending = __import__("threading").Lock()     # the launch-time retry and a Send must not post the same note twice


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
    with _sending:
        return _flush_locked(url, state, post)


def _flush_locked(url, state, post) -> int:
    left = _load_outbox(state)
    if not url or not left:
        return len(left)
    kept = []
    for i, item in enumerate(left):
        res = post(item, url)
        if res == REJECTED:
            continue                 # the sheet will never take this one: drop it, try the rest
        if not res:
            kept = left[i:]          # stop at the first failure: offline, so don't hammer it
            break
    _save_outbox(state, kept)
    return len(kept)


def send(note: str, tool: str, include_log: bool, version: str, *, url: Optional[str] = None,
         state: Optional[str] = None, logs_dir: Optional[str] = None,
         post: Optional[Callable[[dict, str], bool]] = None) -> dict:
    url = feedback_config.URL if url is None else url
    post = post or _post
    if not clean_note(note):
        return {"ok": False, "message": "Write a note first."}
    if not url:
        return {"ok": False, "message": "Feedback isn't switched on yet."}
    payload = build_payload(note, tool, include_log, version, state, logs_dir)
    with _sending:
        _flush_locked(url, state, post)
        res = post(payload, url)
        if res == REJECTED:
            return {"ok": False, "message": "The feedback sheet didn't accept that note. Steezy Studio may need an update."}
        if res:
            return {"ok": True, "message": "Thanks! Sent."}
        items = _load_outbox(state)
        items.append(payload)
        _save_outbox(state, items)
    return {"ok": True, "message": "No connection right now. Your note is saved and will go next time."}
