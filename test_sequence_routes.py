# SPDX-License-Identifier: GPL-3.0-only
"""Regressions for deleted poses, direct transitions and reference-preserving edits."""
import copy
import math
from unittest.mock import Mock
from test_program import ProgramBase
from server import direct_units

class DirectSequenceTests(ProgramBase):
 def setUp(self):
  super().setUp();self.groups=[];self.actions=[]
  def move(deltas,g,record=True,scale=1.):
   self.c.wait_ready(g);plan=self.c.group_plan(deltas,scale=scale)
   self.groups.append(dict(starts=self.c.pos[:],deltas=deltas[:],targets=plan[1],requested=plan[3],duration=plan[5]))
   self.c.pos=plan[1]
   if record:
    import uuid
    key=uuid.uuid4().hex;self.c.trail.extend(dict(axis=i,delta=d,group=key) for i,d in enumerate(deltas) if d)
  self.c.move_group=move;self.c.servo=lambda cmd,g:self.actions.append(cmd)
  # Geometry regressions have their own tests; these route tests inspect exact groups.
  self.s.collision_report=lambda q:[]
 def pose(self,name,angles,path=None):
  return dict(name=name,mode='demo',enabled=True,pos=angles+[0.]*(6-len(angles)),path=path or [],grip='non comandata',dwell=0.)
 def play(self,**opts):
  self.c.action(dict(op='play',**opts));self.wait()
 def edit(self,op,**values):self.c.action(dict(op=op,revision=self.c.sequence_revision,**values))
 def test_delete_removes_old_waypoints_from_motion_and_home(self):
  self.c.sequence=[self.pose('deleted',[30,0]),self.pose('keep',[-20,10],[dict(axis=0,delta=30),dict(axis=0,delta=-50),dict(axis=1,delta=10)])]
  self.edit('pose_delete',index=0);self.play()
  self.assertEqual([x['targets'] for x in self.groups],[[-20,10,0,0,0,0]])
  self.assertTrue(self.c.home);self.c.action(dict(op='home'));self.wait()
  self.assertEqual([x['targets'] for x in self.groups],[[-20,10,0,0,0,0],[0.]*6])
 def test_reorder_and_disable_use_visible_targets_from_current_position(self):
  self.c.pos=[3,4,0,0,0,0]
  self.assertNotIn('torna prima a HOME',self.c.guide())
  self.c.sequence=[self.pose('A',[8,2]),self.pose('skip',[40,30]),self.pose('B',[-4,6])]
  self.edit('pose_enable',index=1,enabled=False);self.edit('pose_move',index=2,target=0);self.play()
  self.assertEqual([x['targets'] for x in self.groups],[[-4,6,0,0,0,0],[8,2,0,0,0,0]])
  self.assertEqual(self.groups[0]['starts'],[3,4,0,0,0,0]);self.assertTrue(self.c.home)
 def test_home_return_is_explicit_and_joint_speeds_are_preserved(self):
  self.c.axis_speeds=[2,12,5,5,5,5];self.c.sequence=[self.pose('A',[6,10])]
  self.play(return_home=True)
  self.assertEqual([g['targets'] for g in self.groups],[[6,10,0,0,0,0],[0.]*6])
  self.assertTrue(all(g['requested']==[2,12,5,5,5,5] for g in self.groups));self.assertEqual(self.c.trail,[])
 def test_repeat_connects_last_to_first_without_automatic_home(self):
  self.c.sequence=[self.pose('A',[4,1]),self.pose('B',[8,2])]
  original=self.c.log
  def log(text):
   original(text)
   if self.c.cycle>=2:self.c.repeat_cycle=False
  self.c.log=log;self.play(repeat=True)
  self.assertEqual([g['targets'][:2] for g in self.groups],[[4,1],[8,2],[4,1],[8,2]])
  self.assertTrue(self.c.home)
 def test_deleted_pose_reference_never_rebinds_to_its_former_index(self):
  self.c.sequence=[self.pose('A',[2]),self.pose('B',[4])]
  for kind in ('pose','movej'):
   raw=dict(kind=kind,index=0)
   if kind=='movej':raw['to']='pose'
   self.s.action(dict(op='studio_blocks',blocks=[raw]))
   old_id=self.s.blocks[0]['pose_id'];self.edit('pose_move',index=0,target=1)
   self.assertEqual(self.c.sequence[self.s.pose_index(self.s.blocks[0])]['id'],old_id)
   self.edit('pose_delete',index=self.s.pose_index(self.s.blocks[0]))
   with self.assertRaisesRegex(ValueError,'eliminata'):self.program_plan()
   self.assertEqual(self.groups,[])
   self.c.sequence=[self.pose('A',[2]),self.pose('B',[4])]
 def test_preview_execution_and_validation_use_the_same_direct_legs(self):
  self.c.pos=[2,-1,0,0,0,0];self.c.sequence=[self.pose('A',[4,2],[dict(axis=0,delta=80)]),self.pose('B',[1,3])]
  self.s.movej.prepare(dict(source='sequence',return_home=False));plan=copy.deepcopy(self.s.movej.plan)
  self.play(context=plan['controller_context'])
  moves=[s for s in plan['stages'] if s['kind']=='movej' and s['axes']]
  self.assertEqual([(s['targets'],s['requested'],s['duration']) for s in moves],[(s['targets'],s['requested'],s['duration']) for s in self.groups])
  self.assertEqual(self.c.pos,[1,3,0,0,0,0])
 def test_plan_context_rejects_deletion_before_execution(self):
  self.c.sequence=[self.pose('A',[2]),self.pose('B',[4])]
  context=self.c.group_context();self.edit('pose_delete',index=0)
  with self.assertRaisesRegex(ValueError,'cambiati'):self.play(context=context)
  self.assertEqual(self.groups,[])
 def test_reference_survives_pure_model_and_scene_edits(self):
  self.c.pos=[2,3,0,0,0,0];self.c.write=Mock();before=self.c.pos[:]
  offsets={n:cal['offset'] for n,cal in self.s.calibration.items()}
  offsets['joint_1']+=.01;self.s.apply_home(offsets,self.s.model['source_hash'])
  self.s.action(dict(op='studio_frame_save',name='Altro',xyz=[.1,0,0],rpy=[0,0,0]))
  self.s.action(dict(op='studio_verified',confirmed=True))
  self.s.action(dict(op='studio_tcp',tip=self.s.tip,tool=self.s.tool))
  self.assertTrue(self.c.home);self.assertTrue(self.c.connected);self.assertEqual(self.c.pos,before);self.c.write.assert_not_called()
 def test_edits_refused_during_motion_and_stop_still_requires_reference(self):
  self.c.busy=True
  with self.assertRaises(ValueError):self.s.apply_home({n:c['offset'] for n,c in self.s.calibration.items()},self.s.model['source_hash'])
  with self.assertRaises(ValueError):self.s.action(dict(op='studio_frame_save',name='x',xyz=[0,0,0],rpy=[0,0,0]))
  self.c.busy=False;self.c.action(dict(op='stop'))
  with self.assertRaises(ValueError):self.play()
 def test_home_validates_every_axis_before_any_group(self):
  self.c.pos=[2,3,0,0,0,0];self.c.axes_enabled[1]=False
  with self.assertRaises(ValueError):self.c.action(dict(op='home'))
  self.assertEqual(self.groups,[]);self.assertEqual(self.c.pos,[2,3,0,0,0,0])
 def test_large_transition_is_split_without_hidden_waypoints(self):
  units=direct_units([-360,300,0,0,0,0],[360,-300,0,0,0,0])
  self.assertEqual(len(units),2)
  self.assertEqual([[(e['axis'],e['delta']) for e in u] for u in units],[[(0,360),(1,-300)],[(0,360),(1,-300)]])
 def test_home_intermediate_collision_is_rejected_before_motion(self):
  self.c.pos=[8,0,0,0,0,0]
  self.s.collision_report=lambda q:['test obstacle'] if 2<math.degrees(q['joint_1'])<6 else []
  with self.assertRaisesRegex(ValueError,'Validazione'):self.c.action(dict(op='home'))
  self.assertEqual(self.groups,[])
 def ordered_motion(self, pauses=None):
  motion=dict(mode='ordered',order=[1,0,3,5,2,4],pauses=pauses or [0.]*6)
  self.s.action(dict(op='studio_sequence_motion',motion=motion))
  return motion
 def test_ordered_preview_and_execution_share_waypoints_and_pauses(self):
  self.ordered_motion([.01,.02,4,.03,6,5])
  self.c.sequence=[self.pose('A',[2,3,0,4,0,1])]
  self.c.axis_speeds=[2,3,4,5,6,7]
  self.s.movej.prepare(dict(source='sequence',return_home=True))
  plan=copy.deepcopy(self.s.movej.plan)
  self.s.movej.seek(plan['id'],plan['duration']) # J6 has no joint in the five-axis model
  waits=[]
  self.c.wait_sequence_pause=lambda seconds,gen:waits.append((self.c.pos[:],seconds))
  self.play(context=plan['controller_context'],return_home=True)
  moves=[stage for stage in plan['stages'] if stage['kind']=='movej']
  self.assertEqual([stage['axes'] for stage in moves],[[1],[0],[3],[5]]*2)
  self.assertEqual([(stage['targets'],stage['requested'],stage['duration']) for stage in moves],
                   [(group['targets'],group['requested'],group['duration']) for group in self.groups])
  self.assertEqual(waits,[(stage['targets'],stage['duration']) for stage in plan['stages'] if stage['kind']=='wait' and stage['duration']>0])
  self.assertEqual([seconds for _,seconds in waits],[.02,.01,.03]*2)
  self.assertEqual(self.c.pos,[0.]*6)
 def test_ordered_intermediate_collision_blocks_before_first_joint(self):
  self.ordered_motion()
  self.c.sequence=[self.pose('A',[8,8])]
  self.s.collision_report=lambda q:['test obstacle'] if abs(q['joint_1'])<1e-6 and math.degrees(q['joint_2'])>3 else []
  with self.assertRaisesRegex(ValueError,'Interferenza'):self.s.movej.prepare(dict(source='sequence'))
  with self.assertRaisesRegex(ValueError,'Validazione'):self.play()
  self.assertEqual(self.groups,[])
 def test_stop_during_pause_prevents_next_joint(self):
  self.ordered_motion([0,5,0,0,0,0])
  self.c.sequence=[self.pose('A',[2,3])]
  wait=self.c.wait_sequence_pause
  def stop_during_pause(seconds,gen):
   self.c.action(dict(op='stop'))
   wait(seconds,gen)
  self.c.wait_sequence_pause=stop_during_pause
  self.play()
  self.assertEqual([group['targets'] for group in self.groups],[[0,3,0,0,0,0]])
  self.assertFalse(self.c.home)
 def test_setting_changes_expire_confirmation_and_survive_relaunch(self):
  from unittest.mock import patch
  import server
  self.c.sequence=[self.pose('A',[2,3])]
  self.s.movej.prepare(dict(source='sequence'))
  context=self.s.movej.plan['controller_context']
  motion=self.ordered_motion([0,.25,0,0,0,0])
  self.assertIsNone(self.s.movej.plan)
  with self.assertRaisesRegex(ValueError,'cambiati'):self.play(context=context)
  with patch.object(server.Controller,'io',lambda self:None):
   self.assertEqual(server.Controller().sequence_motion,motion)
  invalid=dict(motion,order=[1]*6)
  with self.assertRaisesRegex(ValueError,'una sola volta'):
   self.s.action(dict(op='studio_sequence_motion',motion=invalid))
  self.assertEqual(self.c.sequence_motion,motion)
 def test_ordered_split_waits_only_after_a_joint_finishes(self):
  from server import sequence_units
  motion=self.ordered_motion([0,.3,0,0,0,0])
  stages=sequence_units([0,-360,0,0,0,0],[1,360,0,0,0,0],motion)
  self.assertEqual([(unit[0]['axis'],unit[0]['delta'],pause) for unit,pause in stages],
                   [(1,360,0),(1,360,.3),(0,1,0)])
 def test_old_pose_ids_migrate_once_and_survive_restart(self):
  import json,tempfile,server
  from pathlib import Path
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder,patch.object(server,'DATA',Path(folder)),patch.object(server.Controller,'io',lambda self:None):
   file=Path(folder)/'sequenza.json';legacy=dict(sequence=[self.pose('old',[3])],limits=[[-9,9]]*6);file.write_text(json.dumps(legacy))
   first=server.Controller();key=first.sequence[0]['id'];second=server.Controller()
   self.assertEqual(second.sequence[0]['id'],key)
   self.assertEqual(json.loads(file.read_text())['limits'],legacy['limits'])
   self.assertEqual(json.loads((Path(folder)/'sequenza-prima-id.json').read_text()),legacy)
