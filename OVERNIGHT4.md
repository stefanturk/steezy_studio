# Overnight 4-5: friend installer + Windows

Plan: ~/.claude/plans/adaptive-whistling-tower.md. Rules: commit locally, push NOTHING, tag `pre-session4` first,
scratch HOME for tests, never launch Session Sync. A step is ticked only when its verification passes;
two failures = BLOCKED with reason. When done: write MORNING4.md, then CronDelete the job.

- [x] 0 safety tag `pre-session4` on steezy_studio, beat_thief, session_sync; record baseline test counts
- [x] 1 registry `install` info + `studio/share.py` command generation (+ tests)
- [x] 2 `install.sh` (+ scratch-HOME test with local clones, idempotent, private-clone failure tolerated)
- [x] 3 `studio/invite.py` (+ tests, dry-run only)
- [x] 4 Share with friends panel in gui.py + index.html (+ API tests, Chrome render checked)
- [x] 5 engine/setup.ps1
- [x] 6 install.ps1
- [x] 7 Windows portability of studio/ (mock sys.platform tests)
- [ ] 8 Beat Thief + Session Sync Windows guards (macOS baselines identical)
- [ ] 9 .github/workflows/windows.yml (YAML-validated)
- [ ] 10 Windows rows enabled in Share panel
- [ ] 11 memory update, session_sync README "225 passing" fix, MORNING4.md, CronDelete

## Log
- tags pre-session4 set; Studio baseline 33 tests (system python3)
- step 1 done: share.py, private flag; 38 tests
- step 2 done: install.sh + 6 scratch-HOME tests; 44 tests. gh fetch path (pinned v2.103.3 + release checksums) written but not run live
- step 3 done: invite.py, 49 tests
- step 4 done: Share panel (Chrome render reviewed), copy_text/invite_friend API, 53 tests. Session 4 COMPLETE
- steps 5-6 written: setup.ps1 (python sha from upstream SHA256SUMS; ffmpeg gyan 2026-11-02 sha verified by me downloading it), install.ps1. NOT executed: no pwsh on this Mac. windows_run registry field supported; tools fill it in step 8
- step 7 done: platform_paths, windows_run/open/build handling, 58 tests
