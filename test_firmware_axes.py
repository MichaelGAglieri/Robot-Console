# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Execute real firmware command logic with inert host stubs, never an Arduino."""
import shutil,subprocess,tempfile,unittest
from pathlib import Path
class FirmwareAxisTests(unittest.TestCase):
 def test_actual_sketch_enable_and_stop_logic(self):
  compiler=shutil.which('clang++') or shutil.which('g++')
  if not compiler:self.skipTest('C++ compiler unavailable')
  root=Path(__file__).parent
  with tempfile.TemporaryDirectory(prefix='robot-console-firmware-host-') as folder:
   tmp=Path(folder);source=(root/'RegiaDemo/RegiaDemo.ino').read_text().replace('#include "PinzaTimer1.h"','// Inert servo functions provided by harness.')
   (tmp/'sketch.inc').write_text(source)
   result=subprocess.run([compiler,'-std=c++17','-I'+str(tmp),'-I'+str(root/'tests/firmware_stubs'),str(root/'tests/firmware_axis_harness.cpp'),'-o',str(tmp/'check')],capture_output=True,text=True,timeout=60)
   self.assertEqual(result.returncode,0,result.stderr)
   run=subprocess.run([str(tmp/'check')],capture_output=True,text=True,timeout=5);self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertIn('PASS:',run.stdout)
