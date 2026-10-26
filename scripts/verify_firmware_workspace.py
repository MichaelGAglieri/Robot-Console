#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Compile original and generated firmware using installed dependencies. No USB access."""
import copy, os, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'native'))
with tempfile.TemporaryDirectory(prefix='robot-console-compile-') as directory:
 os.environ['DOC_REGIA_DATA']=directory;os.environ['DOC_REGIA_NO_HARDWARE']='1'
 import server
 from firmware_workspace import FirmwareWorkspace, DEFAULT
 from firmware_tools import FirmwareTools
 controller=server.Controller();tools=FirmwareTools(directory,controller);workspace=FirmwareWorkspace(directory,controller);tools.workspace=workspace
 profiles=[copy.deepcopy(DEFAULT) for _ in range(3)]
 profiles[2]['axes'][5].update(active=True,step_pin=42,dir_pin=44)
 profiles[1]['axes'][0].update(microstep=16,reduction=20.,invert=True)
 profiles[1]['axes'][1].update(microstep=10,reduction=30.)
 for index,profile in enumerate(profiles):
  workspace.generate(profile);tools.start('compile');tools.thread.join(200)
  print('Profile',index+1,workspace.state()['identity'],tools.status,flush=True)
  print('\n'.join(tools.logs[-12:]),flush=True)
  if tools.busy or not tools.success:tools.close();raise SystemExit('Compilation failed: '+tools.error)
 tools.close()
print('PASS: all three saved firmware profiles compile; no scan, connection or upload performed.')
