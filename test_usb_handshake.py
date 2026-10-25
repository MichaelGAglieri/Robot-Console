# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import os,pty,time,unittest,threading
from unittest.mock import patch
import server
class Handshake(unittest.TestCase):
 def test_retries_boot_and_recognizes_then_confirms_speed_without_arm(self):
  master,slave=pty.openpty();path=os.ttyname(slave);received=[];stop=threading.Event()
  def board():
   import select
   buf=b''
   while not stop.is_set():
    if not select.select([master],[],[],.05)[0]:continue
    try:chunk=os.read(master,1024)
    except OSError:return
    received.append(chunk);buf+=chunk.replace(b'~',b'')
    while b'\n' in buf:
     line,buf=buf.split(b'\n',1)
     if line==b'hello':os.write(master,b'DOC REGIA 2\r\n')
     if line.startswith(b'speed '):os.write(master,b'SPEED 5.00\r\n')
  t=threading.Thread(target=board);t.start();c=server.Controller()
  try:
   with patch.object(server.glob,'glob',return_value=[path]),patch.object(server.fcntl,'ioctl') as ioctl:
    c.action(dict(op='connect',mode='robot',port=path))
    deadline=time.monotonic()+6
    while not c.speed_confirmed and time.monotonic()<deadline:c.action(dict(op='heartbeat'));time.sleep(.03)
    self.assertTrue(c.identified);self.assertTrue(c.speed_confirmed);self.assertFalse(c.home)
    self.assertEqual(ioctl.call_count,2)
    raw=b''.join(received);self.assertNotIn(b'arm',raw);self.assertNotIn(b'j1',raw)
  finally:
   c.action(dict(op='disconnect'));stop.set();t.join();os.close(master);os.close(slave)
if __name__=='__main__':unittest.main()
