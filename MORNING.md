# Morning report: Steezy Studio, sessions 1-3

Everything in the plan ran; steps 1-11 are ticked in OVERNIGHT.md and nothing is BLOCKED.
`stefanturk/steezy_studio` (private) is pushed. The four tool repos have since been pushed.

## What you have now
- **Steezy Studio.app** in `~/Applications` (signed with a local certificate; pin it to the Dock).
  A tile per tool with version, Open, an amber dot when updates are waiting, and **Update all**.
- **The engine** at `~/Library/Application Support/Steezy Studio/engine`: Python 3.12.15 + ffmpeg,
  SHA-pinned, no Homebrew, no password.
- **Tool commits (since pushed):**
  - beat_thief `5a7bc2b` borrows the engine on a fresh install
  - ableton_loader `3c08b8a`, movie_maker `4be10f4`, session_sync `e6f447b` build on the engine when it is there
  - Every tool has a `pre-studio` tag to roll back to.

## Please do (about 10 minutes)
1. Open Steezy Studio. macOS will ask once to read your Desktop: **Allow**. (Not tested by me; I avoided
   your Desktop on purpose.) Check the four tiles show real versions and Open launches each tool.
2. Press **Update all** once. Expect "ahead / nothing to update" notes for all four (see above).
3. Decide on the open items below.

## What I verified (all on scratch copies unless stated)
| Step | Evidence |
|---|---|
| 2 engine | scratch install gives Python 3.12.15 + ffmpeg 9.0.2; corrupted download rejected; rerun is a no-op |
| 3 signing | two builds with different contents share one designated requirement; ad-hoc ones differ |
| 4 Beat Thief | fresh install used the engine, 0 Python/ffmpeg downloads; 207 tests same as before; fidelity output byte-identical |
| 5-7 registry, window, Update all | 33 tests pass: missing/private/broken tools, dirty, ahead, diverged, no network, one tool failing, dry run changes nothing |
| 8 app | built, strictly signed, launched for real, clean log, quit cleanly |
| 9 other tools | tests on the engine equal baseline: Loader 373 (2 skipped), Movie Maker 307, Session Sync 260 |
| 10 real folders | dry-run Update all over your 4 real folders: git state, refs, trees and apps identical before/after |

## Not verified by me
- How the window looks and feels in practice; I reviewed a Chrome render and one real screenshot.
- The Desktop permission prompt, and Open on each tool from the Studio.
- Session Sync's engine-built app was never launched (it could start a real Drive sync).
- Real Final Cut import, friends' Macs and Windows (sessions 4 and 5).

## Open items for you
1. **Shared engine packages.** All tools share one site-packages, so the last `pip install` wins.
   Movie Maker needs PyObjC 12 (13 breaks its font measuring) plus numpy 1.26.4 / scipy 1.13.1;
   Beat Thief passes on the same pins but does not pin PyObjC or SciPy itself, so an update there could
   re-upgrade them. Options: pin the same set in beat_thief/requirements.txt, or give each tool its
   own virtual environment on the engine. I'd lean to pinning now, venvs if it keeps biting.
2. Push the tool repos when you are happy (`git push` in each). Movie Maker still has 91 and the
   Loader 12 uncommitted files of yours, untouched.
3. Loader tests need pytest < 9 (a test-only quirk, not the app).
4. The toolkit is pywebview (like your other tools), not Qt, so the plan's "Qt offscreen screenshot"
   became a headless-Chrome render plus a real launch.
5. The cron job was session-only and permissions were manual/auto mode; it never needed more.

## Next sessions
4. Friend installer (one-line, pick tools, GitHub invite + sign-in); 5. Windows (PowerShell engine,
Loader/Session Sync/Beat Thief fixes, GitHub Actions Windows runner).
