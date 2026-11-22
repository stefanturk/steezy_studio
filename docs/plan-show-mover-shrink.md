# Show Mover: Shrink (draft for Stefan, 2026-11-20)

## Why
The MXF shrink saves ~75% with no visible change. Stefan wants the same for any other big formats he comes across
(ProRes exports, intra camera files, high-bitrate H.264, 1080p or 4K), without hand-tuning each time. "It should
work when I come across them", and there are no real test files.

## Goals / non-goals
- **Goal:** point it at a show (or the whole 2TB):
  - it finds the files worth shrinking and estimates the saving;
  - it shrinks the ones you tick into `Shrunk (review)/`;
  - it proves each one is right;
  - after your OK it swaps them in.
- **Non-goal:** touching anything already efficient (HEVC/AV1, phone and GoPro footage), finished exports you've
  posted, or audio for active shows.
- **Anti-goal:** a silent quality loss, a broken Final Cut or Movie Maker project, or deleting an original without
  your OK.

## The rule (one formula for 1080p, 4K, any frame rate)
- **Target size:** HEVC 10-bit on the Mac's hardware encoder at **0.30 bits per pixel per frame**. That's what the MXFs
  got: 4K 23.976 → 60 Mbps; 1080p 30 → 19 Mbps. Clamped to 8–100 Mbps.
- **Candidate:** a file is a candidate only if its video uses at least **2× the target** (≥ 50% saving) and isn't
  HEVC/AV1.
- **What gets shrunk:** ProRes, intra H.264/HEVC (XAVC-I, AVC-Intra, All-I), high-bitrate long-GOP H.264
  (XAVC S/HS, DSLR), MJPEG/DNx.
- **Kept as is:** resolution, frame rate (variable frame rate passes through), frame count, start timecode, creation
  date, and colour tags. Colour covers SDR Rec.709, HLG and PQ HDR, and HDR10 mastering metadata where present.
- **Audio:** every track that isn't silent (measured), kept bit-identical. PCM stays PCM at its own bit depth, and
  AAC is copied without re-encoding. Silent tracks are dropped and listed.
- **Skipped and reported, never guessed:**
  - interlaced video (1080i AVCHD);
  - files with transparency (ProRes 4444 alpha);
  - anything ffprobe can't read cleanly.

## The checks (every file, all must pass, or the shrunk file is thrown away)
- A full decode of the new file with no errors.
- The same frame count, timecode and colour tags.
- Every kept audio track bit-identical (MD5 of the decoded PCM).
- SSIM of **every frame**: mean ≥ 0.99, every 3-second stretch ≥ 0.985.
- The SHA-256 of the result goes into a check file next to it.

These are the checks the MXF batch uses now. Frame-by-frame comparison replaced spot-checks because jumping into an
MXF isn't frame-accurate.

## Testing without real files
- **Tests generate their own 2–4 s clips with ffmpeg.** One for each kind:
  - ProRes 422 HQ, and ProRes 4444 with alpha (should skip);
  - 10-bit 4:2:2 H.264 intra HLG with 8 mono tracks, 7 of them silent (the MXF case);
  - 150 Mbps long-GOP H.264;
  - 1080i (should skip);
  - variable frame rate;
  - PQ HDR10 with mastering metadata;
  - HEVC (should skip);
  - AAC audio.
- **Each test** checks the decision, the output's properties and the checks.
- **Some tests prove the checks fail when they should:**
  - a dropped frame;
  - changed audio;
  - stripped colour tags;
  - a crushed bitrate (low SSIM).
- **An opt-in real-file test** runs on `Heels.MXF` when the 2TB is plugged in.

## Swapping in (after your OK, per show)
- The new `.mov` moves into the original's folder.
- The original goes to the drive's Trash (`.Trashes`), so it's undoable until you empty it.
- **Movie Maker:** re-linking needs one change. It matches moved files by path, but the extension changes
  (`.MXF` → `.mov`), so the re-link must also accept "same name, new extension".
- **Final Cut:** libraries that used the file need one File › Relink Files. The swap report lists which libraries.

## Approaches
1. **New sibling repo `show_mover/`** (like `music_detector/`): a core package + CLI + tests now; the Studio app and
   the Movie Maker / Ableton Loader buttons later. Bring in, Take to the Mac and the Space report join it.
   **Recommended.**
2. Inside movie_maker (`fcpkit/archive.py`, the older plan). Quicker to start, but video_streamer and Studio would have
   to reach into movie_maker.
3. Keep scratchpad scripts. Fast, but not durable, not tested, and lost when the scratchpad is cleared.

## Order
1. `show_mover/` core: probe → decide → encode → check, plus the synthetic tests.
2. Space report (read-only scan of the 2TB: candidates, estimated savings, Final Cut libraries holding copies).
3. The swap step plus the Movie Maker "new extension" re-link.
4. Later: the Studio app face and Bring in this show.
