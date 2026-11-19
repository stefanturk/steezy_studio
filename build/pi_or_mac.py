"""Your Pi or this Mac: the start-up shared by every Steezy app that also runs on a Pi (Stage Lighting,
Video Streamer). Each app's make_app.sh copies this file into its bundle, so the app stays self-contained.

When the app opens, its window first shows a small page that looks for a Pi running the same program:
the address it used last, then the app's usual names (sound.lan, video.lan...). A Pi only counts when it
answers like the right program (`fingerprint`), so a router or another app on the same port never does.

  Found       "Found your Pi at X."   [Use the Pi]  [Run on this Mac]
  Not found   "No Pi found."          [Run on this Mac]  [Connect to my Pi...]  (type an address; it's remembered)

Use the Pi opens the Pi's own page in the window and starts nothing on the Mac, so the two never fight.
Run on this Mac calls the app's `run_here()`, which starts its server and returns the page to show.
The choice and the Pi's address are remembered in <data dir>/pi.json; the last choice is the default
button. Stdlib only (the page talks to `Start` through pywebview's js_api).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterable, Optional

MEMORY = "pi.json"


def normalize(addr: str) -> Optional[str]:
    """'video.lan', '192.168.8.161:9200', 'http://x/' -> 'http://host[:port]'. None if it isn't an address."""
    addr = (addr or "").strip()
    if not addr:
        return None
    if "://" not in addr:
        addr = "http://" + addr
    try:
        u = urllib.parse.urlsplit(addr)
        port = u.port
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not u.hostname or any(c in u.hostname for c in " /\\@"):
        return None
    host = u.hostname if ":" not in u.hostname else "[%s]" % u.hostname
    return "%s://%s%s" % (u.scheme, host, ":%d" % port if port else "")


def lights_state(d: dict) -> bool:
    """Stage Lighting's /state: it carries the audio meters, and never a phone list."""
    return any(str(k).startswith("audio_") for k in d) and "angles" not in d


def video_state(d: dict) -> bool:
    """Video Streamer's /state: the show's mode, its phones (angles) and bands."""
    return all(k in d for k in ("mode", "angles", "bands"))


def looks_like(base: str, fingerprint: Callable[[dict], bool], path: str = "/state", timeout: float = 1.5,
               opener=urllib.request.urlopen) -> bool:
    """True only if `base` answers `path` with JSON the fingerprint recognises. Never raises."""
    try:
        with opener(base.rstrip("/") + path, timeout=timeout) as r:
            d = json.loads(r.read(1_000_000).decode("utf-8", "replace"))
        return isinstance(d, dict) and bool(fingerprint(d))
    except Exception:
        return False


def find_pi(candidates: Iterable[str], probe: Callable[[str], bool]) -> Optional[str]:
    """The first candidate (normalised, each tried once) that the probe recognises."""
    seen = set()
    for c in candidates:
        url = normalize(c)
        if not url or url in seen:
            continue
        seen.add(url)
        if probe(url):
            return url
    return None


def load_memory(data_dir: str) -> dict:
    """What pi.json remembers: only a string "pi" and a "last" of "pi" or "mac" survive, so a hand-edited
    or damaged file can never break the start page."""
    try:
        with open(os.path.join(data_dir, MEMORY)) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict):
        return {}
    out = {}
    if isinstance(d.get("pi"), str) and d["pi"].strip():
        out["pi"] = d["pi"]
    if d.get("last") in ("pi", "mac"):
        out["last"] = d["last"]
    return out


def save_memory(data_dir: str, **changes) -> None:
    d = load_memory(data_dir)
    d.update(changes)
    try:
        os.makedirs(data_dir, exist_ok=True)
        tmp = os.path.join(data_dir, MEMORY + ".tmp")
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, os.path.join(data_dir, MEMORY))
    except OSError:
        pass                                # remembering is a convenience, never a reason to fail


PAGE_FUNCTIONS = ("look", "use_pi", "connect", "run_here")
CLOSED = {"ok": False, "message": "This window has moved on from the start page."}


class Start:
    """What the start page calls. `run_here()` -> (ok, url_or_message) starts the app on this Mac.

    The launcher creates the window with js_api=start and hands it over with attach(). attach() then
    takes the object back out of pywebview (window._js_api = None) and exposes only PAGE_FUNCTIONS, by
    exact name, with window.expose(). This matters: pywebview resolves a page's call by following a
    dotted path on the js_api object, underscores and all ("_run_here.popen" reached subprocess.Popen),
    and it injects the bridge into every page the window loads, the Pi's own page included. Exposed
    functions are looked up by exact name only. Once the window has left the start page they refuse."""

    def __init__(self, app_name: str, data_dir: str, defaults: list, probe: Callable[[str], bool],
                 run_here: Callable[[], tuple], what: str = "it"):
        self._app, self._data, self._defaults, self._probe = app_name, data_dir, list(defaults), probe
        self._run_here, self._what = run_here, what
        self._window = None
        self._left = False                  # the window has gone to the Pi's page or the Mac's server

    def attach(self, window) -> None:
        self._window = window
        if hasattr(window, "expose"):
            if getattr(window, "_js_api", None) is self:
                window._js_api = None
            window.expose(*[_named(getattr(self, n), n) for n in PAGE_FUNCTIONS])

    def _go(self, url: str) -> None:
        self._left = True
        if self._window is not None:
            self._window.load_url(url)

    def look(self) -> dict:
        """Called by the page once it's on screen (so the window never waits on the network)."""
        if self._left:
            return dict(CLOSED)
        mem = load_memory(self._data)
        found = find_pi(([mem["pi"]] if mem.get("pi") else []) + self._defaults, self._probe)
        return {"found": found, "last": mem.get("last") or ("pi" if found else "mac"), "app": self._app, "what": self._what}

    def use_pi(self, url: str) -> dict:
        if self._left:
            return dict(CLOSED)
        url = normalize(url if isinstance(url, str) else "")
        if not url or not self._probe(url):
            return {"ok": False, "message": "The Pi stopped answering. Try again, or run on this Mac."}
        save_memory(self._data, pi=url, last="pi")
        self._go(url + "/")
        return {"ok": True}

    def connect(self, addr: str) -> dict:
        if self._left:
            return dict(CLOSED)
        url = normalize(addr if isinstance(addr, str) else "")
        if not url:
            return {"ok": False, "message": "That doesn't look like an address. Try something like 192.168.8.161 or mypi.local:9000."}
        if not self._probe(url):
            return {"ok": False, "message": "Nothing at %s is running %s. Check the address and that the Pi is on." % (url, self._app)}
        return self.use_pi(url)

    def run_here(self) -> dict:
        if self._left:
            return dict(CLOSED)
        try:
            ok, where = self._run_here()
        except Exception as e:              # the page must always get an answer, never hang on "Starting..."
            ok, where = False, "%s could not start: %s" % (self._app, e)
        if not ok:
            return {"ok": False, "message": where}
        save_memory(self._data, last="mac")
        self._go(where)
        return {"ok": True}


def _named(method: Callable, name: str) -> Callable:
    """A plain function called `name` (window.expose() registers functions under their __name__)."""
    def call(*args):
        return method(*args)
    call.__name__ = call.__qualname__ = name
    return call


PAGE = """<!doctype html><meta charset="utf-8"><title>__APP__</title>
<style>
 :root{--panel:#16171b;--raised:#1e2026;--edge:#2c2f37;--ink:#e9e7e2;--dim:#8b8d95;--accent:#a78bfa;--bad:#ff6b5e}
 html,body{margin:0;height:100%;background:var(--panel);color:var(--ink);font:15px/1.5 "Avenir Next",-apple-system,sans-serif}
 body{display:flex;align-items:center;justify-content:center}
 .box{background:var(--raised);border:1px solid var(--edge);border-radius:10px;padding:28px 32px;width:min(520px,90vw);display:flex;flex-direction:column;gap:14px}
 h1{margin:0;font-size:20px} p{margin:0;color:var(--dim)} #msg{color:var(--bad);min-height:20px;font-size:13px}
 .row{display:flex;gap:10px;flex-wrap:wrap}
 button{font:inherit;font-weight:600;border-radius:7px;padding:9px 18px;cursor:pointer;border:1px solid var(--accent);background:transparent;color:var(--accent)}
 button.main{background:var(--accent);color:var(--panel)} button:disabled{opacity:.5;cursor:default}
 input{flex:1;min-width:0;background:var(--panel);color:var(--ink);border:1px solid var(--edge);border-radius:7px;padding:8px 10px;font:inherit}
 [hidden]{display:none!important}
</style>
<div class="box">
 <h1 id="title">__APP__</h1>
 <p id="status">Looking for your Pi…</p>
 <div class="row" id="choices" hidden><button id="pi">Use the Pi</button><button id="mac">Run on this Mac</button><button id="other">Connect to my Pi…</button></div>
 <div class="row" id="addr" hidden><input id="where" placeholder="Pi address, e.g. 192.168.8.161 or mypi.local:9000"><button id="go">Connect</button></div>
 <div id="msg"></div>
</div>
<script>
 const $ = (id) => document.getElementById(id);
 let found = null;
 function busy(on, text) { document.querySelectorAll("button").forEach((b) => b.disabled = on); if (text) $("status").textContent = text; }
 function main(id) { ["pi", "mac", "other"].forEach((k) => $(k).classList.toggle("main", k === id)); $(id).focus(); }
 async function answer(p) {
   let r; try { r = await p; } catch (e) { r = {ok: false, message: "Something went wrong: " + ((e && e.message) || e)}; }
   if (!r || !r.ok) { busy(false); $("msg").textContent = (r && r.message) || ""; }
 }
 $("pi").onclick = () => { busy(true, "Opening the Pi…"); answer(pywebview.api.use_pi(found)); };
 $("mac").onclick = () => { busy(true, "Starting on this Mac…"); $("msg").textContent = ""; answer(pywebview.api.run_here()); };
 $("other").onclick = () => { $("addr").hidden = false; $("where").focus(); };
 $("go").onclick = () => { busy(true, "Checking " + $("where").value + "…"); answer(pywebview.api.connect($("where").value)); };
 $("where").onkeydown = (e) => { if (e.key === "Enter") $("go").click(); };
 async function start() {
   let s;   // if looking fails the buttons still appear: "Run on this Mac" must always be reachable
   try { s = await pywebview.api.look(); } catch (e) { s = {found: null, last: "mac", what: "it"}; }
   found = s.found || null;
   $("status").textContent = found ? "Found your Pi at " + found.replace(/^https?:\\/\\//, "") + ". Use it, or run " + s.what + " on this Mac instead."
                                   : "No Pi found. Run " + s.what + " on this Mac, or connect to your Pi by its address.";
   $("pi").hidden = !found;
   $("choices").hidden = false;
   main(found && s.last === "pi" ? "pi" : "mac");
 }
 if (window.pywebview && window.pywebview.api) start(); else window.addEventListener("pywebviewready", start);
</script>"""


def page(app_name: str) -> str:
    safe = app_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return PAGE.replace("__APP__", safe)
