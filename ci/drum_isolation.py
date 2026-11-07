"""CI on Windows: a real Beat Thief drum separation on a short generated clip.
Run with pythonw (as the Start-menu shortcut does) so sys.executable is pythonw,
exactly like the GUI. pythonw has no console, so the outcome goes to argv[2].
  pythonw ci/drum_isolation.py <beat_thief folder> <result file> <clip.wav>"""
import json
import os
import sys
import traceback

bt, out, clip = sys.argv[1:4]
sys.path.insert(0, bt)
os.chdir(bt)
result = {"ok": False}
try:
    import instrument_isolator
    # As the GUI does (pipeline.py passes on_percent): pythonw has no stdout
    # for the terminal progress bar.
    seen = []
    ctx = instrument_isolator.RunContext(interactive=False, on_percent=seen.append)
    stems = instrument_isolator.separated_stems(clip, "htdemucs", ctx)
    files = sorted(os.listdir(stems))
    result = {"ok": "drums.wav" in files, "stems": files, "dir": stems,
              "last_percent": seen[-1] if seen else None, "drums_bytes": os.path.getsize(os.path.join(stems, "drums.wav")) if "drums.wav" in files else 0}
except BaseException:
    result["error"] = traceback.format_exc()
with open(out, "w") as f:
    json.dump(result, f, indent=1)
sys.exit(0 if result["ok"] else 1)
