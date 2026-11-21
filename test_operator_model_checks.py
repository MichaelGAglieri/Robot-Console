# SPDX-License-Identifier: GPL-3.0-only
"""Session-scoped model warnings never relax controller or Studio motion checks."""
from test_program import ProgramBase
from unittest.mock import Mock
from validation import validate

class OperatorModelChecks(ProgramBase):
 def setUp(self):
  super().setUp();self.s.collision_report=lambda _:['link_3 / link_5'];self.c.pos=[3.,0,0,0,0,0]
  self.c.follow_position=Mock(side_effect=lambda q,g:setattr(self.c,'pos',list(q)))
 def warnings(self):self.s.action(dict(op='studio_operator_collisions',enabled=False,confirmed=True))
 def pose(self):
  return dict(name='A',mode='demo',pos=[2.,0,0,0,0,0],path=[],enabled=True,dwell=0.,grip='non comandata')
 def test_default_home_is_blocked(self):
  self.assertTrue(self.c.operator_collision_checks)
  with self.assertRaisesRegex(ValueError,'Interferenza MoveJ'):self.s.movej.prepare(dict(source='home'))
  with self.assertRaisesRegex(ValueError,'interferenza'):self.c.action(dict(op='home'))
  self.c.follow_position.assert_not_called()
 def test_disable_needs_confirmation_and_keeps_reference(self):
  before=self.c.group_context()
  with self.assertRaisesRegex(ValueError,'Conferma esplicita'):self.s.action(dict(op='studio_operator_collisions',enabled=False))
  self.assertTrue(self.c.operator_collision_checks);self.warnings()
  self.assertFalse(self.c.operator_collision_checks);self.assertTrue(self.c.home);self.assertEqual(self.c.pos[0],3)
  self.assertNotEqual(before,self.c.group_context());self.c.write.assert_not_called()
 def test_home_plan_and_execution_keep_warnings_visible(self):
  self.warnings();self.s.movej.prepare(dict(source='home'));p=self.s.movej.plan
  self.assertIn('link_3 / link_5',p['model_warnings'][0]);self.c.action(dict(op='home',context=p['controller_context']));self.wait()
  self.assertEqual(self.c.pos,[0.]*6);self.assertTrue(self.c.home)
  self.assertTrue(any('SOLO AVVISI' in e for e in self.c.events))
 def test_sequence_remains_at_last_pose(self):
  self.warnings();self.c.sequence=[self.pose()];self.s.movej.prepare(dict(source='sequence'))
  self.c.action(dict(op='play',context=self.s.movej.plan['controller_context']));self.wait()
  self.assertEqual(self.c.pos,[2.,0,0,0,0,0]);self.assertTrue(self.c.home)
 def test_controller_and_urdf_limits_are_still_blocking(self):
  self.warnings();self.c.limits[0]=[0,1]
  with self.assertRaisesRegex(ValueError,'limiti'):self.s.movej.prepare(dict(source='home'))
  with self.assertRaises(ValueError):self.c.action(dict(op='home'))
  self.c.limits=[[-180,180]]*6
  joint=self.s.independent()[0];self.s.calibration[joint['name']]['offset']=1000
  with self.assertRaisesRegex(ValueError,'URDF'):self.s.movej.prepare(dict(source='home'))
  with self.assertRaisesRegex(ValueError,'URDF'):self.c.action(dict(op='home'))
  self.c.follow_position.assert_not_called()
 def test_studio_movej_movel_and_program_are_not_bypassed(self):
  self.warnings()
  for source in ('joints','studio','pose','program','movel'):
   with self.subTest(source=source):
    self.c.sequence=[self.pose()]
    self.s.action(dict(op='studio_blocks',blocks=[dict(kind='movej',name='target',to='joints',angles=[2,0,0,0,0,0])]))
    self.s.movej.movel_instructions=lambda request,start:[dict(kind='movej',name='sample',target=[2,0,0,0,0,0])]
    with self.assertRaisesRegex(ValueError,'[Ii]nterferenza'):
     self.s.movej.prepare(dict(source=source,index=0,targets=[2,0,0,0,0,0],offline=True))
 def test_busy_refuses_change_and_reconnection_restores_checks(self):
  self.warnings();self.c.busy=True
  with self.assertRaises(ValueError):self.s.action(dict(op='studio_operator_collisions',enabled=True))
  with self.assertRaises(ValueError):self.c.action(dict(op='disconnect'))
  self.assertFalse(self.c.operator_collision_checks);self.c.busy=False
  self.c.action(dict(op='disconnect'));self.c.action(dict(op='connect',mode='demo'))
  self.assertTrue(self.c.operator_collision_checks)
 def test_toggle_cancels_stale_plan_and_keeps_normal_validation_strict(self):
  self.warnings();self.s.movej.prepare(dict(source='home'));p=self.s.movej.plan
  self.s.action(dict(op='studio_operator_collisions',enabled=True))
  self.assertIsNone(self.s.movej.plan);self.assertNotEqual(p['controller_context'],self.c.group_context())
  self.warnings();self.c.sequence=[self.pose()];self.s.action(dict(op='studio_blocks',blocks=[dict(kind='pose',index=0,name='A')]))
  self.assertFalse(validate(self.s,'program',collision_warnings=True)['ok'])
  self.assertFalse(validate(self.s,'sequence')['ok'])
  self.assertTrue(validate(self.s,'sequence',collision_warnings=True)['ok'])
 def test_warning_preflight_still_blocks_disabled_axis(self):
  self.warnings();self.c.axes_enabled[0]=False
  with self.assertRaises(ValueError):self.c.action(dict(op='home'))
  self.c.follow_position.assert_not_called()
