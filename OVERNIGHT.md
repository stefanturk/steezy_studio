# Overnight checklist (plan: ~/.claude/plans/adaptive-whistling-tower.md)

Status: [ ] todo, [x] done, [!] BLOCKED

- [x] 1. Init repo, README, OVERNIGHT.md, tests folder
- [x] 2. engine/setup.sh (pinned python 3.12 + ffmpeg)
- [x] 3. Local self-signed identity
- [x] 4. Beat Thief onto the engine
- [x] 5. registry.json + loader
- [x] 6. Launcher GUI
- [x] 7. Update all
- [x] 8. Steezy Studio.app
- [x] 9. Other three tools on the engine
- [x] 10. Dry-run Update all on real folders
- [ ] 11. Push + MORNING.md + memory

## Log
- 2026-11-02 22:37:52 step 2 verified: scratch install gives python 3.12.15 + ffmpeg 9.0.2; bad SHA rejected; rerun is a no-op
- 2026-11-02 22:38:43 step 3 verified: identity 'Steezy Studio Signing' created; two differing builds share designated requirement (cert hash 14a99bcf...); ad-hoc differs
- 2026-11-02 22:42:30 step 4 verified: beat_thief setup.sh adopts engine (0 python/ffmpeg downloads in scratch HOME); tests 207/1 existing failure same as baseline; beat_fidelity identical; pre-studio tag on beat_thief; commit local only
- 2026-11-02 22:51:00 step 5 verified: 9 registry tests pass (missing folder, no git, no access, crashing access check, malformed entries, unreadable registry); real folders all READY
- 2026-11-02 23:14:58 step 6 verified: 15 tests pass (registry + gui Api incl. dirty/behind via real git repos); page rendered in headless Chrome with real list_tools data + fake no_access/broken tiles, screenshot reviewed. Deviation: toolkit is pywebview (family standard), not Qt, so no QT offscreen; real pywebview window is first opened in step 8. Fixed registry app name SessionSync.app
- 2026-11-02 23:51:39 step 7 verified: 11 updater tests on throwaway bare-repo clones (up to date, behind, dirty, ahead, diverged, no network, build failure, exception, unavailable, missing app, dry run changes nothing) + Api update_all test; 33 tests total pass; Update all button rendered and reviewed (headless Chrome, mocked status)
- 2026-11-03 00:15:14 step 8 verified: make_app.sh built Steezy Studio.app into scratch dest on scratch engine (installed pywebview itself); codesign --verify --strict ok, designated requirement = com.stefan.steezystudio + cert hash 14a99bcf; real launch via open (STEEZY_TOOLS_DIR=empty dir to avoid Desktop prompt): window titled Steezy Studio with greyed tiles, Dock icon is the logo, process stayed up, log clean, quit cleanly. NOT yet installed to real ~/Applications or real engine: done at end of run / morning.
- 2026-11-03 00:56:42 step 9 verified: pre-studio tags on ableton_loader/movie_maker/session_sync. Engine-detection with fallback in each build script (local commits 3c08b8a, 4be10f4, e6f447b; not pushed). Tests on engine python = baseline: loader 373p/2s, movie_maker 307p, session_sync 260p. FINDINGS: (1) engine packages must be pinned: PyObjC 13 breaks movie_maker font_audit; pytest 9 breaks 2 tests; movie_maker/requirements.txt now pins numpy 1.26.4 scipy 1.13.1 pillow 11.2.1 pyobjc 12.0 family; beat_thief 207 tests + fidelity identical on that set (its old scipy failure disappears). (2) all tools share one engine site-packages so last pip writer wins: beat_thief requirements are unpinned for pyobjc/scipy and could re-upgrade; decide a shared constraints approach. Existing Loader/Movie Maker uncommitted work left untouched. Session Sync app not launched (could trigger a real Drive sync).
- 2026-11-03 01:13:54 step 10 verified: dry-run Update all (fetch=False, dry_run=True) over the 4 real folders; before/after snapshot of HEAD, all refs, porcelain status hash, FETCH_HEAD and ~/Applications mtimes IDENTICAL. All four report skipped_ahead (local unpushed commits from tonight), as designed.
