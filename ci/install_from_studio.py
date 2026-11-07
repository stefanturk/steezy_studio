"""CI on Windows: press Install the way the page does, through gui.Api, for every
tool that has a Windows version, and check Mac-only tools say so. Exits non-zero
with the reason on any failure. Run with the engine Python from the Studio clone."""
import os
import sys
import time

sys.path.insert(0, os.getcwd())   # the Studio clone under test, not this ci/ folder
from studio import gui, installer, registry

api = gui.Api()
tiles = {t["id"]: t for t in api.list_tools()}
bad = []
for t in registry.load_tools():
    tile = tiles[t.id]
    if "windows" not in t.platforms:
        if tile["state"] != registry.UNSUPPORTED or tile["installable"]:
            bad.append("%s should be Mac-only, got %s" % (t.id, tile["state"]))
        continue
    if not tile["installable"]:
        bad.append("%s has no Install button (%s: %s)" % (t.id, tile["state"], tile["message"]))
        continue
    print("Installing %s ..." % t.name, flush=True)
    started = time.time()
    if not api.install_tool(t.id)["started"]:
        bad.append("%s install didn't start" % t.id)
        continue
    while api.update_status()["running"]:
        time.sleep(2)
    res = api.update_status()["results"][-1]
    print("  %s in %ds: %s" % (res["status"], time.time() - started, res["message"]), flush=True)
    if res["status"] != installer.INSTALLED:
        bad.append("%s: %s" % (t.id, res["message"]))
        continue
    after = {x["id"]: x for x in api.list_tools()}[t.id]
    if not (after["usable"] and after["app"]):
        bad.append("%s installed but can't be opened: %s" % (t.id, after))

print("\n".join(bad) or "All Windows tools installed from the Studio.")
sys.exit(1 if bad else 0)
