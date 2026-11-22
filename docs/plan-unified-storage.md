# The great unifying: one show, every app (storage, audio, Pi, quieting the rig)

First written 2026-11-20 in the video_streamer session. **Revision 2, same day, in steezy_studio**: checked against the
code and the drive, then an interview with Stefan. Where this revision and older notes disagree, this revision wins.
Older history: `~/.claude/plans/i-want-to-start-toasty-bentley.md` and the video_streamer memory `grand-storage-plan.md`.

## Revision 4 (2026-11-22, steezy_studio): where the drive work ended up
**Where this section and the rest of the doc disagree, this section wins.** The one-time drive work is done.
- **Done:** the 2TB is mirrored to the Mac, every MXF is shrunk and its original deleted (each with Stefan's OK), and
  the Final Cut libraries point at the 2TB files. To-do steps 1–3 and 5–7 below are finished.
- **Dropped:** step 4 (the firmware update). The drive was bought in 2026 and SanDisk offers no update. Step 8 (resize
  and "Shows") was already dropped in revision 3. The 2TB stays one partition, "2TB Storage" (HFS+) plus "2TB AUDIO".
- **The Mac mirror is the Mac's backup of the 2TB:** `~/2TB Mirror/{2TB Storage,2TB AUDIO}`, 10,036 files, all
  SHA-256 checked. Trim it later when the Mac needs room.
- **Shrink rules changed (supersedes ruling 6 and the "SSIM gate around 0.99" line):** 60 Mbps for 4K24, passing at
  mean SSIM 0.98 and every 3 s window at 0.97. **Every audio track is kept**, because Final Cut only relinks when the
  channel counts match. The MXFs were shrunk to .mov with all 8 audio tracks (Litty D at 100 Mbps).
- **Check records stay out of the show folders.** They live in `~/Library/Application Support/Show Mover/records/`.
- **No more relinking:** Movie Maker builds from the 2TB files, so a Final Cut library is never relinked after a move.
- **Cleanup still to do** (one at a time, each asks first):
  - each show's multitrack goes in its own `<Show> Audio/` folder (Pabsy's 22 WAVs are still inside the Ableton
    project's `Samples/Imported/`; Litty D Misco 4 has copies in both places);
  - Litty D shows get no `Logos` folder (their logos live elsewhere), and Movie Maker's `ensure_show_folders` must
    stop creating one for them.
- **Known damage:** `2TB AUDIO/Multitrack/0006/LineR IPOD R_00.wav` lost its last 1.2 s (a bad FAT32 cluster chain).
  The mirror holds the readable part.

## Revision 3 (2026-11-21, video_streamer session): a dedicated PI RECORD drive replaces the "Shows" partition
**Where this section and the rest of the doc disagree, this section wins.** Stefan's ruling: the 2TB keeps ALL final
files including Final Cut libraries, stays Mac-format, and is NOT partitioned or shrunk. The Pi records to a separate drive.
- **PI RECORD** is a new portable SSD (500GB, or 1TB if the price gap is small), exFAT, plugged into a blue USB 3 port.
  It takes over the job of the "Shows" exFAT partition: the Pi's live recording target and the phones' upload target.
  It also works standalone when the 2TB is somewhere else. Test sustained write speed (about 30 GB) before relying on it.
- **Dropped:** the HFS+ resize step (to-do 8) and the "Shows" partition. The 2TB is never touched by the Pi.
- **The Soundcraft's 500GB stick stays in the mixer** as the mixer's own audio backup.
- **Destination order:** PI RECORD (found by label/UUID) -> a guest drive Stefan approved -> SD card (last resort).
  The iPad names the drive in use and shows green/amber/red. It never switches quietly.
- **Guest drives** (a customer's drive, with permission): a new drive shows on the iPad with name, format, free space and a
  contents summary, and nothing is written. Stefan picks Use as is / Reformat to exFAT / Ignore. Reformat needs a typed
  confirmation, a list of what will be erased and an owner-permission tick-box. Nothing is ever formatted automatically.
- **Show Mover, one rule and two questions.** A Mac always writes the destination. Where are the files (PI RECORD plugged
  into the Mac, or still on the Pi)? Where should they go (the 2TB, the Mac's own disk, or any other drive)? Plugged in is a
  direct USB copy. Still on the Pi means the Pi sends over Wi-Fi/Ethernet to the Mac helper (`video_streamer/tools/mac_helper.py`,
  already has resume and SHA-256; the Pi needs a Python sender that speaks the same protocol the phones use today).
  If the 2TB is plugged into the Pi, the show waits on PI RECORD until a Mac is on the network. Delete from PI RECORD only
  after the destination reports it verified.
- **Unchanged:** the multitrack recorder (22 channels, 24-bit), the `.part`/fsync rules for exFAT, Quiet the rig, the
  MXF shrink. All of "Recording safely to exFAT" now applies to PI RECORD instead of the Shows partition.
- **Still to build** (none of it exists yet): drive detection by UUID/label with `nofail` mounts, automatic fallback, recorder
  rollover for FAT32's 4GB limit, reopen after an unplug, read-only detection, guest-drive mode, Show Mover.
- **Built 2026-11-21 (video_streamer branch `recording-method`, not pushed, nothing deployed):** manual-only collecting with prompts, PI RECORD / guest drive / SD handling with the iPad pill and guest-drive flow, recorder fixes, 32-channel multitrack recorder (+ stage_lighting branch `multitrack-tap`, VST2 on port 9411), Pi sender to the Mac helper, Mac app starting the helper and announcing itself, phone-hosted control room in the Android app (0.27). Show Mover's move/verify/delete is on branch `show-mover` of the separate `show_mover` repo. All unit-tested; none of it has run on the real Pi, rig or phones yet.
- A picture of the whole method is the private artifact "Show Recording Method" (https://claude.ai/artifact/JXvYv4fS1XBgYgVwsoKnU7).

## The goal (Stefan's words)
"I just start show, end show, and it's all there (eventually). All I have to do is plug the 2TB into my Mac and edit
video right after the show." Keep it as simple as it is now.
- video_streamer puts the files in the right place.
- movie_maker opens the show with no setup.
- ableton_loader builds the Ableton project straight from the multitrack.
- stage_lighting shares the Pi efficiently and can be quieted safely.
- **"Quiet the rig"** makes the whole rig safe to switch off.

## Stefan's rulings (these win over anything older)
1. **The 2TB SanDisk is home:** the long-term store and where he edits.
   - The Mac is temporary, only for a few shows while he travels. No Mac importer.
2. **Clean up first, then the Mac backs up the one-time drive work.**
   - Free the Mac's space, then make a full checked copy of the 2TB on the Mac.
   - That copy must exist before the firmware update, the resize and the MXF deletes.
   - Afterwards the Mac keeps the audio plus finished shows. Raw phone footage can go once the edit is done.
   - A big backup drive comes "eventually".
   - **Nothing is ever deleted before its copy has been checked:** SHA-256, plus a full decode and SSIM for
     transcoded video.
3. **If the 2TB is plugged into the Pi, record straight to it.** Use the SD card as little as possible.
   - A **256 GB endurance SD card** is only the fallback for when the 2TB is missing.
4. **After a phone file is verified on the 2TB, the Pi deletes it from the phone.**
5. **Audio:**
   - The Pi is the **main multitrack recorder**. It keeps only USB channels 11–32 (22 channels):
     - 11–30 are the real inputs and 31–32 are aux;
     - 1–10 are the 2 mains plus 8 monitor sends;
     - mains 1+2 are still used as the video's sound.
   - The Soundcraft's own USB stick is a **backup used only if Stefan sees the Pi failing.** He doesn't plan to run
     both.
6. **MXFs:** keep audio track 1 only, as mono (tracks 2–8 are silent on all 9 files). Shrink them to HEVC.
7. **"Shows" is only the Pi's inbox.**
   - At home, **Bring in this show** moves the show into `2TB Storage/<band>/<show>/` and checks it.
   - He edits there, Ableton and Final Cut side by side.
   - Nothing moves after that, so nothing needs re-linking.
8. **Quiet the rig, not power down.** The Pi stays on.
   - Stage Lighting **stops sending anything** (DMX and Govee), and the lights hold their last state. No blackout.
   - **Wake the rig** resumes everything.
   - Stefan switches things off himself.
9. **No UPS and no rugged hub for now.**
   - The ports are SSD, webcam, Soundcraft and DMX.
   - The Pi Camera is wanted but on the backburner.

## What was checked (2026-11-20, read-only)
- **Shrinking "2TB Storage" needs no wipe.**
  - `diskutil resizeVolume disk4s2 limits` gives a minimum of 1.48 TB today.
  - HFS+ moves files during a resize, so after the MXF shrink (~0.93 TB used) 1.2 TB is reachable.
- **Phone uploads are already checked.** `video_streamer/tools/mac_helper.py` builds each file's SHA-256 as it arrives
  and compares it with the phone's (`finish`). It also keeps verified.json/done.json, so deleting from the phone is
  mostly wiring.
- **The audio tap can carry the multitrack.** `stage_lighting/ui24_audio.py` `VideoTap` sends one UDP packet per
  block.
  - With 384 frames, 22 channels and 3 bytes per sample, that's about 25 KB per packet at 125 packets/s.
  - That's well under the UDP limit, about 3.2 MB/s over localhost.
- **movie_maker** already accepts .wav/.flac and every video type we record (`fcpkit/project.py`). It re-links its own
  project media when a show folder moves.
- **ableton_loader** reads only .wav/.mp3 (`ableton_loader/audio.py`). So the Pi records WAV, and no FLAC work is
  needed.
- **Final Cut can't keep a library on exFAT.** That's why ruling 7 exists: you edit in "2TB Storage" (HFS+), not in
  "Shows".
- **The Mac** has 406 GB free. Time Machine still takes hourly local snapshots for the unused "Backup Mac", the likely
  cause of the missing ~900 GB.

## The 2TB layout (SanDisk Extreme 2TB, disk4, GPT)
- **"2TB AUDIO"** (FAT32, 200 GB, 77 GB used): untouched.
- **"2TB Storage"** (journaled HFS+): **where shows live and get edited.**
  - Shrunk to about 1.2 TB after the MXF shrink.
  - Band folders: `Litty D/`, `Other bands/`, each show self-contained.
  - The Pi never writes here, because Linux won't write journaled HFS+.
- **"Shows"** (exFAT, about 600 GB, new): **the Pi's inbox.** exFAT so the Pi can write to it. It holds about one full
  8-phone show waiting to be brought in.

### Per-show folder (movie_maker's canonical layout)
```
Shows/<YYYY-MM-DD name>/                     name typed on the iPad at Start show (prefilled with the date)
  <show> Video/                              one file per phone/angle, named after the device ("Front.mp4")
  <show> Audio/                              one 24-bit mono WAV per channel 11–32, Ui24 names ("15 KICK.wav"); gaps.log
  <show> Full Show (desk).wav                mains 1+2, a ready sync reference until the real north star is mixed
  show.json                                  manifest: every file, SHA-256, source, start time, verified state
```
After Bring in this show, the folder sits at `2TB Storage/<band>/<show>/`. Movie Maker adds `<show> Data/` and the
Final Cut library, and Ableton adds `<show> Project/`.

## Show-night flow
1. **Start show.**
   - The iPad sends its clock to the Pi first. The Pi has no clock that survives a power-off, so it adopts the iPad's
     time if it's more than 2 s off.
   - Phones record 4K on themselves.
   - The Pi records guest video, the USB cam and the 22-channel multitrack **straight to "Shows"**.
   - The iPad control room shows a **Multitrack row**: recording or not, channel count, gaps, and minutes of space
     left. It turns red if the packets stop, which is the moment to press record on the mixer stick.
   - No 2TB: the Pi uses the SD fallback and the iPad says so in red.
2. **End show.** Pi recordings are finalized in seconds. Phones upload to the Pi, which checks each file, then deletes
   it from the phone.
   - About 320 GB for 8 phones × 2 h takes **2–4 h** if the Pi is wired to the router, longer over Wi-Fi (check this).
   - Need the drive early? Press **Quiet the rig**, then unplug. Phones keep their files and catch up next time.
3. **Quiet the rig** (below), then switch off whenever.
4. **Home:**
   - Plug the 2TB into the Mac.
   - **Bring in this show**, choosing the band.
   - Edit.

**No 2TB:** phones keep everything. The Pi records the multitrack and guests to the 256 GB SD card. When the 2TB comes
back, the Pi copies, checks, then frees the SD.

## Recording safely to exFAT (it has no journal)
- **The recorder never waits on the disk.**
  - One thread reads the tap with a big receive buffer and queues packets.
  - A writer thread writes `.part` files, flushes (`fsync`) about every 2 s and rewrites the WAV header each time.
    It renames at the end.
  - Sequence gaps go to `gaps.log`.
  - A crash loses seconds, never earlier files.
- **The tap stays fire-and-forget**, so the lights always come first.
- **Mounting:**
  - The 2TB is mounted by UUID with `nofail,noatime` and checked with `fsck.exfat` when plugged in.
  - The Pi still boots without it.
  - The Pi ignores the Mac's `._*` and Spotlight files.
- **The status light:**
  - **green:** nothing is being written, so unplug or switch off any time;
  - **amber:** writing, so wait or press Quiet the rig.

## Quiet the rig
- **One button** (iPad control room and Steezy Studio).
- **It does these, in order, and shows each tick:**
  1. Pauses transfers once the current upload chunk finishes. Uploads are resumable.
  2. Finalizes every recording (closes the files, the last flush, the manifest).
  3. **Lights:** stage_lighting stops sending DMX and Govee commands. The lights hold their last state.
     - Most DMX fixtures hold their last value when the signal stops.
     - If one blacks out or starts a demo mode instead, change that fixture's menu setting.
  4. Syncs and unmounts the 2TB.
  5. Shows a big green **"Safe to switch off"**. The Pi stays on.
- **Wake the rig** reverses it: remount, the lights resume, uploads continue.

## Pi efficiency (sharing with stage_lighting)
- **One USB reader of the mixer:** stage_lighting already reads all 32 channels and hands audio to video_streamer
  through `VideoTap`. That tap can never slow the lights.
- **Extend the tap** to send channels 11–32 at 24-bit to a video_streamer recorder:
  - numbered packets, with gaps logged;
  - hardware test: `stage_lighting/hil/test_video_tap.py`;
  - processor load measured live.
- **USB facts (checked with lsusb -t):**
  - every USB 2 device shares one 480 Mbps lane: Soundcraft, DMX and the webcam;
  - the 2TB sits alone on USB 3;
  - the hardware H.264 encoder is unused, so it's free for the Pi Camera.

## Show Mover (new standalone Steezy Studio tool, used by every app)
- **Bring in this show:**
  - moves it from Shows to `2TB Storage/<band>/<show>/`, checks every SHA-256, then deletes it from Shows;
  - optionally imports the mixer stick's files.
- **Take to the Mac / bring back** for travel.
- **Shrink, in place:** HEVC 10-bit on the Mac's hardware encoder.
  - Keep the timecode, colour tags and frame count.
  - Audio stays lossless (camera audio as mono PCM).
  - SSIM gate around 0.99.
  - movie_maker re-links on open. A Final Cut library needs one File › Relink Files.
- **A space report.**
- movie_maker and ableton_loader each get a button that calls it.
- **Test (2026-11-20):** a 20-second MXF excerpt at 60 Mbps came out 71% smaller with SSIM 0.995. The M3 encodes about
  2× real time.

## To do, in order (ask Stefan before any step that writes to a drive)
1. **Clean up the Mac** (Stefan does the System Settings part).
   - Time Machine: remove "Backup Mac".
   - `tmutil deletelocalsnapshots /`.
   - Measure the free space again.
2. **Plug in "Backup Mac"** (500 GB, holds old files that exist nowhere else) and scan it read-only.
3. **Copy the audio to the Mac** (~260 GB, fits today), checked. Music comes before video.
4. **SanDisk firmware update.** Stefan runs it from the [WD firmware page](https://www.westerndigital.com/support/firmwareupdate).
5. **MXF shrink in place** on "2TB Storage". The originals stay until Stefan reviews the results.
6. **Full copy of the 2TB to the Mac** (~1.0 TB), every SHA-256 checked.
7. **Delete the MXF originals, show by show.** Then remove the byte-identical Misco 4 copies in
   `~/Movies/Litty deBungus.fcpbundle/Misco 4/Original Media` (196 GB), after relinking in Final Cut.
8. **Resize "2TB Storage" to ~1.2 TB and add "Shows"** (exFAT, ~600 GB). Move existing shows into band folders only if
   Stefan wants.
9. **New Pi SD card** (256 GB endurance): the system plus a fallback recordings part, using
   `video_streamer/tools/pi_sd_image.sh`.
10. **Pi drive handling:** mount, damage check, `.part`/fsync, the green/amber light, the SD fallback.
11. **Multitrack recorder:** channels 11–32, 24-bit WAV, straight to "Shows", plus the iPad Multitrack row.
12. **Phones:** upload → check → delete.
    - The Android uploader and the Pi helper already exist: `video_streamer/tools/mac_helper.py`, `MacLink` in
      `video_streamer/vsapp/app.py`.
    - Point them at "Shows".
13. **`show.json` plus the iPad clock at Start show;** movie_maker auto-adds a folder that has a `show.json`.
14. **Quiet the rig / Wake the rig:** the button and stage_lighting's "stop output" mode.
15. **Show Mover** app and library, plus buttons in movie_maker and ableton_loader.
16. **Tests:**
    - a full rehearsal;
    - pulling the plug mid-write;
    - a show with no 2TB;
    - a kill mid-upload;
    - a bad hash;
    - Quiet → switch off → on → Wake.
17. **Later:** the Pi Camera (rpicam-vid H.264 in the same copy path as the USB cam). A UPS if an unplanned power cut
    ever bites. A big backup drive.

## Still to check on the real Pi (read-only, only when Stefan says so)
- The kernel has exFAT and `exfatprogs` is installed.
- Whether the Pi is wired to the router or on Wi-Fi. That sets the upload time.
- Whether the Pi powers the SanDisk plus the webcam without a hub (if not: [StarTech ST4300USBM](https://www.cdw.com/product/startech-4pt-rugged-usb-3.0-hub/2294100)).
- What each DMX fixture does when DMX stops.

## To buy
- [Samsung PRO Endurance 256 GB microSD](https://www.samsung.com/us/memory-storage/memory-card/pro-endurance-adapter-microsdxc-256gb-sku-mb-mj256ka-am/)
- **Backburner:** [Raspberry Pi Camera Module 3 Wide](https://www.raspberrypi.com/products/camera-module-3/) plus a
  15-pin ribbon of about 1 m.
- **Later, if needed:**
  - [Geekworm X728 UPS](https://geekworm.com/en-au/products/x728) for unplanned power cuts. Test it first: one report
    says it [cuts power too early](https://geekworm.com/community/forum/topic/23709/x728-is-shutting-off-the-power-too-quickly-before-the-rpi-has-properly-shut-down).
  - A big backup drive (4 TB or more).

## Space (2026-11-20)
- **2TB:**
  - AUDIO: 200 GB.
  - Storage: about 1.2 TB, with about 270 GB free after the shrink.
  - Shows: about 600 GB.
- **Mac:** 406 GB free, plus whatever the snapshot cleanup frees. A full 2TB backup needs about 1.0 TB.
- **The real limit:** each full show is about 320 GB raw. Shrinking shows after the edit keeps the 2TB from filling.

## Inventory facts (read-only scan, 2026-11-20)
- **The drive:** 6,078 files.
  - MXF: 526 GB (4K, 4:2:2 10-bit, 240 Mbps, 8 mono PCM tracks, only track 1 live).
  - Phone and GoPro 4K HEVC: about 530 GB (already efficient, leave as is).
  - Other video: about 200 GB.
  - Audio: about 260 GB (wav 187, aif 62).
- **Ui24R:** records up to 22 inputs to a USB stick as WAV or FLAC, 16- or 24-bit, plus an LR stereo file
  ([Soundtech](https://soundtech.co.uk/news/recording-with-the-ui24r)).
