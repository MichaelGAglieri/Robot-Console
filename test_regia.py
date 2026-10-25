# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import unittest,time
import server
class Tests(unittest.TestCase):
 def setUp(self):
  self.c=server.Controller(); self.c.action({'op':'connect','mode':'demo'});self.c.action({'op':'home_set'});self.c.action({'op':'limits','limits':[[-2,2]]*5})
 def tearDown(self):self.c.halt('test finito');self.c.connected=False
 def wait(self):
  end=time.monotonic()+8
  while self.c.busy and time.monotonic()<end:self.c.browser=time.monotonic();time.sleep(.02)
  self.assertFalse(self.c.busy)
 def test_limits_reject_no_motion(self):
  with self.assertRaises(ValueError):self.c.action({'op':'jog','axis':0,'delta':3})
  self.assertEqual(self.c.pos,[0]*5)
 def test_large_jog_and_limits(self):
  from unittest.mock import Mock
  self.c.action({'op':'limits','limits':[[-360,360]]*5})
  self.c.spawn=Mock()
  for angle in [1,2,5,10,15,20,30,45,60,90,120,150,180,270,360,-360]:
   self.c.action({'op':'jog','axis':0,'delta':angle})
  self.assertEqual(self.c.spawn.call_count,16)
  for angle in [361,-361,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):self.c.action({'op':'jog','axis':0,'delta':angle})
  self.c.pos[0]=1
  with self.assertRaises(ValueError):self.c.action({'op':'jog','axis':0,'delta':360})
  self.assertEqual(self.c.spawn.call_count,16)
 def test_stop_invalidates_home(self):
  self.c.action({'op':'jog','axis':1,'delta':1});self.c.action({'op':'stop'});time.sleep(.1)
  self.assertFalse(self.c.home);self.assertEqual(self.c.pos,[0]*5)
  with self.assertRaises(ValueError):self.c.action({'op':'home'})
 def test_reverse_path(self):
  self.c.action({'op':'jog','axis':0,'delta':.25});self.wait()
  self.c.action({'op':'jog','axis':1,'delta':-.25});self.wait()
  self.assertEqual(len(self.c.trail),2)
  self.c.action({'op':'home'});self.wait();self.assertEqual(self.c.pos,[0]*5);self.assertFalse(self.c.trail)
 def test_replay(self):
  self.c.action({'op':'jog','axis':0,'delta':.25});self.wait()
  self.c.sequence=[dict(name='test',mode='demo',pos=self.c.pos[:],path=self.c.trail[:],grip='non comandata',dwell=0)]
  self.c.action({'op':'home'});self.wait()
  self.c.action({'op':'play','repeat':False});self.wait()
  self.assertEqual(self.c.cycle,1);self.assertEqual(self.c.pos,[0]*5)
 def test_preview_cannot_run_on_robot(self):
  self.c.sequence=[dict(name='preview',mode='demo',pos=[0]*5,path=[],grip='non comandata',dwell=0)]
  self.c.mode='robot'
  with self.assertRaises(ValueError):self.c.action({'op':'play'})
  self.assertFalse(self.c.playing)
 def test_return_owns_motion_until_complete(self):
  self.c.trail=[dict(axis=0,delta=.25),dict(axis=1,delta=.25)];self.c.pos=[.25,.25,0,0,0]
  self.c.action({'op':'home'})
  time.sleep(.6)
  with self.assertRaises(ValueError):self.c.action({'op':'jog','axis':2,'delta':.25})
  self.wait();self.assertEqual(self.c.pos,[0]*5)
 def test_speed_range_and_busy(self):
  for value in [0,20.1,float('nan'),True]:
   with self.assertRaises(ValueError):self.c.action({'op':'set_speed','speed':value})
  for value in [1,10,20,5.5]:
   self.c.action({'op':'set_speed','speed':value});self.assertEqual(self.c.speed,value)
  self.c.busy=True
  with self.assertRaises(ValueError):self.c.action({'op':'set_speed','speed':2})
  self.c.busy=False
 def test_real_speed_requires_matching_ack(self):
  from unittest.mock import Mock
  self.c.mode='robot';self.c.write=Mock()
  self.c.action({'op':'set_speed','speed':2.5})
  self.c.write.assert_called_with('~speed 2.50\n');self.assertFalse(self.c.speed_confirmed)
  with self.assertRaises(ValueError):self.c.action({'op':'jog','axis':0,'delta':1})
  self.c.receive('SPEED 5.00');self.assertFalse(self.c.speed_confirmed)
  self.c.receive('SPEED 2.50');self.assertTrue(self.c.speed_confirmed);self.assertEqual(self.c.speed,2.5)
 def test_firmware_identity_gate_and_reset(self):
  from unittest.mock import Mock
  self.c.mode='robot';self.c.home=False;self.c.identified=False;self.c.speed_confirmed=False;self.c.write=Mock()
  self.c.receive('DOC REGIA 1');self.assertFalse(self.c.identified)
  with self.assertRaises(ValueError):self.c.action({'op':'home_set'})
  self.c.receive('DOC REGIA 2');self.assertTrue(self.c.identified);self.assertFalse(self.c.speed_confirmed)
  self.c.receive('SPEED 5.00');self.c.action({'op':'home_set'});self.assertTrue(self.c.home)
  self.c.receive('DOC REGIA 2');self.assertFalse(self.c.home)
 def test_heartbeat_loss(self):
  self.c.browser=time.monotonic()-3;time.sleep(.1)
  self.assertFalse(self.c.home);self.assertFalse(self.c.connected)
if __name__=='__main__':unittest.main()
