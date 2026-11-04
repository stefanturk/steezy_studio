# Install Steezy Studio (and optionally some of its tools) on Windows:
#
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/stefanturk/steezy_studio/main/install.ps1)))
#   & ([scriptblock]::Create((irm .../install.ps1))) beat_thief session_sync
#
# No tool names = the Studio only. `all` installs every tool that has a Windows
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

function Clone-Url($url) {
    if ($env:STEEZY_REPO_BASE) { return (Join-Path $env:STEEZY_REPO_BASE ([IO.Path]::GetFileNameWithoutExtension($url))) }
    return $url
}

Say 'Steezy Studio'

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Note 'Windows needs Git first. Install it from https://git-scm.com/download/win,'
    Note 'then run this same line again.'
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
    & (Join-Path $Dest 'engine\setup.ps1')
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
    $lnk.Save()
}

# The Studio window itself (pythonw = no console flash).
if (Test-Path $Py) {
    Say 'Setting up the Studio window'
    & $Py -m pip install --quiet --prefer-binary --upgrade -r (Join-Path $Dest 'requirements.txt')
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
        git clone --depth 1 (Clone-Url $t.repo) $dir 2>$null
        if (($LASTEXITCODE -ne 0) -and $t.private -and -not $env:STEEZY_REPO_BASE) {
            if (Get-Command gh -ErrorAction SilentlyContinue) {
                Note "$($t.name) is private. Sign in to GitHub (the account Stefan invited):"
                gh auth status 2>$null
                if ($LASTEXITCODE -ne 0) { gh auth login --web --git-protocol https }
                gh auth setup-git 2>$null
                git clone --depth 1 $t.repo $dir 2>$null
            }
        }
        if (-not (Test-Path (Join-Path $dir '.git'))) {
            if ($t.private) { Note "Can't reach $($t.name) - it's private. Ask Stefan to invite your GitHub account, then run this again." }
            else { Note "Couldn't download $($t.name). Check your internet and run this again." }
            $Failed += $id; continue
        }
    }
    $req = Join-Path $dir 'requirements.txt'
    if ((Test-Path $Py) -and (Test-Path $req)) {
        & $Py -m pip install --quiet --prefer-binary -r $req
        if ($LASTEXITCODE -ne 0) { Note "Some packages for $id didn't install; press Update all in the Studio to retry."; $Failed += $id }
    }
    if ($t.windows_run) {
        $pyw = Join-Path $Engine 'python\pythonw.exe'
        New-Shortcut $t.name $pyw (($t.windows_run) -join ' ') $dir
        Note "Start menu: $($t.name)"
    }
}

Say 'Done'
Note 'Open it from the Start menu: Steezy Studio.'
if ($Failed.Count -gt 0) { Note ("Not installed: " + ($Failed -join ' ')) }
