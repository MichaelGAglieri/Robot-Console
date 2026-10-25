# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import os,threading,unittest
from types import SimpleNamespace
from unittest.mock import patch
import serial_transport,server
class PortGuard(unittest.TestCase):
 def test_other_reader_refused_before_open(self):
  result=SimpleNamespace(returncode=0,stdout='p12345\ncserial-monitor\nf3\n',stderr='')
  with patch.object(threading.Thread,'start'):c=server.Controller()
  with patch.object(serial_transport.os.path,'exists',return_value=True),patch.object(serial_transport.subprocess,'run',return_value=result),patch.object(server.os,'open') as opened:
   with patch.object(server.glob,'glob',return_value=['/dev/cu.usbmodemTEST']):
    with self.assertRaisesRegex(ValueError,'occupata'):c.action(dict(op='connect',mode='robot',port='/dev/cu.usbmodemTEST'))
   opened.assert_not_called();self.assertFalse(c.connected)
 def test_free_port_and_own_process_allowed(self):
  for output,rc in [('',1),(f'p{os.getpid()}\ncPython\n',0)]:
   with patch.object(serial_transport.os.path,'exists',return_value=True),patch.object(serial_transport.subprocess,'run',return_value=SimpleNamespace(returncode=rc,stdout=output,stderr='')):
    serial_transport.ensure_port_available('/dev/cu.usbmodemTEST')
 def test_failed_check_is_not_silently_ignored(self):
  with patch.object(serial_transport.os.path,'exists',return_value=True),patch.object(serial_transport.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='permission denied')):
   with self.assertRaisesRegex(ValueError,'verificare'):serial_transport.ensure_port_available('/dev/cu.usbmodemTEST')
 def test_legacy_firmware_diagnosed_but_motion_still_blocked(self):
  with patch.object(threading.Thread,'start'):c=server.Controller()
  c.receive('Formato: j1 180 ... j5 -180; apri; chiudi; h=aiuto.')
  self.assertIn('Firmware di test',c.error);self.assertFalse(c.identified);self.assertFalse(c.speed_confirmed)
if __name__=='__main__':unittest.main()
