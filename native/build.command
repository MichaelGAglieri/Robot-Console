#!/bin/zsh
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
set -e
cd "$(dirname "$0")/.."
APP='Robot Console.app'
python3 scripts/build_localizations.py
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
xcrun swiftc -target arm64-apple-macos14.0 -parse-as-library -swift-version 5 -module-cache-path /private/tmp/doc-swift-cache -o "$APP/Contents/MacOS/DOCRegia" native/Regia.swift native/Localization.swift native/VoiceCapture.swift native/Appearance.swift native/AssistantSpeech.swift native/StudioView.swift native/BridgeLineReader.swift native/FirmwareEditor.swift native/ROSPanel.swift native/CameraPanel.swift
cp native/Info.plist "$APP/Contents/Info.plist"
cp native/DOCRegia.icns "$APP/Contents/Resources/DOCRegiaCover.icns"
cp local_api.py tool_manager.py firmware_workspace.py robot_model.py studio.py server.py serial_transport.py firmware_tools.py assistant_local.py ollama_local.py native/ros_link.py native/ros_observer.py native/native_bridge.py "$APP/Contents/Resources/"
/usr/bin/ditto RegiaDemo "$APP/Contents/Resources/RegiaDemo"
mkdir -p "$APP/Contents/Resources/docs"
cp docs/STUDIO.md docs/STUDIO.en.md "$APP/Contents/Resources/docs/"
cp native/Localization/English.json "$APP/Contents/Resources/English.json"
/usr/bin/ditto native/Localization/en.lproj "$APP/Contents/Resources/en.lproj"
/usr/bin/ditto native/Localization/it.lproj "$APP/Contents/Resources/it.lproj"
/usr/bin/ditto models "$APP/Contents/Resources/models"
/usr/bin/ditto examples "$APP/Contents/Resources/examples"
cp LICENSE THIRD_PARTY.md AUTHORS.md "$APP/Contents/Resources/"
/usr/bin/ditto LICENSES "$APP/Contents/Resources/LICENSES"
/usr/bin/codesign --force --sign - "$APP"
