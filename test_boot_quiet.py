# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Regression: Mega bootloader must see a quiet UART before the first hello."""
import os,pty,select,time,threading,unittest
from unittest.mock import patch
import server
class MegaBoot(unittest.TestCase):
 def test_silent_boot_then_identity_then_heartbeat(self):
  master,slave=pty.openpty();path=os.ttyname(slave);stop=threading.Event();chunks=[];started=time.monotonic();booted=False
  def board():
   nonlocal booted
   buf=b'';last_byte=started
   while not stop.is_set():
    now=time.monotonic()
    if not booted and now-last_byte>=1.5:
     booted=True;os.write(master,b'DOC REGIA 2\r\n')
    if not select.select([master],[],[],.02)[0]:continue
    raw=os.read(master,1024);chunks.append((time.monotonic(),raw));last_byte=time.monotonic()
    if not booted:continue # Bootloader consumes non-protocol bytes until UART is quiet.
    buf+=raw.replace(b'~',b'')
    while b'\n' in buf:
     line,buf=buf.split(b'\n',1)
     if line==b'hello':os.write(master,b'DOC REGIA 2\r\n')
     elif line.startswith(b'speed '):os.write(master,b'SPEED 5.00\r\n')
  thread=threading.Thread(target=board);thread.start();c=server.Controller()
  try:
   with patch.object(server.glob,'glob',return_value=[path]),patch.object(server.fcntl,'ioctl'):
    c.action(dict(op='connect',mode='robot',port=path));connected=c.connected_at
    until=time.monotonic()+6
    while not c.speed_confirmed and time.monotonic()<until:c.action(dict(op='heartbeat'));time.sleep(.02)
    self.assertTrue(booted);self.assertTrue(c.speed_confirmed);self.assertFalse(c.home)
    self.assertTrue(chunks);self.assertGreaterEqual(chunks[0][0]-connected,server.USB_BOOT_QUIET-.03)
    raw=b''.join(data for _,data in chunks);self.assertNotIn(b'arm',raw);self.assertNotIn(b'j1',raw)
  finally:
   c.action(dict(op='disconnect'));stop.set();thread.join();os.close(master);os.close(slave)
if __name__=='__main__':unittest.main()
