# Steezy Studio engine for Windows: one private Python 3.12 and one ffmpeg/ffprobe
# that every tool can run on. Same idea and same pinned-download rule as setup.sh:
# each file is checked against a known SHA-256 and refused if it differs.
#
#   engine\setup.ps1            install (or verify) the engine
#   engine\setup.ps1 -Path      print the engine folder and exit
#
# Safe to run again. No admin rights needed. Windows 10 1803+ (tar.exe, Expand-Archive).
param([switch]$Path)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is far faster without the bar

$Engine = if ($env:STEEZY_ENGINE_DIR) { $env:STEEZY_ENGINE_DIR } else { Join-Path $env:LOCALAPPDATA 'Steezy Studio\engine' }
$Py  = Join-Path $Engine 'python\python.exe'
$Bin = Join-Path $Engine 'bin'

if ($Path) { Write-Output $Engine; return }

function Say($m)  { Write-Host ""; Write-Host $m -ForegroundColor White }
function Note($m) { Write-Host "   $m" }

# Downloads $Url to $Dest and refuses it unless it is the exact file expected.
function Fetch($Url, $Sha, $Dest) {
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    $got = (Get-FileHash -Algorithm SHA256 -Path $Dest).Hash.ToLower()
    if ($got -ne $Sha) {
        Remove-Item -Force $Dest -ErrorAction SilentlyContinue
        throw "That download wasn't the file it should have been."
    }
}

function Test-Python {
    if (-not (Test-Path $Py)) { return $false }
    try { & $Py -c 'import sys; assert sys.version_info >= (3, 12)' 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

Say 'Steezy Studio engine'
$Work = Join-Path ([IO.Path]::GetTempPath()) ("steezy-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $Engine, $Bin, $Work | Out-Null

try {
    Say '1. Python'
    if (Test-Python) {
        Note ((& $Py --version) + ' - already here.')
    } else {
        $PyFile = 'cpython-3.12.15+20261003-x86_64-pc-windows-msvc-install_only.tar.gz'
        $PyUrl  = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261003/' + $PyFile.Replace('+', '%2B')
        $PySha  = '4b6f0beebbb695a0f3ea237b8c3eaa5bd424f47a7bc25b2fbe3a43390c770f08'
        Note 'Downloading Python 3.12 (about 40MB)...'
        $tgz = Join-Path $Work 'python.tar.gz'
        Fetch $PyUrl $PySha $tgz
        if (Test-Path (Join-Path $Engine 'python')) { Remove-Item -Recurse -Force (Join-Path $Engine 'python') }
        tar -xzf $tgz -C $Engine
        if ($LASTEXITCODE -ne 0) { throw 'Could not unpack Python.' }
        if (-not (Test-Python)) { throw "Python won't start on this PC." }
        Note ((& $Py --version) + ' - ok.')
    }

    Say '2. ffmpeg'
    $haveFf = (Test-Path (Join-Path $Bin 'ffmpeg.exe')) -and (Test-Path (Join-Path $Bin 'ffprobe.exe'))
    if ($haveFf) {
        Note 'ffmpeg and ffprobe - already here.'
    } else {
        $Tag = '2026-11-02-git-b034eb5e7e'
        $FfUrl = "https://github.com/GyanD/codexffmpeg/releases/download/$Tag/ffmpeg-$Tag-essentials_build.zip"
        $FfSha = 'ff646d864bd9b0fa6e0be55acaa2e1f0ad7210c309325f13853c89bf7afd79e7'
        Note 'Downloading ffmpeg (about 115MB)...'
        $zip = Join-Path $Work 'ffmpeg.zip'
        Fetch $FfUrl $FfSha $zip
        Expand-Archive -Path $zip -DestinationPath (Join-Path $Work 'ff') -Force
        foreach ($t in 'ffmpeg', 'ffprobe') {
            Copy-Item -Force (Join-Path $Work "ff\ffmpeg-$Tag-essentials_build\bin\$t.exe") (Join-Path $Bin "$t.exe")
            & (Join-Path $Bin "$t.exe") -version *> $null
            if ($LASTEXITCODE -ne 0) { throw "$t won't start on this PC." }
            Note "$t - ok."
        }
    }
    Say "Engine ready: $Engine"
}
finally {
    Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue
}
