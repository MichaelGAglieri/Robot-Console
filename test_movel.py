# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import math
import time
from pathlib import Path
import ik5
import movel
from robot_model import parse_urdf, tcp
from test_movej_execution import MoveJExecutionBase
from test_studio import StudioFixture, SIMPLE

DOC = Path(__file__).parent/'models/doc5/doc5.urdf'
NAMES = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5']


def chain_and_start(model, point=(.25, 0, .10)):
    chain = ik5.Chain(model, model['tip'], [0, 0, 0], {n: dict(sign=1, offset=0) for n in NAMES}, {n: True for n in NAMES})
    q = dict.fromkeys(NAMES, 0.); q['__gripper'] = 0.
    found, _ = ik5.inverse_kinematics(chain, q, list(point), [0, 0, -1]); return chain, found[0]['positions']


def executed_deviation(chain, waypoints, a, b, step_deg=.05):
    """Independent check: re-sample every joint-linear segment finely."""
    worst = 0.
    for qa, qb in zip(waypoints, waypoints[1:]):
        largest = max(abs(qb[n]-qa[n]) for n in chain.variables); count = max(10, math.ceil(math.degrees(largest)/step_deg))
        for i in range(count+1):
            q = dict(qa)
            for n in chain.variables: q[n] = qa[n]+(qb[n]-qa[n])*i/count
            pose, _, _ = chain.forward(q); worst = max(worst, movel.distance_to_segment([pose[k][3] for k in range(3)], a, b))
    return worst


class LinePlannerTests(StudioFixture):
    def setUp(self):
        super().setUp(); self.model = parse_urdf(DOC.read_bytes()); self.chain, self.q = chain_and_start(self.model)

    def test_executed_segments_stay_within_tolerance_and_keep_orientation(self):
        for target, tolerance in (([.25, .10, .10], .0005), ([.25, 0, .30], .0005), ([.32, -.05, .05], .0002)):
            result = movel.plan_line(self.chain, self.q, target, True, tolerance)
            check = executed_deviation(self.chain, result['waypoints'], result['start'], target)
            self.assertLessEqual(check, tolerance*1.05); self.assertAlmostEqual(result['max_deviation'], check, delta=tolerance*.1)
            self.assertLess(result['end_error'], .00015); self.assertLess(result['axis_error'], math.radians(.05))
            for q in result['waypoints']:  # whole hundredths of a degree, as the controller commands them
                for n in NAMES: self.assertAlmostEqual(math.degrees(q[n])*100, round(math.degrees(q[n])*100), places=6)

    def test_unrepresentable_tolerance_is_rejected_after_angle_rounding(self):
        model = parse_urdf(SIMPLE)
        chain = ik5.Chain(model, 'tip', [0, 0, 0], {'yaw': dict(sign=1, offset=0)}, {'yaw': True})
        # A 1 m link, target at 0.0008 rad: rounding to 0.01 degrees misses by 0.073 mm.
        target = [math.cos(.0008), math.sin(.0008), 0]
        with self.assertRaisesRegex(ValueError, 'tolleranza'):
            movel.plan_line(chain, {'yaw': 0}, target, False, .00005)

    def test_tighter_tolerance_needs_more_segments(self):
        counts = [movel.plan_line(self.chain, self.q, [.25, .10, .10], True, t)['segments'] for t in (.002, .0005, .0001)]
        self.assertLess(counts[0], counts[1]); self.assertLess(counts[1], counts[2])
        with self.assertRaisesRegex(ValueError, 'più di'): movel.plan_line(self.chain, self.q, [.25, .10, .10], True, .0001, max_segments=3)

    def test_unreachable_part_of_the_line_is_located(self):
        with self.assertRaisesRegex(ValueError, r'a \d+\.\d mm dall’inizio'): movel.plan_line(self.chain, self.q, [.70, 0, .10], True, .0005)
        for joint in self.model['joints']:
            if joint['name'] == 'joint_1': joint['lower'], joint['upper'] = -.4, -.30
        chain, q = ik5.Chain(self.model, self.model['tip'], [0, 0, 0], {n: dict(sign=1, offset=0) for n in NAMES}, {n: True for n in NAMES}), self.q
        with self.assertRaisesRegex(ValueError, 'limiti dei giunti.*joint_1'): movel.plan_line(chain, q, [.25, .10, .10], True, .0005)
        with self.assertRaisesRegex(ValueError, 'coincide'): movel.plan_line(self.chain, self.q, movel.column(self.chain.forward(self.q)[0], 3), True, .0005)

    def test_five_axes_report_the_orientation_they_cannot_hold(self):
        tilted, _, _ = self.chain.forward(dict(self.q, joint_4=self.q['joint_4']+.4))
        q = dict(self.q, joint_4=self.q['joint_4']+.4); start = movel.column(tilted, 3)
        result = movel.plan_line(self.chain, q, [start[0], start[1]+.08, start[2]], True, .0005)
        self.assertGreater(result['axis_error'], math.radians(1))  # sideways line with a tilted gripper
        self.assertLessEqual(result['max_deviation'], .0005)
        free = movel.plan_line(self.chain, q, [start[0], start[1]+.08, start[2]], False, .0005); self.assertIsNone(free['axis_error'])


class StudioMoveLTests(MoveJExecutionBase):
    def setUp(self):
        super().setUp(); self.s.load_reference(); self.c.limits = [[-180., 180.]]*6
        self.c.pos = [-19.34, 5.64, 98.75, 75.61, 0., 0.]  # tool down at (250, 0, 100) mm

    def test_movel_plan_preview_and_execution_follow_the_line(self):
        plan = self.plan(source='movel', target=[.25, .08, .10], frame='base', orientation='keep', tolerance=.5)
        info = plan['movel']; self.assertEqual(plan['source'], 'movel'); self.assertLessEqual(info['max_deviation_mm'], .5)
        self.assertEqual(len([s for s in plan['stages'] if s['kind'] == 'movej']), info['segments'])
        self.assertTrue(all(sample['tcp'][2] > .099 and sample['tcp'][2] < .101 for sample in plan['samples']))
        self.assertEqual(self.lines, [])  # planning sends nothing
        self.execute(plan); self.wait()
        self.assertTrue(self.s.movej.exec_done, self.s.movej.exec_error)
        self.assertEqual(len(self.multi_lines()), info['segments'])
        end = tcp(self.s.model, {**{n: math.radians(self.c.pos[i]) for i, n in enumerate(NAMES)}, '__gripper': 0}, self.s.calibration, self.s.tip, self.s.tool)
        self.assertAlmostEqual(end[1], .08, places=3); self.assertAlmostEqual(end[2], .10, places=3)
        measured = self.s.movej.state()['exec_measured']
        self.assertEqual(len(measured), info['segments']); self.assertTrue(all(m['actual'] >= m['planned']*.9 for m in measured))

    def test_movel_in_work_frame_respects_controller_limits_and_robot_checks(self):
        self.c.connected = False  # scene editing requires a disconnected controller
        self.s.edit_scene(dict(op='studio_frame_save', name='Tavolo', xyz=[.25, 0, .10], rpy=[0, 0, math.pi/2])); self.c.connected = True
        frame = self.s.work_frames[0]['id']
        plan = self.plan(source='movel', target=[.05, 0, 0], frame=frame, orientation='keep', tolerance=1)
        self.assertAlmostEqual(plan['movel']['target_mm'][1], 50, places=3)
        self.c.limits[0] = [-20., -19.]
        with self.assertRaisesRegex(ValueError, 'limiti dei giunti'): self.plan(source='movel', target=[.05, 0, 0], frame=frame, tolerance=1)
        self.c.limits[0] = [-180., 180.]; self.robot(); plan = self.plan(source='movel', target=[.05, 0, 0], frame=frame, tolerance=1)
        with self.assertRaisesRegex(ValueError, 'corrispondenza fisica'): self.execute(plan)
        with self.assertRaises(ValueError): self.plan(source='movel', target=[.05, 0, 0], frame='tool')
        self.assertEqual(self.multi_lines(), [])
