#!/bin/bash
# Steezy Studio engine: one private Python 3.12 and one ffmpeg/ffprobe that
# every tool in the family can run on. Same pinned downloads as Beat Thief's
# setup.sh, checked against known SHA-256s, no Homebrew, no password.
#
#   engine/setup.sh            install (or verify) the engine
#   engine/setup.sh --path     print the engine folder and exit
#
# Safe to run again: each step checks whether it is already done.
# STEEZY_ENGINE_SOURCE_ONLY=1 loads the functions without installing (tests).

set -euo pipefail

ENGINE="${STEEZY_ENGINE_DIR:-$HOME/Library/Application Support/Steezy Studio/engine}"
PY="$ENGINE/python/bin/python3"
BIN="$ENGINE/bin"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
note() { printf '   %s\n' "$*"; }

# Downloads url to path and refuses it unless it is the exact file expected.
fetch() {
    local url="$1" sha="$2" path="$3"
    curl -fL --retry 3 --progress-bar -o "$path" "$url"
    if [ "$(shasum -a 256 "$path" | cut -d' ' -f1)" != "$sha" ]; then
        rm -f "$path"
        note "That download wasn't the file it should have been."
        return 1
    fi
}

if [ "${STEEZY_ENGINE_SOURCE_ONLY:-}" = 1 ]; then
    return 0 2>/dev/null || exit 0
fi

if [ "${1:-}" = "--path" ]; then
    echo "$ENGINE"
    exit 0
fi

say "Steezy Studio engine"

# Asked of the hardware, not `uname -m`: Terminal under Rosetta lies.
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = "1" ]; then
    MACHINE=arm64
else
    MACHINE=x86_64
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$ENGINE" "$BIN"

say "1. Python"
PBS="https://github.com/astral-sh/python-build-standalone/releases/download/20261003"
if [ "$MACHINE" = arm64 ]; then
    PY_FILE="cpython-3.12.15+20261003-aarch64-apple-darwin-install_only.tar.gz"
    PY_SHA="316a463172740e71d8dca1f2730784e325f3f720941137b5d674d5801a632213"
else
    PY_FILE="cpython-3.12.15+20261003-x86_64-apple-darwin-install_only.tar.gz"
    PY_SHA="a8fd7a91852f19b6d959793ef41fad048631ccb2a334a9ecdf573255298f7978"
fi
if "$PY" -c 'import sys; assert sys.version_info >= (3, 12)' >/dev/null 2>&1; then
    note "$("$PY" --version) - already here."
else
    note "Downloading Python 3.12 (25MB)..."
    fetch "$PBS/${PY_FILE//+/%2B}" "$PY_SHA" "$WORK/python.tar.gz" || exit 1
    rm -rf "$ENGINE/python"
    tar -xzf "$WORK/python.tar.gz" -C "$ENGINE"
    note "$("$PY" --version) - ok."
fi

say "2. ffmpeg"
if [ "$MACHINE" = arm64 ]; then
    FF_URL="https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2"
    FFMPEG_SHA="c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924"
    FFPROBE_SHA="fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6"
    ff_zip() { echo "$FF_URL/$1.zip"; }
else
    FFMPEG_SHA="4acc0be580f9b2788029eb7bd4d645ff87968911b0a62aeeb3940d42d54558d5"
    FFPROBE_SHA="24a9c968cd4da72d99c7245e914b921815835eb6dff01d99868031aebaf1d439"
    ff_zip() { echo "https://evermeet.cx/ffmpeg/$1-9.0.2.zip"; }
fi
for tool in ffmpeg ffprobe; do
    if "$BIN/$tool" -version >/dev/null 2>&1; then
        note "$tool - already here."
        continue
    fi
    note "Downloading $tool..."
    sha_var="$(echo "$tool" | tr a-z A-Z)_SHA"
    fetch "$(ff_zip "$tool")" "${!sha_var}" "$WORK/$tool.zip" || exit 1
    unzip -oq "$WORK/$tool.zip" -d "$WORK/$tool"
    mv -f "$WORK/$tool/$tool" "$BIN/$tool"
    chmod +x "$BIN/$tool"
    "$BIN/$tool" -version >/dev/null 2>&1 || codesign --force -s - "$BIN/$tool" 2>/dev/null || true
    if ! "$BIN/$tool" -version >/dev/null 2>&1; then
        note "$tool won't start on this Mac."
        exit 1
    fi
    note "$tool - ok."
done

say "Engine ready: $ENGINE"
