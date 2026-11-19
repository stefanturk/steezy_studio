#!/bin/bash
# Create the self-signed code-signing identity that Steezy Studio apps are signed with.
# Run it once; running it again does nothing.
#
# Why it exists: macOS remembers "an app may read your Desktop" against
# the app's code signature. An ad-hoc signature (codesign --sign -) is just a
# hash of the app's bytes, so every rebuild is a different app and the grant is
# lost. Signing with the same certificate every time keeps the identity the
# same across rebuilds, so the permission is asked once.
#
# The certificate is not put in your login keychain. It gets a keychain of its
# own, with a random password made on this Mac (see signing_keychain.sh), because codesign
# cannot use a key in the login keychain without a click-through dialog - which
# a build script cannot answer. The key signs nothing but local Steezy Studio apps on this
# machine; it is not an Apple Developer ID and vouches for nothing to anyone.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=signing_keychain.sh
. "$HERE/signing_keychain.sh"

if [ -f "$SIGNING_KEYCHAIN" ] && security find-certificate -c "$SIGNING_NAME" "$SIGNING_KEYCHAIN" >/dev/null 2>&1; then
    if _signing_unlock_any >/dev/null; then
        security lock-keychain "$SIGNING_KEYCHAIN" 2>/dev/null || true
        echo "\"$SIGNING_NAME\" already exists in $SIGNING_KEYCHAIN."
        exit 0
    fi
    # Its password is lost (signing_password deleted): no build could ever sign again, so start over.
    # The new certificate means macOS asks for Desktop access once more.
    echo "Can't open $SIGNING_KEYCHAIN with any known password; making a new signing identity." >&2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat > "$WORK/openssl.cnf" <<CNF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $SIGNING_NAME
[ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
CNF

/usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -keyout "$WORK/key.pem" -out "$WORK/cert.pem" -config "$WORK/openssl.cnf" 2>/dev/null

# The .p12 password only protects the file for the second it exists.
/usr/bin/openssl pkcs12 -export -inkey "$WORK/key.pem" -in "$WORK/cert.pem" \
    -out "$WORK/identity.p12" -passout pass:temp

# A keychain of its own with a random password (see signing_keychain.sh); it locks after 10 minutes.
create_signing_keychain
security import "$WORK/identity.p12" -k "$SIGNING_KEYCHAIN" -P temp -T /usr/bin/codesign >/dev/null
# Lets codesign use the key without a dialog.
security set-key-partition-list -S apple-tool:,apple: -s -k "$(signing_password)" "$SIGNING_KEYCHAIN" >/dev/null

open_signing_keychain
close_signing_keychain
echo "Created \"$SIGNING_NAME\" in $SIGNING_KEYCHAIN"
