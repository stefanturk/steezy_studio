# Shared pieces of every Steezy app's make_app.sh. Source it:
#
#   . "${STEEZY_BUILD:-$REPO/../steezy_studio/build}/lib.sh" 2>/dev/null || true
#
# Steezy Studio sets STEEZY_BUILD when it builds a tool; by hand, the neighbouring steezy_studio
# folder is used. If neither exists the functions below simply aren't defined, and a build that
# calls them guards with `declare -F` and carries on without (an icon is nice, never essential).
#
# Keep this free of anything app-specific: the one place to fix "where do apps go", "how does the
# icon get made" and "how are old copies swept" for all of them.

_STEEZY_BUILD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Where the app goes: an explicit folder wins; else /Applications when this user can write there
# (an admin account can), else ~/Applications.
steezy_dest() {
    if [ -n "${1:-}" ]; then printf '%s\n' "$1"
    elif [ -w /Applications ]; then printf '%s\n' "/Applications"
    else printf '%s\n' "$HOME/Applications"; fi
}

# Earlier builds went into ~/Applications. When building into /Applications, move to the new copy: its
# Dock pin is repointed, then the old one removed (a second copy goes stale in the Dock).
# Builds anywhere else delete nothing.
steezy_sweep_old_copy() {   # <dest> <App Name>
    if [ "$1" = "/Applications" ] && [ -e "$HOME/Applications/$2.app" ]; then
        echo "Moving ~/Applications/$2.app to $1/$2.app (its Dock pin comes with it)." >&2
        # Point the Dock pin at the new copy first: a pin to a deleted app turns into a question mark.
        [ -d "$1/$2.app" ] && /usr/bin/python3 "$_STEEZY_BUILD_DIR/dock_repin.py" "$HOME/Applications/$2.app" "$1/$2.app" || true
        rm -rf "$HOME/Applications/$2.app"
    fi
}

# Put a finished app in its place without a gap (see appswap.py). Build into a hidden folder
# beside the destination, then:   steezy_install_app "$STAGED" "$FINAL"
steezy_install_app() {      # <staged.app> <final.app>
    /usr/bin/python3 "$_STEEZY_BUILD_DIR/appswap.py" "$1" "$2"
}

# An SVG to a Mac .icns with its transparency kept (Quick Look would flatten it onto white).
#   steezy_icns <logo.svg> <out.icns> <python>     returns non-zero (and says why) if it can't.
steezy_icns() {
    local svg="$1" out="$2" py="$3" work size
    work="$(mktemp -d)"; mkdir -p "$work/icon.iconset"
    if "$py" "$_STEEZY_BUILD_DIR/render_logo.py" "$work/master.png" 1024 "$svg" 2>/dev/null; then
        for size in 16 32 128 256 512; do
            sips -z $size $size "$work/master.png" --out "$work/icon.iconset/icon_${size}x${size}.png" >/dev/null 2>&1
            sips -z $((size * 2)) $((size * 2)) "$work/master.png" --out "$work/icon.iconset/icon_${size}x${size}@2x.png" >/dev/null 2>&1
        done
        if iconutil -c icns "$work/icon.iconset" -o "$out" 2>/dev/null; then rm -rf "$work"; return 0; fi
    fi
    rm -rf "$work"
    echo "Warning: could not render the icon; the app will use a generic one." >&2
    return 1
}
