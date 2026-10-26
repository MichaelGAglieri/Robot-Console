# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Protocol tests: only demo mode; opening a serial port is forbidden."""
import subprocess,sys,tempfile,json,os,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class BridgeTests(unittest.TestCase):
 def test_native_protocol_and_eof(self):
  with tempfile.TemporaryDirectory() as folder:
   env={**os.environ,'DOC_REGIA_DATA':folder,'PYTHONPATH':str(ROOT)}
   p=subprocess.Popen([sys.executable,'-u',str(ROOT/'native/native_bridge.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
   def call(op,**args):
    p.stdin.write(json.dumps(dict(op=op,**args))+'\n');p.stdin.flush()
    r=json.loads(p.stdout.readline());self.assertNotIn('error',r);return r['state']
   try:
    s=call('heartbeat');self.assertFalse(s['connected']);self.assertEqual(s['mode'],'demo')
    call('connect',mode='demo');call('home_set');call('limits',limits=[[-2,2]]*5)
    call('jog',axis=0,delta=.25)
    for _ in range(50):
     s=call('heartbeat')
     if not s['busy']:break
     time.sleep(.04)
    self.assertEqual(s['pos'][0],.25)
    call('record',name='native preview',dwell=0)
    call('home')
    while call('heartbeat')['busy']:time.sleep(.04)
    call('play',repeat=True);call('end_cycle')
    while True:
     s=call('heartbeat')
     if not s['busy']:break
     time.sleep(.04)
    self.assertEqual(s['cycle'],1);self.assertEqual(s['pos'],[0]*6)
    self.assertTrue((Path(folder)/'sequenza.json').exists())
    p.stdin.close();self.assertEqual(p.wait(timeout=3),0)
   finally:
    if p.poll() is None:p.kill();p.wait()
    p.stdout.close();p.stderr.close()
 def test_demo_never_opens_serial(self):
  # Patch low-level serial open: a single attempt fails the test immediately.
  sys.path.insert(0,str(ROOT))
  import server
  from unittest.mock import patch
  c=server.Controller()
  try:
   with patch.object(server.os,'open',side_effect=AssertionError('Serial must not open in preview')) as opened:
    c.action({'op':'connect','mode':'demo'});c.action({'op':'home_set'})
    c.action({'op':'limits','limits':[[-2,2]]*5});c.action({'op':'jog','axis':0,'delta':.25})
    while c.busy:c.action({'op':'heartbeat'});time.sleep(.04)
    c.action({'op':'servo','command':'apri'})
    while c.busy:c.action({'op':'heartbeat'});time.sleep(.04)
    c.action({'op':'home'})
    while c.busy:c.action({'op':'heartbeat'});time.sleep(.04)
    c.action({'op':'stop'});opened.assert_not_called()
  finally:c.connected=False
if __name__=='__main__':unittest.main()
