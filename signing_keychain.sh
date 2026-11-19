# Sourced by make_signing_identity.sh and make_app.sh.
#
# Steezy Studio's own local signing identity. Same idea as the Ableton Loader's:
# a self-signed key in a keychain of its own, so rebuilds keep one code
# identity and macOS asks for Desktop access once.
#
# The keychain's password is random and made on this Mac (signing_password, beside the engine, readable
# only by you). It used to be a fixed word written in this public repo, and the keychain never locked,
# so any program running as you could have signed itself as Steezy Studio and inherited the access you
# gave it. Now the keychain is opened for a build and locked again at its end (and locks by itself after
# 10 minutes, or when the Mac sleeps, if a build dies midway). An old keychain still on the public word
# is moved to a random password the next time it is opened. Nothing here ever asks you anything.

SIGNING_NAME="${STEEZY_SIGNING_NAME:-Steezy Studio Signing}"
SIGNING_KEYCHAIN="${STEEZY_SIGNING_KEYCHAIN:-$HOME/Library/Keychains/steezy-studio-signing.keychain-db}"
SIGNING_STATE="$(dirname "${STEEZY_ENGINE_DIR:-$HOME/Library/Application Support/Steezy Studio/engine}")"
SIGNING_PASSWORD_FILE="$SIGNING_STATE/signing_password"
SIGNING_LEGACY_PASSWORD="steezy-studio"     # what keychains made before 2026-11-19 used

# The password for this Mac's signing keychain (the old public one if none was made yet).
signing_password() {
    if [ -s "$SIGNING_PASSWORD_FILE" ]; then head -n 1 "$SIGNING_PASSWORD_FILE"
    else printf '%s\n' "$SIGNING_LEGACY_PASSWORD"; fi
}

_signing_new_password() { /usr/bin/openssl rand -hex 16; }

_signing_write_password() {     # <file> <password>: readable by this user only, written whole
    ( umask 077; mkdir -p "$(dirname "$1")" && printf '%s\n' "$2" > "$1.tmp" && mv -f "$1.tmp" "$1" )
}

# Unlock with whichever known password works, and print it: the saved one, one half-saved by an
# interrupted move (signing_password.new), then the old public word. Fails if none does.
_signing_unlock_any() {
    local pw
    for pw in "$(signing_password)" "$(head -n 1 "$SIGNING_PASSWORD_FILE.new" 2>/dev/null)" "$SIGNING_LEGACY_PASSWORD"; do
        [ -n "$pw" ] || continue
        if security unlock-keychain -p "$pw" "$SIGNING_KEYCHAIN" 2>/dev/null; then
            printf '%s\n' "$pw"; return 0
        fi
    done
    return 1
}

# A brand-new, empty signing keychain with a random password (make_signing_identity.sh fills it).
create_signing_keychain() {
    local pw; pw="$(_signing_new_password)"
    [ -n "$pw" ] || { echo "Couldn't make a password for the signing keychain." >&2; return 1; }
    security delete-keychain "$SIGNING_KEYCHAIN" 2>/dev/null || rm -f "$SIGNING_KEYCHAIN"
    _signing_write_password "$SIGNING_PASSWORD_FILE" "$pw" || return 1
    rm -f "$SIGNING_PASSWORD_FILE.new"
    security create-keychain -p "$pw" "$SIGNING_KEYCHAIN" || return 1
    security set-keychain-settings -l -t 600 "$SIGNING_KEYCHAIN"
    security unlock-keychain -p "$pw" "$SIGNING_KEYCHAIN"
}

# Unlock for a build, moving an old keychain off the public password, and make sure codesign can see it.
open_signing_keychain() {
    local pw new
    pw="$(_signing_unlock_any)" || { echo "Couldn't unlock $SIGNING_KEYCHAIN." >&2; return 1; }
    if [ "$pw" = "$SIGNING_LEGACY_PASSWORD" ]; then
        new="$(_signing_new_password)"
        # The new password is saved to .new first: if the change happens but we're cut off before
        # the rename, the next open still finds it.
        if [ -n "$new" ] && _signing_write_password "$SIGNING_PASSWORD_FILE.new" "$new" &&
           security set-keychain-password -o "$pw" -p "$new" "$SIGNING_KEYCHAIN" </dev/null 2>/dev/null; then
            mv -f "$SIGNING_PASSWORD_FILE.new" "$SIGNING_PASSWORD_FILE"
            security unlock-keychain -p "$new" "$SIGNING_KEYCHAIN" 2>/dev/null || true
        else
            rm -f "$SIGNING_PASSWORD_FILE.new"       # stays on the old word this time; nothing breaks
        fi
    elif [ "$pw" != "$(signing_password)" ]; then
        mv -f "$SIGNING_PASSWORD_FILE.new" "$SIGNING_PASSWORD_FILE"     # finish an interrupted move
    fi
    # Locks itself after 10 minutes and on sleep, so a build that dies before close_ never leaves it open.
    security set-keychain-settings -l -t 600 "$SIGNING_KEYCHAIN" 2>/dev/null || true
    _signing_add_to_search_list
}

# Lock it again once the build has signed (make_app.sh does this on any exit).
close_signing_keychain() {
    security lock-keychain "$SIGNING_KEYCHAIN" 2>/dev/null || true
}

# codesign only finds identities in keychains on the user's search list. Each path is kept whole
# (a path with a space used to be split apart, which could drop the login keychain from the list).
_signing_real() {      # the path with symlinks resolved (macOS lists /var/... as /private/var/...)
    local d; d="$(cd "$(dirname "$1")" 2>/dev/null && pwd -P)" && printf '%s/%s\n' "$d" "$(basename "$1")" || printf '%s\n' "$1"
}

_signing_add_to_search_list() {
    local line paths=() mine; mine="$(_signing_real "$SIGNING_KEYCHAIN")"
    while IFS= read -r line; do
        line="${line#"${line%%[![:space:]]*}"}"; line="${line%\"}"; line="${line#\"}"
        [ -n "$line" ] || continue
        [ "$(_signing_real "$line")" = "$mine" ] && return 0
        paths+=("$line")
    done < <(security list-keychains -d user)
    security list-keychains -d user -s ${paths[@]+"${paths[@]}"} "$SIGNING_KEYCHAIN"
}

signing_identity() {
    security find-identity -p codesigning "$SIGNING_KEYCHAIN" |
        awk -v name="\"$SIGNING_NAME\"" '$0 ~ name {print $2; exit}'
}
