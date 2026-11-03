# Sourced by make_signing_identity.sh and make_app.sh.
#
# Steezy Studio's own local signing identity. Same idea as the Ableton Loader's:
# a self-signed key in a keychain of its own, so rebuilds keep one code
# identity and macOS asks for Desktop access once. The password is written here
# on purpose: the keychain holds one self-made key that signs local apps only.

SIGNING_NAME="${STEEZY_SIGNING_NAME:-Steezy Studio Signing}"
SIGNING_KEYCHAIN="${STEEZY_SIGNING_KEYCHAIN:-$HOME/Library/Keychains/steezy-studio-signing.keychain-db}"
SIGNING_PASSWORD="steezy-studio"

open_signing_keychain() {
    security unlock-keychain -p "$SIGNING_PASSWORD" "$SIGNING_KEYCHAIN"
    local base; base="$(basename "$SIGNING_KEYCHAIN" .keychain-db)"
    if ! security list-keychains -d user | grep -q "$base"; then
        # shellcheck disable=SC2046
        security list-keychains -d user -s $(security list-keychains -d user | tr -d '"') "$SIGNING_KEYCHAIN"
    fi
}

signing_identity() {
    security find-identity -p codesigning "$SIGNING_KEYCHAIN" |
        awk -v name="\"$SIGNING_NAME\"" '$0 ~ name {print $2; exit}'
}
