# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import copy
import math
from unittest.mock import Mock, patch
from test_studio import StudioFixture, SIMPLE
from robot_model import parse_urdf
from server import motion_fraction
from movej_preview import build_plan, coordinates, fraction_time


class MoveJTests(StudioFixture):
    def setUp(self):
        super().setUp(); self.c.limits=[[-180.,180.]]*6
        self.c.spawn=Mock(); self.c.move_group=Mock()

    def prepare(self, target=None, **options):
        request=dict(op='studio_movej_plan', source='joints', targets=target or [5,10,0,0,0,0]); request.update(options)
        self.s.action(request); return self.s.movej.plan

    def assert_no_motion(self):
        self.c.write.assert_not_called(); self.c.spawn.assert_not_called(); self.c.move_group.assert_not_called()

    def simple_model(self):
        self.s.model=parse_urdf(SIMPLE); self.s.raw=SIMPLE.decode(); self.s.reset_joints(True)
        self.s.tip='tip'; self.s.tool=[0,0,0]

    def test_same_group_profile_without_mutating_commanded_positions(self):
        before=copy.deepcopy(self.c.pos); expected=self.c.group_plan([5,10,0,0,0,0])
        plan=self.prepare(); stage=plan['stages'][0]
        self.assertEqual(stage['duration'],expected[5]); self.assertEqual(stage['requested'],expected[3])
        self.assertEqual(stage['effective'],expected[4]); self.assertEqual(self.c.pos,before)
        later=self.c.group_plan([5,-5,0,0,0,0],starts=[10,20,0,0,0,0])
        self.assertEqual(later[1],[15,15,0,0,0,0]); self.assertEqual(self.c.pos,before); self.assert_no_motion()

    def test_individual_speeds_and_pulse_budget_respected(self):
        self.c.axis_speeds=[1,20,5,5,5,5]; plan=self.prepare(); move=plan['stages'][0]
        self.assertLessEqual(move['peaks'][0],1); self.assertLessEqual(move['peaks'][1],20)
        pulse_rate=sum(abs(move['deltas'][i])*move['path_speed']*self.c.pulses_per_rev[i]/360 for i in move['axes'])
        self.assertLessEqual(pulse_rate,2001); self.assert_no_motion()

    def test_timing_inverse_and_normalized_joint_progress(self):
        plan=self.prepare(); stage=plan['stages'][0]
        for fraction in [0,.01,.25,.5,.75,.99,1]:
            stamp=fraction_time(fraction,stage['path_speed'],stage['path_acceleration'],stage['duration'])
            actual=motion_fraction(1,stage['path_speed'],stamp,stage['path_acceleration'])
            self.assertAlmostEqual(actual,fraction,places=8)
        self.s.movej.seek(plan['id'],plan['duration']/2)
        self.assertAlmostEqual(self.s.preview['joint_1'],math.radians(2.5)); self.assertAlmostEqual(self.s.preview['joint_2'],math.radians(5))
        self.assertEqual(self.c.pos,[0]*6); self.assert_no_motion()

    def test_tcp_path_curves_and_samples_do_not_exceed_one_degree(self):
        self.simple_model(); plan=self.prepare([90,0,0,0,0,0]); samples=plan['samples']
        middle=min(samples,key=lambda sample:abs(sample['q'][0]-45))
        self.assertAlmostEqual(middle['tcp'][0],math.sqrt(.5),places=8)
        self.assertAlmostEqual(middle['tcp'][1],math.sqrt(.5),places=8)
        self.assertGreater(abs(middle['tcp'][0]-.5),.2)
        self.assertTrue(all(max(abs(a-b) for a,b in zip(left['q'],right['q']))<=1.000001 for left,right in zip(samples,samples[1:])))

    def test_detect_intermediate_collision_before_any_preview_motion(self):
        self.simple_model(); self.s.obstacles=[dict(name='middle',center=[math.sqrt(.5),math.sqrt(.5),0],size=[.02]*3)]
        before=self.s.preview.copy()
        self.assertFalse(self.s.collision_report({'yaw':0})); self.assertFalse(self.s.collision_report({'yaw':math.pi/2}))
        with self.assertRaisesRegex(ValueError,'Interferenza MoveJ'): self.prepare([90,0,0,0,0,0])
        self.assertEqual(self.s.preview,before); self.assertIsNone(self.s.movej.plan); self.assert_no_motion()

    def test_included_return_is_planned_and_checked(self):
        plan=self.prepare(return_to_start=True); self.assertEqual(plan['targets'],[0]*6)
        self.assertEqual(len(plan['stages']),2); self.assertGreater(plan['duration'],plan['stages'][0]['duration'])
        self.s.movej.seek(plan['id'],plan['duration']); self.assertAlmostEqual(self.s.preview['joint_1'],0.)
        self.assert_no_motion()

    def test_planning_is_pure_in_any_mode_but_needs_an_idle_controller(self):
        for field,value in [('busy',True),('playing',True),('firmware_busy',True)]:
            old=getattr(self.c,field); setattr(self.c,field,value)
            with self.assertRaises(ValueError): self.prepare()
            setattr(self.c,field,old)
        # Planning with the robot connected sends nothing; execution is a separate, confirmed step.
        self.c.mode='robot'; self.c.fd=123; self.c.multi_axis=True; plan=self.prepare(); self.assertTrue(plan['preview_only'])
        self.c.mode='demo'; self.c.fd=None; self.assert_no_motion()

    def test_disabled_limit_urdf_unmapped_and_duplicate_mapping_rejected(self):
        self.c.axes_enabled[0]=False
        with self.assertRaises(ValueError): self.prepare()
        self.c.axes_enabled[0]=True; self.c.limits[1]=[-1,1]
        with self.assertRaises(ValueError): self.prepare()
        self.c.limits[1]=[-180,180]; self.s.calibration['joint_1']['offset']=4
        with self.assertRaisesRegex(ValueError,'URDF'): self.prepare()
        self.s.calibration['joint_1']['offset']=0; self.s.mapping['joint_2']=0
        with self.assertRaisesRegex(ValueError,'duplicato'): self.prepare()
        self.simple_model()
        with self.assertRaisesRegex(ValueError,'non associato'): self.prepare([0,5,0,0,0,0])
        self.assert_no_motion()

    def test_stale_speed_plan_and_wrong_id_do_not_start_or_seek(self):
        plan=self.prepare(); self.c.axis_speeds[0]=2
        with self.assertRaises(ValueError): self.s.movej.play(plan['id'])
        self.s.movej.tick(); self.c.axis_speeds[0]=5
        with self.assertRaises(ValueError): self.s.movej.play(plan['id'])
        self.assertFalse(self.s.movej.running)
        fresh=self.prepare()
        with self.assertRaises(ValueError): self.s.movej.seek('wrong',0)
        self.assertEqual(self.s.movej.elapsed,0); self.assert_no_motion()

    def test_animation_stop_and_global_stop_generation(self):
        plan=self.prepare(); self.c.home=True
        # Changing HOME after planning requires a fresh plan, too.
        plan=self.prepare(); old=copy.deepcopy((self.c.pos,self.c.home,self.c.trail,self.c.grip))
        with patch('movej_studio.time.monotonic',return_value=100): self.s.movej.play(plan['id'])
        with patch('movej_studio.time.monotonic',return_value=100+plan['duration']/2): self.s.movej.stop()
        self.assertFalse(self.s.movej.running); self.assertGreater(self.s.movej.elapsed,0)
        self.assertEqual((self.c.pos,self.c.home,self.c.trail,self.c.grip),old)
        self.c.generation+=1; self.s.movej.tick(); self.assertTrue(self.s.movej.error)
        self.assert_no_motion()

    def test_pose_and_program_share_movej_with_gripper_and_dwell(self):
        self.c.sequence=[dict(name='A',pos=[5,10,0,0,0,0],path=[],dwell=.4,grip='apri',mode='robot',enabled=True)]
        snapshot=copy.deepcopy(self.c.sequence)
        pose=self.prepare(source='pose',index=0)
        self.s.movej.seek(pose['id'],pose['duration']); self.assertEqual(self.s.movej.grip,'apri')
        self.assertEqual(self.c.grip,'non comandata')
        self.s.blocks=self.s.validate_blocks([dict(kind='pose',index=0),dict(kind='wait',seconds=2)])
        program=self.prepare(source='program')
        self.assertEqual(program['stages'][0]['duration'],pose['stages'][0]['duration'])
        self.assertAlmostEqual(program['duration'],pose['duration']+2)
        self.assertEqual(program['stages'][0]['block_index'],0)
        self.assertEqual(self.c.sequence,snapshot); self.assert_no_motion()

    def test_program_repeat_exclusion_and_unknown_wait_not_guessed(self):
        self.c.sequence=[dict(name='excluded',pos=[90]*6,dwell=0,enabled=False),dict(name='B',pos=[5,0,0,0,0,0],dwell=0)]
        self.s.blocks=self.s.validate_blocks([dict(kind='pose',index=0),dict(kind='pose',index=1),dict(kind='repeat',start=0,count=2)])
        plan=self.prepare(source='program'); self.assertEqual([s['name'] for s in plan['stages'] if s['kind']=='movej'],['B','B'])
        self.s.blocks=self.s.validate_blocks([dict(kind='sensor',sensor='proximity',expected=1,timeout=2)])
        with self.assertRaisesRegex(ValueError,'sensore'): self.prepare(source='program')
        self.assert_no_motion()

    def test_studio_uses_the_same_targets_and_manual_edits_clear_plan(self):
        self.s.preview['joint_1']=math.radians(5); self.s.follow=False
        plan=self.prepare(source='studio'); self.assertEqual(plan['targets'],[5,0,0,0,0,0])
        self.s.action(dict(op='studio_preview',joint='joint_1',value=.1)); self.assertIsNone(self.s.movej.plan)
        self.assert_no_motion()

    def test_nonfinite_input_and_bounded_sampling_rejected(self):
        for values in ([True]*6,[float('nan')]*6,[1]*5,[361]*6):
            with self.assertRaises(ValueError): coordinates(values)
        instructions=[dict(kind='movej',name='long',target=[180 if i%2 else -180,0,0,0,0,0]) for i in range(30)]
        with self.assertRaisesRegex(ValueError,'4096'): build_plan([0]*6,instructions,lambda d,q:self.c.group_plan(d,starts=q),self.s.movej.evaluate,'test')
        self.assert_no_motion()
