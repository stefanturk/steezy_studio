# Steezy Studio

Launcher and shared engine for the family: movie_maker, Ableton Loader, Beat Thief, Session Sync.
Each tool keeps its own name, folder and repo.

## Install

**Windows** — open PowerShell (Start › type "PowerShell") and paste:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/stefanturk/steezy_studio/main/install.ps1))) session_sync
```

**Mac** — open Terminal and paste:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/stefanturk/steezy_studio/main/install.sh)" _ session_sync
```

Leave out `session_sync` to install just the Studio, or name other tools (`beat_thief`, or `all`).
Run the same line again any time to update.

Nothing needs changing on the computer first:
- Windows without Git gets it from winget, or a private copy (MinGit, checked by SHA-256)
  kept in the Studio's engine folder.
- Windows blocking scripts ("running scripts is disabled on this system") is fine: the
  installer runs its own steps with `-ExecutionPolicy Bypass` for that run only.
- No PATH changes are needed; ignore any old advice to add the engine's `Scripts` folder.

