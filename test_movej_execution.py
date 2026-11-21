# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import math
import threading
import time
from unittest.mock import Mock
from test_studio import StudioFixture


class MoveJExecutionBase(StudioFixture):
    """Connected Anteprima with a simulated Mega serial protocol; helpers only, no tests."""

    def setUp(self):
        super().setUp(); c = self.c
        c.action(dict(op='connect', mode='demo')); c.action(dict(op='home_set'))
        c.limits = [[-180., 180.]]*6; c.axis_speeds = [20.]*6; c.max_speed = 20.
        self.lines = []; self.answer = True
        c.write = Mock(side_effect=self.firmware)

    def firmware(self, line):
        """Simulated Mega: acknowledge and complete each ~multi line, record everything."""
        self.lines.append(line)
        if line.startswith('~multi') and self.answer and self.c.mode == 'robot':
            def reply():
                time.sleep(.05); self.c.receive('MULTI ACK'); time.sleep(.05); self.c.receive('MULTI DONE: ok')
            threading.Thread(target=reply, daemon=True).start()

    def robot(self):
        c = self.c; c.mode = 'robot'; c.connected = True; c.identified = True; c.speed_confirmed = True
        c.multi_axis = True; c.home = True; c.firmware = 'DOC REGIA 4'; c.speed = 20.

    def plan(self, **request):
        request.setdefault('source', 'joints'); request.setdefault('targets', [2, -2, 0, 0, 0, 0])
        self.s.action(dict(op='studio_movej_plan', **request)); return self.s.movej.plan

    def execute(self, plan):
        self.s.action(dict(op='studio_movej_execute', id=plan['id'], confirmed=True))

    def wait(self, condition=None, timeout=30):  # whole programs with grip pauses: slow CI runners need margin
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            if (condition() if condition else not (self.c.busy or self.s.movej.executing)): return
            time.sleep(.01)
        self.fail('timeout')

    def multi_lines(self): return [line for line in self.lines if line.startswith('~multi')]


class MoveJExecutionTests(MoveJExecutionBase):
    """Shared MoveJ execution, in Anteprima and against a simulated Mega serial protocol."""

    def test_executes_the_previewed_plan_and_home_returns_along_it(self):
        plan = self.plan(); self.assertEqual(self.c.pos, [0]*6)
        with self.assertRaisesRegex(ValueError, 'Conferma'): self.s.action(dict(op='studio_movej_execute', id=plan['id']))
        with self.assertRaisesRegex(ValueError, 'scaduto'): self.s.action(dict(op='studio_movej_execute', id='other', confirmed=True))
        self.execute(plan); self.wait()
        movej = self.s.movej.state()
        self.assertTrue(movej['exec_done']); self.assertFalse(movej['exec_error']); self.assertFalse(movej['valid'])
        self.assertEqual(self.c.pos, [2, -2, 0, 0, 0, 0]); stage = plan['stages'][0]
        expected = '~multi '+' '.join('%.2f %.2f' % (d, v) for d, v in zip(stage['deltas'], stage['requested']))+'\n'
        self.assertEqual(self.multi_lines(), [expected])  # exactly the previewed group, one line
        groups = {step['group'] for step in self.c.trail}; self.assertEqual(len(groups), 1)
        self.assertEqual(sorted((s['axis'], s['delta']) for s in self.c.trail), [(0, 2.), (1, -2.)])
        with self.assertRaisesRegex(ValueError, 'scaduto'): self.execute(plan)  # executed plans never rerun
        self.c.action(dict(op='home')); self.wait(); self.assertEqual(self.c.pos, [0]*6); self.assertEqual(self.c.trail, [])

    def test_stale_plan_limits_and_disabled_axes_are_refused_before_any_command(self):
        plan = self.plan(); self.c.axis_speeds[0] = 10
        with self.assertRaisesRegex(ValueError, 'scaduto'): self.execute(plan)
        self.c.axis_speeds[0] = 20; plan = self.plan(); self.c.limits[1] = [-1., 1.]
        with self.assertRaisesRegex(ValueError, 'scaduto'): self.execute(plan)
        with self.assertRaises(ValueError): self.plan()
        self.c.limits[1] = [-180., 180.]; self.c.axes_enabled[0] = False
        with self.assertRaises(ValueError): self.plan()
        self.c.axes_enabled[0] = True; self.c.home = False; plan = self.plan()
        with self.assertRaisesRegex(ValueError, 'home'): self.execute(plan)
        self.assertEqual(self.multi_lines(), []); self.assertFalse(self.s.movej.executing)

    def test_stop_between_and_during_stages_has_no_automatic_resume(self):
        plan = self.plan(return_to_start=True); self.assertEqual(len(plan['stages']), 2)
        self.execute(plan); self.wait(lambda: self.c.motion is not None)
        self.c.action(dict(op='stop')); self.wait()
        movej = self.s.movej.state()
        self.assertIn('Interrotto', movej['exec_error']); self.assertFalse(movej['exec_done'])
        self.assertFalse(self.c.home); self.assertEqual(self.c.pos, [0]*6); self.assertEqual(len(self.multi_lines()), 1)
        time.sleep(.3); self.assertEqual(len(self.multi_lines()), 1)
        with self.assertRaisesRegex(ValueError, 'home'): self.execute(plan)

    def test_pause_holds_before_the_next_stage(self):
        plan = self.plan(); self.c.paused = True; self.execute(plan); time.sleep(.3)
        self.assertEqual(self.multi_lines(), []); self.assertEqual(self.s.movej.exec_stage, -1)
        self.c.paused = False; self.wait(); self.assertTrue(self.s.movej.exec_done)

    def test_robot_protocol_waits_for_ack_and_done_for_every_group(self):
        self.robot(); plan = self.plan(source='joints', targets=[3, 0, -1, 0, 0, 0], return_to_start=True)
        self.execute(plan); self.wait()
        self.assertTrue(self.s.movej.exec_done, self.s.movej.exec_error); self.assertEqual(len(self.multi_lines()), 2)
        self.assertEqual(self.c.pos, [0]*6); self.assertTrue(self.c.home)
        self.assertTrue(self.multi_lines()[1].startswith('~multi -3.00'))

    def test_lost_usb_or_firmware_error_interrupts_execution(self):
        self.robot(); self.answer = False; plan = self.plan(); self.execute(plan)
        self.wait(lambda: self.multi_lines()); time.sleep(.1)
        self.assertTrue(self.c.busy)  # still waiting for MULTI DONE, nothing assumed
        self.c.halt('USB scollegata')  # what Controller.io does on a read error
        self.wait(); self.assertIn('!', self.lines); self.assertFalse(self.c.home); self.assertEqual(self.c.pos, [0]*6)
        self.assertIn('Interrotto', self.s.movej.exec_error)
        self.c.home = True; self.c.error = ''; plan = self.plan(); self.execute(plan)
        self.wait(lambda: len(self.multi_lines()) == 2); self.c.receive('ERROR limit'); self.wait()
        self.assertFalse(self.c.home); self.assertEqual(self.c.pos, [0]*6); self.assertTrue(self.s.movej.exec_error)

    def test_robot_requires_verified_studio_mapping_and_real_poses(self):
        self.robot(); self.s.preview['joint_1'] = math.radians(2); self.s.follow = False
        with self.assertRaisesRegex(ValueError, 'corrispondenza fisica'): self.s.action(dict(op='studio_execute', confirmed=True))
        self.c.sequence = [dict(name='A', pos=[2, 0, 0, 0, 0, 0], path=[], dwell=0, grip='non comandata', mode='demo', enabled=True)]
        plan = self.plan(source='pose', index=0)
        with self.assertRaisesRegex(ValueError, 'Anteprima'): self.execute(plan)
        self.assertEqual(self.multi_lines(), [])

    def test_studio_target_uses_the_shared_movej_plan(self):
        self.s.preview['joint_1'] = math.radians(2); self.s.preview['joint_2'] = math.radians(-1); self.s.follow = False
        self.s.action(dict(op='studio_execute', confirmed=True)); self.wait()
        plan = self.s.movej.plan; self.assertEqual(plan['source'], 'studio'); self.assertTrue(self.s.movej.exec_done)
        self.assertEqual(self.c.pos[:2], [2, -1]); self.assertEqual(len(self.multi_lines()), 1)  # simultaneous, not per joint
        self.s.mapping['joint_3'] = -1; self.s.preview['joint_3'] = .1; self.s.follow = False
        with self.assertRaisesRegex(ValueError, 'non è associato'): self.s.action(dict(op='studio_execute', confirmed=True))

    def test_program_with_gripper_and_dwell_runs_through_the_same_executor(self):
        self.c.sequence = [dict(name='A', pos=[2, 0, 0, 0, 0, 0], path=[], dwell=.2, grip='chiudi', mode='demo', enabled=True)]
        self.s.blocks = self.s.validate_blocks([dict(kind='pose', index=0), dict(kind='note', name='nota'), dict(kind='wait', seconds=.1)])
        plan = self.plan(source='program', return_to_start=True); started = time.monotonic(); self.execute(plan); self.wait()
        self.assertTrue(self.s.movej.exec_done, self.s.movej.exec_error); self.assertEqual(self.c.grip, 'chiudi')
        self.assertIn('chiudi\n', self.lines); self.assertEqual(self.c.pos, [0]*6)
        self.assertGreaterEqual(time.monotonic()-started, 1.5+.2+.1)

    def test_completed_stationary_plan_is_one_use_and_retains_completed_status(self):
        plan = self.plan(targets=[0.]*6)
        def immediate(worker):
            worker(self.c.generation); self.c.playing = False; self.c.busy = False
        self.c.spawn = immediate
        self.execute(plan)
        self.assertTrue(self.s.movej.exec_done)
        self.assertIn('MoveJ eseguito', self.s.status)
        with self.assertRaisesRegex(ValueError, 'scaduto'): self.execute(plan)
        self.assertEqual(self.multi_lines(), [])

    def test_legacy_firmware_keeps_sequential_studio_execution(self):
        self.robot(); self.c.multi_axis = False; self.s.verified = True; self.c.spawn = Mock()
        self.s.preview['joint_1'] = math.radians(2); self.s.follow = False
        self.s.action(dict(op='studio_execute', confirmed=True))
        self.c.spawn.assert_called_once(); self.assertFalse(self.s.movej.executing); self.assertIsNone(self.s.movej.plan)
