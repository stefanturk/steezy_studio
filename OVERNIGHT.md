# Overnight checklist (plan: ~/.claude/plans/adaptive-whistling-tower.md)

Status: [ ] todo, [x] done, [!] BLOCKED

- [x] 1. Init repo, README, OVERNIGHT.md, tests folder
- [x] 2. engine/setup.sh (pinned python 3.12 + ffmpeg)
- [x] 3. Local self-signed identity
- [x] 4. Beat Thief onto the engine
- [x] 5. registry.json + loader
- [x] 6. Launcher GUI
- [ ] 7. Update all
- [ ] 8. Steezy Studio.app
- [ ] 9. Other three tools on the engine
- [ ] 10. Dry-run Update all on real folders
- [ ] 11. Push + MORNING.md + memory

## Log
- 2026-11-02 22:37:52 step 2 verified: scratch install gives python 3.12.15 + ffmpeg 9.0.2; bad SHA rejected; rerun is a no-op
- 2026-11-02 22:38:43 step 3 verified: identity 'Steezy Studio Signing' created; two differing builds share designated requirement (cert hash 14a99bcf...); ad-hoc differs
- 2026-11-02 22:42:30 step 4 verified: beat_thief setup.sh adopts engine (0 python/ffmpeg downloads in scratch HOME); tests 207/1 existing failure same as baseline; beat_fidelity identical; pre-studio tag on beat_thief; commit local only
- 2026-11-02 22:51:00 step 5 verified: 9 registry tests pass (missing folder, no git, no access, crashing access check, malformed entries, unreadable registry); real folders all READY
- 2026-11-02 23:14:58 step 6 verified: 15 tests pass (registry + gui Api incl. dirty/behind via real git repos); page rendered in headless Chrome with real list_tools data + fake no_access/broken tiles, screenshot reviewed. Deviation: toolkit is pywebview (family standard), not Qt, so no QT offscreen; real pywebview window is first opened in step 8. Fixed registry app name SessionSync.app
