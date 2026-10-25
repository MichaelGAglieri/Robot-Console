#!/bin/zsh
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
set -e
cd "$(dirname "$0")/.."
APP='Robot Console.app'
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
xcrun swiftc -target arm64-apple-macos14.0 -parse-as-library -swift-version 5 -module-cache-path /private/tmp/doc-swift-cache -o "$APP/Contents/MacOS/DOCRegia" native/Regia.swift native/VoiceCapture.swift
cp native/Info.plist "$APP/Contents/Info.plist"
cp native/DOCRegia.icns "$APP/Contents/Resources/DOCRegiaCover.icns"
cp server.py serial_transport.py firmware_tools.py assistant_local.py ollama_local.py native/ros_link.py native/ros_observer.py native/native_bridge.py "$APP/Contents/Resources/"
/usr/bin/ditto RegiaDemo "$APP/Contents/Resources/RegiaDemo"
cp LICENSE THIRD_PARTY.md AUTHORS.md "$APP/Contents/Resources/"
/usr/bin/ditto LICENSES "$APP/Contents/Resources/LICENSES"
/usr/bin/codesign --force --sign - "$APP"
