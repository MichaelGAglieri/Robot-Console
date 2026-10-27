#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Run the simulated tests with isolated user data; no real serial device is needed."""
from pathlib import Path
import os,sys,tempfile,subprocess
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='robot-console-tests-') as folder:
 env={**os.environ,'DOC_REGIA_DATA':folder,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
 modules=['test_multi_voice','test_firmware_axes','test_joint_control','test_localization','test_studio','test_regia','test_sequence_edit','test_pose_editor','test_stop_ack','test_boot_quiet','test_usb_handshake','test_serial_guard','test_assistant','test_ollama','native.test_native_bridge']
 raise SystemExit(subprocess.call([sys.executable,'-m','unittest','-v',*modules],cwd=root,env=env))
