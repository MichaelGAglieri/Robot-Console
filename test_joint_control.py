# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Control/ACK invariants; serial is mocked and never opened."""
import copy,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import server
from firmware_workspace import FirmwareWorkspace,DEFAULT
class JointControlTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
  self.data=patch.object(server,'DATA',self.folder);self.data.start()
  with patch.object(server.Controller,'io',lambda _:None):self.c=server.Controller()
  self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='home_set'));self.c.limits=[[-90,90] for _ in range(6)];self.c.write=Mock()
 def tearDown(self):self.data.stop();self.temp.cleanup()
 def real(self):
  c=self.c;c.mode='robot';c.axis_control=True;c.drive_caps=[True,False,True,True,True,False];c.drive_state=[True,None,True,True,True,None]
 def test_speeds_independent_persist_and_all_speed_resets_all(self):
  c=self.c;c.action(dict(op='set_axis_speed',axis=0,speed=2));c.action(dict(op='set_axis_speed',axis=1,speed=12))
  self.assertEqual(c.axis_speeds[:3],[2,12,5]);self.assertEqual(json.loads((self.folder/'axis_speeds.json').read_text()),c.axis_speeds)
  with patch.object(server.Controller,'io',lambda _:None):other=server.Controller()
  self.assertEqual(other.axis_speeds,c.axis_speeds)
  c.action(dict(op='set_speed',speed=3));self.assertEqual(c.axis_speeds,[3]*6)
 def test_bad_speed_and_busy_do_not_mutate(self):
  c=self.c
  for value in [True,0,21,float('nan'),'5']:
   with self.assertRaises(ValueError):c.action(dict(op='set_axis_speed',axis=0,speed=value))
  for axis in [-1,6,True,1.5]:
   with self.assertRaises(ValueError):c.action(dict(op='set_axis_speed',axis=axis,speed=3))
  c.busy=True
  with self.assertRaises(ValueError):c.action(dict(op='set_axis_speed',axis=0,speed=3))
  self.assertEqual(c.axis_speeds,[5]*6);c.write.assert_not_called()
 def test_each_segment_waits_for_matching_speed_before_motion(self):
  c=self.c;self.real();c.axis_speeds=[2,12,5,5,5,5];commands=[];durations=[]
  def serial(text):
   commands.append(text)
   if text.startswith('~speed '):c.receive('SPEED '+text.split()[1])
   elif text.startswith('j'):durations.append(c.motion['duration']);c.receive('j1 DONE: test')
  c.write.side_effect=serial
  c.move(0,12,c.generation);c.move(1,12,c.generation)
  self.assertEqual(commands,['~speed 2.00\n','j1 12.00\n','~speed 12.00\n','j2 12.00\n'])
  self.assertEqual(durations,[6.5,1.5]);self.assertEqual(c.pos[:2],[12,12])
 def test_speed_timeout_never_sends_motor_command(self):
  c=self.c;self.real();c.axis_speeds[0]=2
  counter=iter(range(0,100,10))
  with patch.object(server.time,'monotonic',side_effect=lambda:next(counter)):
   with self.assertRaisesRegex(ValueError,'non confermata'):c.move(0,1,c.generation)
  self.assertEqual(c.write.call_args_list[0].args[0],'~speed 2.00\n');self.assertFalse(any(x.args[0].startswith('j') for x in c.write.call_args_list))
 def test_axis_stop_cancels_speed_preparation_without_motion(self):
  c=self.c;self.real();c.axis_speeds[0]=2;errors=[]
  def run():
   try:c.move(0,1,c.generation)
   except ValueError as e:errors.append(str(e))
  t=threading.Thread(target=run);t.start();deadline=time.monotonic()+1
  while c.preparing_axis is None and time.monotonic()<deadline:time.sleep(.005)
  c.action(dict(op='axis_stop',axis=0));t.join(1)
  self.assertFalse(t.is_alive());self.assertEqual(errors,['Interrotto']);self.assertFalse(c.home)
  self.assertFalse(any(x.args[0].startswith('j') for x in c.write.call_args_list));self.assertIn('!',[x.args[0] for x in c.write.call_args_list])
 def test_stop_inactive_joint_leaves_active_joint_alone(self):
  c=self.c;c.motion=dict(axis=1);c.busy=True;g=c.generation
  c.action(dict(op='axis_stop',axis=0));self.assertEqual(c.generation,g);self.assertTrue(c.busy);self.assertTrue(c.home);c.write.assert_not_called()
 def test_stop_active_joint_holds_torque_and_cancels_sequence(self):
  c=self.c;c.motion=dict(axis=0);c.busy=True;c.playing=True
  c.action(dict(op='axis_stop',axis=0));c.write.assert_called_once_with('!');self.assertFalse(c.home);self.assertFalse(c.playing);self.assertFalse(c.busy)
 def test_disable_active_axis_atomic_no_racing_bang(self):
  c=self.c;self.real();c.motion=dict(axis=0);c.busy=True;c.playing=True
  c.action(dict(op='joint_enable',axis=0,enabled=False))
  c.write.assert_called_once_with('~off 1\n');self.assertFalse(c.axes_enabled[0]);self.assertFalse(c.home);self.assertFalse(c.playing);self.assertTrue(c.awaiting_halt)
  self.assertTrue(c.drive_state[0]);self.assertIn(0,c.pending_off)
  c.receive('HALTED');c.receive('DRIVES 0?111?');c.receive('AXIS_OFF 1');self.assertFalse(c.drive_state[0]);self.assertFalse(c.pending_off)
 def test_disable_unmanaged_never_reports_current_off(self):
  c=self.c;self.real();c.action(dict(op='joint_enable',axis=1,enabled=False));c.receive('DRIVES 1?111?');c.receive('AXIS_OFF 2')
  self.assertIsNone(c.drive_state[1]);self.assertIn('ENA non collegato',c.events[-1]);self.assertFalse(c.axes_enabled[1])
 def test_ack_without_driver_off_does_not_claim_success(self):
  c=self.c;self.real();c.action(dict(op='joint_enable',axis=0,enabled=False));c.receive('AXIS_OFF 1')
  self.assertIn('stato del driver incerto',c.error);self.assertTrue(c.drive_state[0])
 def test_old_firmware_rejects_electrical_disable(self):
  c=self.c;self.real();c.axis_control=False
  with self.assertRaisesRegex(ValueError,'nuovo firmware'):c.action(dict(op='joint_enable',axis=0,enabled=False))
  self.assertTrue(c.axes_enabled[0]);c.write.assert_not_called()
 def test_including_requires_home_and_does_not_send_arm(self):
  c=self.c;self.real();c.axes_enabled[0]=False;c.drive_state[0]=False
  c.action(dict(op='joint_enable',axis=0,enabled=True));c.write.assert_called_once_with('~mask 111111\n');self.assertFalse(c.home);self.assertFalse(c.drive_state[0])
 def test_home_synchronizes_disabled_mask_before_arm(self):
  c=self.c;self.real();c.axes_enabled[0]=False;c.action(dict(op='home_set'))
  self.assertEqual([x.args[0] for x in c.write.call_args_list],['~mask 011111\n','~arm\n'])
 def test_home_waits_for_stop_and_off_ack(self):
  c=self.c;self.real();c.awaiting_halt=True
  with self.assertRaisesRegex(ValueError,'STOP'):c.action(dict(op='home_set'))
  c.awaiting_halt=False;c.pending_off[0]=time.monotonic()
  with self.assertRaisesRegex(ValueError,'disabilitazione'):c.action(dict(op='home_set'))
  c.write.assert_not_called()
 def test_protocol_capabilities_not_assumed_or_carried_across_connect(self):
  c=self.c;self.real();c.receive('FEATURES AXIS_ENABLE');c.receive('DRIVE_CAPS 101110');self.assertEqual(c.drive_caps,[True,False,True,True,True,False])
  c.action(dict(op='disconnect'));c.action(dict(op='connect',mode='demo'));self.assertFalse(c.axis_control);self.assertEqual(c.drive_state,[None]*6)
 def test_workspace_upgrade_preserves_profile_headers_and_revision(self):
  c=self.c;c.connected=False;w=FirmwareWorkspace(self.folder,c);profile=copy.deepcopy(DEFAULT);profile['axes'][0].update(reduction=20,microstep=16);w.generate(profile)
  old=w.file('RegiaDemo.ino').read_text().replace('FEATURES AXIS_ENABLE','LEGACY');w.save_file('RegiaDemo.ino',old)
  header=w.file('PinzaTimer1.h');header.write_text(header.read_text()+'\n// user header\n')
  self.assertFalse(w.state()['axis_control_source']);w.upgrade_axis_control();self.assertTrue(w.state()['axis_control_source']);self.assertEqual(w.profile['axes'][0]['reduction'],20)
  self.assertIn('// user header',header.read_text());self.assertIn('{3200, 1600',w.file('RegiaDemo.ino').read_text());self.assertTrue(any(p.read_text()==old for p in (w.folder/'revisions').glob('*/RegiaDemo.ino')));c.write.assert_not_called()
if __name__=='__main__':unittest.main()
