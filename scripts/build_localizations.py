#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Generate deterministic Apple strings files from the reviewed bilingual catalog."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'native/Localization';catalog=json.loads((folder/'English.json').read_text())
for language in ('it','en'):
 directory=folder/(language+'.lproj');directory.mkdir(exist_ok=True)
 text='// Generated from native/Localization/English.json.\n'
 text+='\n'.join(json.dumps(k,ensure_ascii=False)+' = '+json.dumps(v if language=='en' else k,ensure_ascii=False)+';' for k,v in sorted(catalog.items()))+'\n'
 (directory/'Localizable.strings').write_text(text)
privacy={'NSCameraUsageDescription':'Show local camera video and detect QR codes without sending images to external services.','NSMicrophoneUsageDescription':'Dictate a question in Robot Console chat.','NSSpeechRecognitionUsageDescription':'Transcribe questions on this Mac before you confirm sending them.'}
(folder/'en.lproj/InfoPlist.strings').write_text('\n'.join(json.dumps(k)+' = '+json.dumps(v)+';' for k,v in privacy.items())+'\n')
print('Generated',len(catalog),'bilingual keys.')
