# Install Steezy Studio (and optionally some of its tools) on Windows:
#
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/stefanturk/steezy_studio/main/install.ps1)))
#   & ([scriptblock]::Create((irm .../install.ps1))) beat_thief session_sync
#
# No tool names = the Studio only; then press Install on a tool inside the Studio. `all` installs every tool that has a Windows
# version. Run it again any time to update. Private tools need a GitHub account
# Stefan has invited; if one can't be reached it is skipped and the rest install.
#
# Test hooks: STEEZY_INSTALL_DEST, STEEZY_TOOLS_DIR, STEEZY_ENGINE_DIR,
# STEEZY_REPO_BASE (clone from here), STEEZY_SKIP_ENGINE=1, STEEZY_SKIP_SHORTCUTS=1.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Tools)

$ErrorActionPreference = 'Stop'
$StudioUrl = 'https://github.com/stefanturk/steezy_studio.git'
$Dest   = if ($env:STEEZY_INSTALL_DEST) { $env:STEEZY_INSTALL_DEST } else { Join-Path $env:USERPROFILE 'steezy_studio' }
$ToolsDir = if ($env:STEEZY_TOOLS_DIR) { $env:STEEZY_TOOLS_DIR } else { Join-Path $env:USERPROFILE 'steezy_tools' }
$Engine = if ($env:STEEZY_ENGINE_DIR) { $env:STEEZY_ENGINE_DIR } else { Join-Path $env:LOCALAPPDATA 'Steezy Studio\engine' }
$State  = Split-Path $Engine -Parent
$Failed = @()

function Say($m)  { Write-Host ""; Write-Host $m -ForegroundColor White }
function Note($m) { Write-Host "   $m" }

# Run a native command with its stderr hidden. Windows PowerShell 5.1 turns
# redirected stderr into a terminating error under 'Stop', and git writes its
# progress to stderr, so a plain `git clone ... 2>$null` would end the script.
function Quiet([scriptblock]$Cmd) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Cmd 2>&1 | Out-Null } finally { $ErrorActionPreference = $old }
}

function Clone-Url($url) {
    if ($env:STEEZY_REPO_BASE) { return (Join-Path $env:STEEZY_REPO_BASE ([IO.Path]::GetFileNameWithoutExtension($url))) }
    return $url
}

Say 'Steezy Studio'

# Git: the one on PATH; else a private MinGit already in the engine folder; else
# Windows' own installer (winget); else a pinned MinGit download (checked by
# SHA-256) into the engine folder. Nothing asks for admin rights.
$MinGitDir = Join-Path $Engine 'mingit'
function Use-PrivateGit {
    $cmd = Join-Path $MinGitDir 'cmd'
    if (Test-Path (Join-Path $cmd 'git.exe')) { $env:PATH = "$cmd;$env:PATH"; return $true }
    return $false
}
function Refresh-Path {
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:PATH = "$m;$u;$env:PATH"
}
if ($env:STEEZY_NO_SYSTEM_GIT -eq '1') {
    # CI: behave like a PC without Git
    $env:PATH = (($env:PATH -split ';') | Where-Object { $_ -and -not (Test-Path (Join-Path $_ 'git.exe')) }) -join ';'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { [void](Use-PrivateGit) }
if (-not (Get-Command git -ErrorAction SilentlyContinue) -and $env:STEEZY_NO_SYSTEM_GIT -ne '1' -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Say 'Installing Git (Windows needs it to fetch the tools)'
    Quiet { winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements }
    Refresh-Path
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Say 'Getting a private copy of Git'
    $GitVer = '2.56.0.windows.4'
    $GitZip = 'MinGit-2.56.0.4-64-bit.zip'
    $GitSha = 'e3bf78351fe777fba47ddee5950082f8a98bb0f02604fdc7ba3ee2cb68ffa877'
    $zip = Join-Path ([IO.Path]::GetTempPath()) $GitZip
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri "https://github.com/git-for-windows/git/releases/download/v$GitVer/$GitZip" -OutFile $zip -UseBasicParsing
        if ((Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower() -ne $GitSha) { throw 'wrong file' }
        if (Test-Path $MinGitDir) { Remove-Item -Recurse -Force $MinGitDir }
        Expand-Archive -Path $zip -DestinationPath $MinGitDir -Force
    } catch {
        Note "Couldn't get Git ($_)."
    } finally {
        Remove-Item -Force $zip -ErrorAction SilentlyContinue
    }
    [void](Use-PrivateGit)
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Note 'Windows needs Git first, and it could not be installed automatically.'
    Note 'Install it from https://git-scm.com/download/win, then run this same line again.'
    return
}

if (Test-Path (Join-Path $Dest '.git')) {
    Say 'Studio already here - updating'
    git -C $Dest pull --ff-only
    if ($LASTEXITCODE -ne 0) { Note "Couldn't update the Studio (local changes?). Carrying on." }
} elseif (Test-Path $Dest) {
    Note "There's already something at $Dest that isn't a Steezy Studio clone."
    Note 'Move it out of the way and run this again.'
    return
} else {
    Say 'Getting Steezy Studio'
    git clone --depth 1 (Clone-Url $StudioUrl) $Dest
    if ($LASTEXITCODE -ne 0) { Note "Couldn't download Steezy Studio."; return }
}

if ($env:STEEZY_SKIP_ENGINE -ne '1') {
    # Its own PowerShell with -ExecutionPolicy Bypass for this one run: Windows
    # blocks running .ps1 files by default ("running scripts is disabled on this
    # system"), and nothing on the PC needs changing for this.
    $shell = (Get-Process -Id $PID).Path
    & $shell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dest 'engine\setup.ps1')
    if ($LASTEXITCODE -ne 0) { Note "The engine didn't finish setting up; run this same line again."; return }
}
$Py = Join-Path $Engine 'python\python.exe'

New-Item -ItemType Directory -Force -Path $State, $ToolsDir | Out-Null
Set-Content -Path (Join-Path $State 'tools_dir') -Value $ToolsDir -Encoding ASCII

function New-Shortcut($Name, $Target, $Arguments, $WorkDir) {
    if ($env:STEEZY_SKIP_SHORTCUTS -eq '1') { return }
    $dir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
    $sh = New-Object -ComObject WScript.Shell
    $lnk = $sh.CreateShortcut((Join-Path $dir "$Name.lnk"))
    $lnk.TargetPath = $Target
    $lnk.Arguments = $Arguments
    $lnk.WorkingDirectory = $WorkDir
    # The tool's own icon, not Python's, when its repo has one.
    $ico = Join-Path $WorkDir 'icon.ico'
    if (Test-Path $ico) { $lnk.IconLocation = "$ico,0" }
    $lnk.Save()
}

# The Studio window itself (pythonw = no console flash).
if (Test-Path $Py) {
    Say 'Setting up the Studio window'
    Copy-Item (Join-Path $Dest 'constraints.txt') (Join-Path $Engine 'constraints.txt') -Force -ErrorAction SilentlyContinue
    $cArg = if (Test-Path (Join-Path $Engine 'constraints.txt')) { @('-c', (Join-Path $Engine 'constraints.txt')) } else { @() }
    & $Py -m pip install --quiet --prefer-binary --upgrade --no-warn-script-location @cArg -r (Join-Path $Dest 'requirements.txt')
    $pyw = Join-Path $Engine 'python\pythonw.exe'
    New-Shortcut 'Steezy Studio' $pyw '-m studio.gui' $Dest
    Note 'Start menu: Steezy Studio'
}

$registry = (Get-Content (Join-Path $Dest 'registry.json') -Raw | ConvertFrom-Json).tools
$want = @($Tools | Where-Object { $_ })
if ($want -contains 'all') { $want = @($registry | Where-Object { $_.platforms -contains 'windows' } | ForEach-Object { $_.id }) }

foreach ($id in $want) {
    $t = $registry | Where-Object { $_.id -eq $id } | Select-Object -First 1
    if (-not $t) { Note "Unknown tool '$id'."; $Failed += $id; continue }
    Say $t.name
    if ($t.platforms -notcontains 'windows') {
        Note "$($t.name) doesn't have a Windows version yet."
        $Failed += $id; continue
    }
    $dir = Join-Path $ToolsDir $t.folder
    if (Test-Path (Join-Path $dir '.git')) {
        git -C $dir pull --ff-only
        if ($LASTEXITCODE -ne 0) { Note "Couldn't update $id (local changes?). Carrying on." }
    } else {
        Quiet { git clone --depth 1 (Clone-Url $t.repo) $dir }
        if (($LASTEXITCODE -ne 0) -and $t.private -and -not $env:STEEZY_REPO_BASE) {
            if (Get-Command gh -ErrorAction SilentlyContinue) {
                Note "$($t.name) is private. Sign in to GitHub (the account Stefan invited):"
                Quiet { gh auth status }
                if ($LASTEXITCODE -ne 0) { gh auth login --web --git-protocol https }
                Quiet { gh auth setup-git }
                Quiet { git clone --depth 1 $t.repo $dir }
            }
        }
        if (-not (Test-Path (Join-Path $dir '.git'))) {
            if ($t.private) { Note "Can't reach $($t.name) - it's private. Ask Stefan to invite your GitHub account, then run this again." }
            else { Note "Couldn't download $($t.name). Check your internet and run this again." }
            $Failed += $id; continue
        }
    }
    # Same rule as the Studio's Install button (updater.default_refresh): every file
    # in windows_requirements (default requirements.txt), then -e . if asked.
    if (Test-Path $Py) {
        $reqs = if ($t.windows_requirements) { @($t.windows_requirements) } else { @('requirements.txt') }
        $pipOk = $true
        foreach ($r in $reqs) {
            $req = Join-Path $dir $r
            if (-not (Test-Path $req)) { continue }
            if ($r -ne 'requirements.txt') { Note "Installing $r (this can be a big download)..." }
            & $Py -m pip install --quiet --prefer-binary --upgrade --no-warn-script-location @cArg -r $req
            if ($LASTEXITCODE -ne 0) { $pipOk = $false }
        }
        if ($t.windows_pip_editable) {
            & $Py -m pip install --quiet --prefer-binary --upgrade --no-warn-script-location @cArg -e $dir
            if ($LASTEXITCODE -ne 0) { $pipOk = $false }
        }
        if (-not $pipOk) { Note "Some packages for $id didn't install; run this line again to retry."; $Failed += $id }
    }
    if ($t.windows_run) {
        $pyw = Join-Path $Engine 'python\pythonw.exe'
        New-Shortcut $t.name $pyw (($t.windows_run) -join ' ') $dir
        Note "Start menu: $($t.name)"
    }
}

Say 'Done'
Note 'Open it from the Start menu: Steezy Studio.'
Note 'Press Install on any tool you want; Update all keeps them current.'
if ($Failed.Count -gt 0) { Note ("Not installed: " + ($Failed -join ' ')) }
