# SPDX-License-Identifier: GPL-3.0-only
import copy,math,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import server
from studio import Studio
from voice_commands import parse_command,confirmation
class MultiVoiceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.data=patch.object(server,'DATA',Path(self.temp.name));self.data.start()
  with patch.object(server.Controller,'io',lambda _:None):self.c=server.Controller()
  self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='home_set'));self.c.limits=[[-180,180] for _ in range(6)];self.c.write=Mock()
 def tearDown(self):self.c.halt('end',False);self.data.stop();self.temp.cleanup()
 def test_robot_events_have_time_mode_order_and_bounded_history(self):
  c=self.c;before=time.time()
  for i in range(305):c.log('J1 command '+str(i))
  events=c.state()['robot_events'];self.assertEqual(len(events),300);self.assertEqual(len(c.events),30)
  self.assertEqual(events[-1]['text'],'J1 command 304');self.assertEqual(events[-1]['mode'],'demo')
  self.assertGreaterEqual(events[0]['time'],before);self.assertEqual([e['id'] for e in events],sorted(e['id'] for e in events))
 def test_plan_individual_limits_and_aggregate_budget(self):
  c=self.c;c.axis_speeds=[20,3,8,5,5,5];p=c.group_plan([10,-20,5,0,0,0]);effective=p[4]
  self.assertLessEqual(sum(c.pulses_per_rev[i]*effective[i]/360 for i in p[2]),2000.1)
  self.assertAlmostEqual(effective[0]*2,effective[1]);self.assertLessEqual(effective[1],3)
  self.assertAlmostEqual(server.motion_fraction(1,p[6],p[5]/2,p[7]),.5)
 def test_shared_speeds_change_group_preview_and_actual_packet(self):
  c=self.c;d=[10,20,0,0,0,0]
  first=c.preview_group(d);self.assertTrue(first['valid']);c.write.assert_not_called()
  c.action(dict(op='set_axis_speed',axis=0,speed=1))
  slower=c.preview_group(d);self.assertGreater(slower['duration'],first['duration']);self.assertLessEqual(slower['peaks'][0],1.)
  self.assertEqual(slower['requested'],c.axis_speeds);self.assertEqual(c.pos,[0]*6);c.write.assert_not_called()
  c.mode='robot';c.multi_axis=True
  def reply(text):
   if text.startswith('~multi '):c.receive('MULTI ACK');c.receive('MULTI DONE: simulated pulses')
  c.write.side_effect=reply;c.move_group(d,c.generation,False)
  packet=c.write.call_args.args[0].split()
  self.assertEqual(packet[2],'1.00');self.assertEqual(packet[4],'5.00')
 def test_changed_speed_invalidates_reviewed_group(self):
  c=self.c;d=[10,20,0,0,0,0];review=c.preview_group(d);c.spawn=Mock()
  c.action(dict(op='set_axis_speed',axis=1,speed=2))
  with self.assertRaisesRegex(ValueError,'riepilogo'):c.action(dict(op='multi_jog',deltas=d,context=review['context']))
  c.spawn.assert_not_called();updated=c.preview_group(d)
  c.action(dict(op='multi_jog',deltas=d,context=updated['context']));c.spawn.assert_called_once()
 def test_preview_peak_acceleration_zero_and_voice_use_shared_values(self):
  c=self.c;c.axis_speeds=[10]*6;short=c.preview_group([.1,.2,0,0,0,0])
  self.assertTrue(short['valid']);self.assertLess(short['peaks'][1],short['effective'][1]);self.assertEqual(short['peaks'][2:], [0]*4)
  self.assertFalse(c.preview_group([0]*6)['valid']);self.assertFalse(c.preview_group([float('nan')]*6)['valid']);c.write.assert_not_called()
  spoken=c.prepare_voice('muovi J1 di 1 e J2 di 2')
  self.assertIn('picco previsto',spoken['summary']);c.write.assert_not_called()
 def test_reject_atomic_disabled_limit_j6_and_legacy(self):
  c=self.c
  for values in ([1,999,0,0,0,0],[1,float('nan'),0,0,0,0],[1,True,0,0,0,0]):
   with self.assertRaises(ValueError):c.action(dict(op='multi_jog',deltas=values))
  c.axes_enabled[1]=False
  with self.assertRaises(ValueError):c.action(dict(op='multi_jog',deltas=[1,2,0,0,0,0]))
  c.axes_enabled[1]=True;c.mode='robot'
  with self.assertRaisesRegex(ValueError,'MULTI_AXIS'):c.group_plan([1,2,0,0,0,0])
  c.multi_axis=True
  with self.assertRaises(ValueError):c.group_plan([1,2,0,0,0,1])
  c.write.assert_not_called()
 def test_group_record_reverse_and_portable_roundtrip(self):
  c=self.c;c.move_group([.1,-.2,0,0,0,0],c.generation)
  self.assertEqual(c.pos[:2],[.1,-.2]);self.assertEqual(len(server.path_units(c.trail)),1)
  c.busy=False;c.action(dict(op='record',name='group',dwell=0));pose=c.sequence[0]
  self.assertEqual(Studio.validate_project_sequence([pose])[0]['path'],pose['path'])
  c.back(c.generation);self.assertEqual(c.pos,[0]*6);self.assertFalse(c.trail)
  c.follow_path(pose['path'],c.generation);self.assertEqual(c.trail,pose['path']);self.assertEqual(c.pos,pose['pos'])
 def test_stop_any_group_member_cancels_all(self):
  c=self.c;errors=[]
  def run():
   try:c.move_group([90,90,0,0,0,0],c.generation)
   except ValueError as e:errors.append(str(e))
  t=threading.Thread(target=run);t.start()
  for _ in range(100):
   if c.motion:break
   time.sleep(.005)
  c.action(dict(op='axis_stop',axis=1));t.join(2)
  self.assertFalse(t.is_alive());self.assertFalse(c.home);self.assertFalse(c.trail);self.assertEqual(c.pos,[0]*6);self.assertEqual(errors,['Interrotto'])
 def test_done_requires_multi_ack_and_multi_done(self):
  c=self.c;c.motion=dict(axes=[0,1]);c.done.clear()
  c.receive('j1 DONE: old');self.assertFalse(c.done.is_set())
  c.receive('MULTI DONE: missing ack');self.assertFalse(c.done.is_set())
  c.receive('MULTI ACK');c.receive('MULTI DONE: ok');self.assertTrue(c.done.is_set())
  c.receive('DOC REGIA 4');self.assertFalse(c.multi_axis)
 def test_group_structure_rejects_duplicate_and_noncontiguous(self):
  for edges in ([dict(axis=0,delta=1,group='a')]*2,[dict(axis=0,delta=1,group='a'),dict(axis=1,delta=1),dict(axis=2,delta=1,group='a')]):
   with self.assertRaises(ValueError):server.path_units(edges)
 def test_voice_relative_absolute_multiple_and_english(self):
  self.assertEqual(parse_command('muovi J2 di 45 gradi')['targets'][0],dict(axis=1,value=45,relative=True))
  self.assertEqual(parse_command('muovi J3 di meno 20 gradi')['targets'][0]['value'],-20)
  self.assertEqual(len(parse_command('muovi il J1 a 45 gradi, J2 a 30 e J3 a - 10')['targets']),3)
  self.assertEqual(parse_command('move joint two by minus 20 degrees')['targets'][0]['value'],-20)
  self.assertEqual(parse_command('avvia posa uno'),dict(op='pose_start',index=0))
  for text in ('muovi j1 a 20 e j1 a 30','avvia posa 0','muovi j2 di nan gradi','muovi j2 di 450 gradi','muovi j1 a 10 poi cancella tutto'):
   with self.assertRaises(ValueError):parse_command(text)
 def test_voice_prepare_never_moves_exact_confirmation_one_use(self):
  c=self.c;c.pos[0]=10
  p=c.prepare_voice('muovi J1 a 45 e J2 di 30 gradi');c.write.assert_not_called();self.assertEqual(c.pending_voice['command']['deltas'][:2],[35,30])
  c.spawn=Mock()
  with self.assertRaises(ValueError):c.action(dict(op='voice_execute',token=p['token']))
  c.action(dict(op='voice_execute',token=p['token'],confirmation='sì confermo'));c.spawn.assert_called_once()
  with self.assertRaises(ValueError):c.action(dict(op='voice_execute',token=p['token'],confirmation='sì confermo'))
 def test_voice_wrong_cancel_expiry_and_changed_limits(self):
  c=self.c;c.spawn=Mock()
  p=c.prepare_voice('muovi J1 di 10 gradi')
  with self.assertRaises(ValueError):c.action(dict(op='voice_execute',token=p['token'],confirmation='sì confermo ma no'))
  c.action(dict(op='voice_execute',token=p['token'],confirmation='annulla'));self.assertIsNone(c.pending_voice)
  p=c.prepare_voice('muovi J1 di 10 gradi');c.limits[0]=[-5,5]
  with self.assertRaises(ValueError):c.action(dict(op='voice_execute',token=p['token'],confirmation='confermo'))
  c.limits[0]=[-90,90];p=c.prepare_voice('muovi J1 di 10 gradi');c.pending_voice['expires']=0
  with self.assertRaises(ValueError):c.action(dict(op='voice_execute',token=p['token'],confirmation='confermo'))
  c.spawn.assert_not_called();self.assertIsNone(confirmation('muovi j1 a 20'))
 def test_pose_voice_checks_mode_enabled_revision(self):
  c=self.c;c.sequence=[dict(name='uno',mode='demo',pos=[1,0,0,0,0,0],path=[dict(axis=0,delta=1)],grip='chiudi',dwell=0,enabled=True)]
  p=c.prepare_voice('avvia posa 1');self.assertIn('pinza',p['summary']);c.sequence_revision+=1
  with self.assertRaises(ValueError):c.action(dict(op='voice_execute',token=p['token'],confirmation='confermo'))
  c.sequence[0]['enabled']=False
  with self.assertRaises(ValueError):c.prepare_voice('avvia posa 1')
  c.write.assert_not_called()
