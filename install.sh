#!/bin/bash
# Install Steezy Studio (and optionally some of its tools) on a Mac that has
# never seen it:
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/stefanturk/steezy_studio/main/install.sh)"
#   bash -c "$(curl -fsSL .../install.sh)" _ beat_thief session_sync
#
# No tool names = the Studio only; then pick tools inside the app, or name them
# here. `all` installs every tool. Run it again any time to update.
#
# Tools that are private (Ableton Loader, Movie Maker) need a GitHub account
# that Stefan has invited; if you can't reach one it is skipped and the rest
# still install.
#
# Test hooks: STEEZY_INSTALL_DEST (Studio folder), STEEZY_TOOLS_DIR (where tools
# go), STEEZY_ENGINE_DIR, STEEZY_REPO_BASE (clone from here instead of GitHub),
# STEEZY_SKIP_ENGINE=1, STEEZY_SKIP_BUILD=1, STEEZY_NO_GH=1.

set -uo pipefail

STUDIO_URL="https://github.com/stefanturk/steezy_studio.git"
DEST="${STEEZY_INSTALL_DEST:-$HOME/steezy_studio}"
TOOLS="${STEEZY_TOOLS_DIR:-$HOME/steezy_tools}"
ENGINE="${STEEZY_ENGINE_DIR:-$HOME/Library/Application Support/Steezy Studio/engine}"
STATE="$(dirname "$ENGINE")"
GH_VERSION="2.103.3"
# Apps go in the main /Applications folder when this account can write there
# (any admin account can), else the one in the home folder.
if [ -n "${STEEZY_APPS_DIR:-}" ]; then APPS="$STEEZY_APPS_DIR"
elif [ -w /Applications ]; then APPS="/Applications"
else APPS="$HOME/Applications"; fi

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
note() { printf '   %s\n' "$*"; }

if [ "${1:-}" = "--list" ]; then
    echo "beat_thief ableton_loader session_sync movie_maker (or: all)"
    exit 0
fi

WANT="$*"
say "Steezy Studio"

if ! git --version >/dev/null 2>&1; then
    note "macOS needs its command line tools first (this is where git comes"
    note "from). A window is opening now - click Install, wait for it to"
    note "finish, then run this same line again."
    xcode-select --install 2>/dev/null || true
    exit 1
fi

clone_url() {  # $1 = real URL; tests point STEEZY_REPO_BASE at a folder of local repos
    if [ -n "${STEEZY_REPO_BASE:-}" ]; then
        echo "$STEEZY_REPO_BASE/$(basename "$1" .git)"
    else
        echo "$1"
    fi
}

# --- the Studio itself
if [ -d "$DEST/.git" ]; then
    say "Studio already here - updating"
    git -C "$DEST" pull --ff-only || note "Couldn't update the Studio (local changes?). Carrying on."
elif [ -e "$DEST" ]; then
    note "There's already something at $DEST that isn't a Steezy Studio clone."
    note "Move it out of the way and run this again."
    exit 1
else
    say "Getting Steezy Studio"
    git clone --depth 1 "$(clone_url "$STUDIO_URL")" "$DEST" || { note "Couldn't download Steezy Studio."; exit 1; }
fi

if [ "${STEEZY_SKIP_ENGINE:-}" != 1 ]; then
    "$DEST/engine/setup.sh" || { note "The engine setup failed."; exit 1; }
fi

# Tell the app where tools live (it reads this when no env var is set).
mkdir -p "$STATE" "$TOOLS"
printf '%s\n' "$TOOLS" > "$STATE/tools_dir"

if [ "${STEEZY_SKIP_BUILD:-}" != 1 ]; then
    say "Building Steezy Studio.app"
    (cd "$DEST" && ./make_app.sh "$APPS") || note "The app build failed; run ./make_app.sh in $DEST to see why."
fi

PYBIN="$ENGINE/python/bin/python3"
[ -x "$PYBIN" ] || PYBIN=python3

# registry lines: id|folder|repo|private|build...  (printed by the Studio's own loader)
registry_lines() {
    STEEZY_REGISTRY="$DEST/registry.json" "$PYBIN" - <<'PY'
import json, os
for t in json.load(open(os.environ["STEEZY_REGISTRY"]))["tools"]:
    print("|".join([t["id"], t["folder"], t["repo"], "1" if t.get("private") else "0", " ".join(t["build"])]))
PY
}

ensure_gh() {
    command -v gh >/dev/null 2>&1 && return 0
    [ -x "$ENGINE/bin/gh" ] && { PATH="$ENGINE/bin:$PATH"; return 0; }
    [ "${STEEZY_NO_GH:-}" = 1 ] && return 1
    local arch="amd64" tmp base file sum
    [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = "1" ] && arch="arm64"
    base="https://github.com/cli/cli/releases/download/v$GH_VERSION"
    file="gh_${GH_VERSION}_macOS_${arch}.zip"
    tmp="$(mktemp -d)"
    note "Getting GitHub's sign-in helper (gh)..."
    curl -fsSL -o "$tmp/$file" "$base/$file" && curl -fsSL -o "$tmp/sums" "$base/gh_${GH_VERSION}_checksums.txt" || { rm -rf "$tmp"; return 1; }
    sum="$(grep " $file\$" "$tmp/sums" | cut -d' ' -f1)"
    if [ -z "$sum" ] || [ "$(shasum -a 256 "$tmp/$file" | cut -d' ' -f1)" != "$sum" ]; then
        note "The gh download didn't check out; not using it."; rm -rf "$tmp"; return 1
    fi
    unzip -q "$tmp/$file" -d "$tmp" && mkdir -p "$ENGINE/bin" && cp "$tmp/gh_${GH_VERSION}_macOS_${arch}/bin/gh" "$ENGINE/bin/gh"
    rm -rf "$tmp"
    PATH="$ENGINE/bin:$PATH"
    command -v gh >/dev/null 2>&1
}

install_tool() {  # id folder repo private build
    local id="$1" folder="$2" repo="$3" priv="$4" build="$5"
    say "$id"
    local dir="$TOOLS/$folder"
    if [ -d "$dir/.git" ]; then
        git -C "$dir" pull --ff-only || note "Couldn't update $id (local changes?). Carrying on."
    else
        if ! GIT_TERMINAL_PROMPT=0 git clone --depth 1 "$(clone_url "$repo")" "$dir" 2>/dev/null; then
            if [ "$priv" = 1 ] && [ -z "${STEEZY_REPO_BASE:-}" ] && ensure_gh; then
                note "$id is private. Sign in to GitHub (the account Stefan invited):"
                gh auth status >/dev/null 2>&1 || gh auth login --web --git-protocol https || true
                gh auth setup-git >/dev/null 2>&1 || true
                GIT_TERMINAL_PROMPT=0 git clone --depth 1 "$repo" "$dir" 2>/dev/null
            fi
        fi
        if [ ! -d "$dir/.git" ]; then
            if [ "$priv" = 1 ]; then
                note "Can't reach $id - it's private. Ask Stefan to invite your GitHub account, then run this again."
            else
                note "Couldn't download $id. Check your internet and run this again."
            fi
            FAILED="$FAILED $id"
            return 1
        fi
    fi
    if [ "${STEEZY_SKIP_BUILD:-}" != 1 ]; then
        (cd "$dir" && $build "$APPS") || { note "Built $id with errors; open Steezy Studio and press Update all to retry."; FAILED="$FAILED $id"; }
    fi
}

FAILED=""
if [ -n "$WANT" ]; then
    LINES="$(registry_lines)"
    [ "$WANT" = all ] && WANT="$(echo "$LINES" | cut -d'|' -f1 | tr '\n' ' ')"
    for id in $WANT; do
        line="$(echo "$LINES" | grep "^$id|" | head -1)"
        if [ -z "$line" ]; then note "Unknown tool '$id' (try --list)."; FAILED="$FAILED $id"; continue; fi
        IFS='|' read -r tid folder repo priv build <<EOF2
$line
EOF2
        install_tool "$tid" "$folder" "$repo" "$priv" "$build"
    done
fi

say "Done"
note "Open it: $APPS/Steezy Studio.app (drag it to the Dock)."
[ -n "$FAILED" ] && note "Not installed:$FAILED"
exit 0
