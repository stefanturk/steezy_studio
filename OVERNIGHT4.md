# Overnight 4-5: friend installer + Windows

Plan: ~/.claude/plans/adaptive-whistling-tower.md. Rules: commit locally, push NOTHING, tag `pre-session4` first,
scratch HOME for tests, never launch Session Sync. A step is ticked only when its verification passes;
two failures = BLOCKED with reason. When done: write MORNING4.md, then CronDelete the job.

- [x] 0 safety tag `pre-session4` on steezy_studio, beat_thief, session_sync; record baseline test counts
- [x] 1 registry `install` info + `studio/share.py` command generation (+ tests)
- [ ] 2 `install.sh` (+ scratch-HOME test with local clones, idempotent, private-clone failure tolerated)
- [ ] 3 `studio/invite.py` (+ tests, dry-run only)
- [ ] 4 Share with friends panel in gui.py + index.html (+ API tests, Chrome render checked)
- [ ] 5 engine/setup.ps1
- [ ] 6 install.ps1
- [ ] 7 Windows portability of studio/ (mock sys.platform tests)
- [ ] 8 Beat Thief + Session Sync Windows guards (macOS baselines identical)
- [ ] 9 .github/workflows/windows.yml (YAML-validated)
- [ ] 10 Windows rows enabled in Share panel
- [ ] 11 memory update, session_sync README "225 passing" fix, MORNING4.md, CronDelete

## Log
- tags pre-session4 set; Studio baseline 33 tests (system python3)
- step 1 done: share.py, private flag; 38 tests
