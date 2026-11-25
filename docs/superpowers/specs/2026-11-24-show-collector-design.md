# Show Collector: design

Status: approved in conversation 2026-11-24, not yet built. Nothing deployed or pushed.

## Why
After a show the video is on phones (and the Pi, SD cards, guest drives). Getting it onto the 2TB is split across
`video_streamer/tools/mac_helper.py` (receiver on port 9300: resumable, SHA-256 checked, never overwrites),
`video_streamer/tools/pull_recordings.sh` (adb pull and repair), the Pi's vsapp "brain" (tells each phone where to
send) and Show Mover (`show_mover`, branch `show-mover`: move, verify, delete). No single window shows progress or
where each file lives. `docs/plan-unified-storage.md` already says "a Mac always writes the destination".
Stefan asked for this app in the video_streamer session of 2026-11-25 (UTC).

## What it is
A Mac-only, private Steezy Studio app for Stefan alone. Repo `show_collector`, registry tile "Show Collector".
It is the front end over existing pieces: it owns and runs the receiver, uses Show Mover for copy, check and delete,
and shows everything in one window.

## Version 1
- **Phones over Wi-Fi.** Phones on ShainyNet send themselves to the Mac; the app shows each phone's progress, speed,
  time left, with Pause.
- **Plugged-in drives to the 2TB.** SD cards, PI RECORD, guest drives: pick a show, copy and check.
- **Show overview.** Every show with its video and audio, and where each copy is (phone, Pi, drive, 2TB). Read-only.
- **Success on night one:** open the app after a show, phones send themselves, the window ends on a green
  "all safe on 2TB".

## Screens
- **Now:** a card per phone or drive (progress, speed, time left, Pause) and a status line ("3 of 3 phones safe on 2TB").
- **Shows:** show cards with where each copy lives.
- **Drives:** plugged-in drives, pick a show, Copy and check.

## Decisions (Stefan's)
- **Receiver owner:** Show Collector runs mac_helper and starts it at login. It is also used as a main app, so it must
  be flexible. If both Show Collector and Video Streamer run, Show Collector runs the receiver.
- **Originals are auto-deleted after the check** (a deliberate change from Show Mover's "nothing deleted without an OK"),
  with three safeguards:
  1. Re-read check: delete only after the file is read back from the 2TB and its SHA-256 matches the original's.
  2. Only phones and the Pi auto-delete. SD cards and guest drives are copied and checked, never wiped by the app.
  3. The newest show's originals are never auto-deleted, so last night always has two copies.

## My calls (change any)
- If port 9300 already answers, Video Streamer attaches instead of starting a second receiver.
- Python with the same GUI style as Show Mover and Movie Maker; imports `mac_helper` and `show_mover` as libraries
  (no second receiver, one verification path).
- Mac only, private repo with an invite, like Stage Lighting.

## Approaches considered
1. New app on top of the existing pieces. **Chosen:** least new code, one verification path.
2. Grow a window inside Show Mover. Rejected: Show Mover is a shared library, not a front end.
3. Rewrite a receiver inside the app. Rejected: duplicates the tested resume and SHA code.

## Non-goals
Phones by USB cable (later), Windows, public release, changes to the phone app, touching the live lighting rig.

## Left to the builder
- How phones and the Pi announce themselves, and how the brain learns the Mac is reachable. The per-phone routing
  change on the Pi side is a separate video_streamer job.
- ~~The delete path for phones~~ Answered while building: the Pi's brain (`vsapp`, `_auto_clear`) already tells a phone to delete a
  file once the receiver answers `X-Archive: 1`. Show Collector gates that answer (older show, re-read matched) and never deletes itself.
  With no Pi and no Mac-side brain running (Video Streamer's Mac app), nothing clears a phone: the app shows "safe on 2TB" only.
- Registry entry, icon, `make_app.sh`, and tests like the other apps.
