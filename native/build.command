#!/bin/zsh
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
set -e
cd "$(dirname "$0")/.."
APP='Robot Console.app'
python3 scripts/build_localizations.py
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
xcrun swiftc -target arm64-apple-macos14.0 -parse-as-library -swift-version 5 -module-cache-path /private/tmp/doc-swift-cache -o "$APP/Contents/MacOS/DOCRegia" native/Regia.swift native/InputDraft.swift native/Localization.swift native/VoiceCapture.swift native/Appearance.swift native/AssistantSpeech.swift native/StudioView.swift native/ViewportSupport.swift native/WorkSceneView.swift native/MoveJPreviewView.swift native/ProgramView.swift native/CartesianView.swift native/GuideView.swift native/BridgeLineReader.swift native/FirmwareEditor.swift native/ROSPanel.swift native/APIPanel.swift native/CameraPanel.swift
cp native/Info.plist "$APP/Contents/Info.plist"
cp native/DOCRegia.icns "$APP/Contents/Resources/DOCRegiaCover.icns"
# Every controller module (tests and the Qt launcher excluded): a new module can never be left out.
for module in *.py; do case "$module" in test_*|robot_console.py) ;; *) cp "$module" "$APP/Contents/Resources/" ;; esac; done
cp native/ros_link.py native/ros_observer.py native/native_bridge.py "$APP/Contents/Resources/"
/usr/bin/ditto RegiaDemo "$APP/Contents/Resources/RegiaDemo"
mkdir -p "$APP/Contents/Resources/docs"
cp docs/CAMPI_E_SEQUENZE.md docs/SOTTOPROGRAMMI.md docs/PYTHON_API.md docs/STUDIO.md docs/STUDIO.en.md docs/MULTI_VOICE.md docs/WORK_FRAMES.md docs/MOVEJ_PREVIEW.md docs/IK_JOG.md docs/MOVEL.md docs/COLLISIONI.md docs/PROGRAMMI.md docs/USER_GUIDE.md docs/USER_GUIDE.en.md "$APP/Contents/Resources/docs/"
cp native/Localization/English.json "$APP/Contents/Resources/English.json"
/usr/bin/ditto native/Localization/en.lproj "$APP/Contents/Resources/en.lproj"
/usr/bin/ditto native/Localization/it.lproj "$APP/Contents/Resources/it.lproj"
/usr/bin/ditto models "$APP/Contents/Resources/models"
/usr/bin/ditto examples "$APP/Contents/Resources/examples"
cp LICENSE THIRD_PARTY.md AUTHORS.md "$APP/Contents/Resources/"
/usr/bin/ditto LICENSES "$APP/Contents/Resources/LICENSES"
/usr/bin/codesign --force --sign - "$APP"
