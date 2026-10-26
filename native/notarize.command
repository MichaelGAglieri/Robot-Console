#!/bin/zsh
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
# Explicit release action: requires the author's Developer ID and Keychain profile.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CODE_SIGN_IDENTITY:?Set a Developer ID Application identity from your Keychain}"
: "${NOTARY_KEYCHAIN_PROFILE:?Set the existing notarytool Keychain profile name}"
[[ "$CODE_SIGN_IDENTITY" == 'Developer ID Application:'* ]] || { print -u2 'A Developer ID Application certificate is required.'; exit 1; }
[[ -d 'Robot Console.app' ]] || { print -u2 'Build the app first.'; exit 1; }
RELEASE_ROOT="${RELEASE_DIRECTORY:-$PWD/build/notarized-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$RELEASE_ROOT"
RELEASE_APP="$RELEASE_ROOT/Robot Console.app"
/usr/bin/ditto 'Robot Console.app' "$RELEASE_APP"
# Current build contains one native executable and text resources; extra runtimes
# require an explicit inside-out signing plan before using this release script.
[[ ! -d "$RELEASE_APP/Contents/Resources/Tools" ]] || { print -u2 'Sign bundled tools individually before adapting this script.'; exit 1; }
/usr/bin/codesign --force --options runtime --timestamp --sign "$CODE_SIGN_IDENTITY" "$RELEASE_APP/Contents/MacOS/DOCRegia"
/usr/bin/codesign --force --options runtime --timestamp --sign "$CODE_SIGN_IDENTITY" "$RELEASE_APP"
/usr/bin/codesign --verify --strict --verbose=2 "$RELEASE_APP"
/usr/bin/ditto -c -k --keepParent "$RELEASE_APP" "$RELEASE_ROOT/submission.zip"
xcrun notarytool submit "$RELEASE_ROOT/submission.zip" --keychain-profile "$NOTARY_KEYCHAIN_PROFILE" --wait --output-format json > "$RELEASE_ROOT/notary-result.json"
python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); sys.exit(0 if r.get("status")=="Accepted" else "Notarization was not accepted; inspect notary-result.json and the Apple log.")' "$RELEASE_ROOT/notary-result.json"
xcrun stapler staple "$RELEASE_APP"
xcrun stapler validate "$RELEASE_APP"
/usr/sbin/spctl --assess --type execute --verbose=2 "$RELEASE_APP"
/usr/bin/ditto -c -k --keepParent "$RELEASE_APP" "$RELEASE_ROOT/Robot-Console-macOS-arm64.zip"
print "Signed, notarized and stapled archive: $RELEASE_ROOT/Robot-Console-macOS-arm64.zip"
