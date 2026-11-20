# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import math
import random
from pathlib import Path
from unittest.mock import Mock
import ik5
from robot_model import parse_urdf, tcp
from test_studio import StudioFixture

DOC = Path(__file__).parent/'models/doc5/doc5.urdf'
NAMES = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5']
I4 = [[float(i == k) for k in range(4)] for i in range(4)]


def reference_tcp(q):
    """Independent FK from the EB-15 quotes (D.O.C.Mac doc5_kinematics.py), zero = arm vertical."""
    def rz(a): c, s = math.cos(a), math.sin(a); return [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    def ry(a): c, s = math.cos(a), math.sin(a); return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    def mul(a, b): return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    steps = [(rz, (0, 0, .0308)), (ry, (0, .0408, .043)), (ry, (0, 0, .222)), (ry, (0, -.0008, .221)), (rz, (0, .0428, .040))]
    r = [[float(i == k) for k in range(3)] for i in range(3)]; p = [0., 0., 0.]
    for (rot, offset), angle in zip(steps, q):
        p = [p[i]+sum(r[i][k]*offset[k] for k in range(3)) for i in range(3)]; r = mul(r, rot(angle))
    return [p[i]+r[i][2]*(.0008+.099) for i in range(3)]


class ChainTests(StudioFixture):
    def setUp(self):
        super().setUp(); self.model = parse_urdf(DOC.read_bytes()); random.seed(7)
        self.cal = {n: dict(sign=1, offset=0) for n in NAMES}; self.on = {n: True for n in NAMES}

    def chain(self, cal=None, enabled=None, tool=(0, 0, 0)):
        return ik5.Chain(self.model, self.model['tip'], list(tool), cal or self.cal, enabled or self.on)

    def q(self, values=None):
        q = dict(zip(NAMES, values or [0.]*5)); q['__gripper'] = 0.; return q

    def test_forward_matches_urdf_and_independent_eb15_quotes(self):
        cal = {n: dict(sign=-1 if i % 2 else 1, offset=.1*i) for i, n in enumerate(NAMES)}
        chain = self.chain(cal, tool=(.01, -.02, .03))
        for _ in range(10):
            q = self.q([random.uniform(-1.5, 1.5) for _ in NAMES]); pose, _, _ = chain.forward(q)
            expected = tcp(self.model, q, cal, self.model['tip'], [.01, -.02, .03])
            self.assertLess(max(abs(pose[i][3]-expected[i]) for i in range(3)), 1e-12)
            angles = [q[n] for n in NAMES]; pose, _, _ = self.chain().forward(self.q(angles))
            self.assertLess(max(abs(a-b) for a, b in zip([pose[i][3] for i in range(3)], reference_tcp(angles))), 1e-12)

    def test_jacobian_matches_finite_differences(self):
        chain = self.chain({n: dict(sign=-1, offset=.2) for n in NAMES}, tool=(0, .01, .02))
        q = self.q([.3, -.4, .9, .5, 1.1]); pose, jp, jw = chain.forward(q)
        for c, name in enumerate(NAMES):
            moved = dict(q); moved[name] += 1e-7; other, _, _ = chain.forward(moved)
            for i in range(3):
                self.assertAlmostEqual((other[i][3]-pose[i][3])/1e-7, jp[i][c], places=5)
                self.assertAlmostEqual((other[i][2]-pose[i][2])/1e-7, sum(jw[k][c]*[[0, -pose[2][2], pose[1][2]], [pose[2][2], 0, -pose[0][2]], [-pose[1][2], pose[0][2], 0]][i][k]*-1 for k in range(3)), places=5)

    def test_reachable_poses_round_trip_position_and_axis_with_calibration(self):
        cal = {n: dict(sign=-1 if i in (1, 3) else 1, offset=.05*i) for i, n in enumerate(NAMES)}; chain = self.chain(cal)
        for _ in range(15):
            q = self.q([random.uniform(-1.1, 1.1) for _ in NAMES]); pose, _, _ = chain.forward(q)
            target = [pose[i][3] for i in range(3)]; axis = [pose[i][2] for i in range(3)]
            found, _ = ik5.inverse_kinematics(chain, self.q(), target, axis)
            self.assertTrue(found); best = found[0]
            self.assertLess(best['position_error'], ik5.POSITION_TOL); self.assertLess(best['axis_error'], math.radians(.1))
            check, _, _ = chain.forward(best['positions'])
            self.assertLess(max(abs(check[i][3]-target[i]) for i in range(3)), ik5.POSITION_TOL)
            for name in NAMES:
                lo, hi = chain.limits[name]; self.assertTrue(lo-1e-9 <= best['positions'][name] <= hi+1e-9)

    def test_alternative_configurations_and_continuity(self):
        chain = self.chain(); found, _ = ik5.inverse_kinematics(chain, self.q(), [.25, 0, .10], [0, 0, -1])
        self.assertGreaterEqual(len(found), 2)
        self.assertEqual({r['labels']['reach'] for r in found}, {'front', 'back'})
        # Starting next to the second solution keeps that branch.
        near = dict(found[1]['positions']); near['joint_2'] += .02
        again, _ = ik5.inverse_kinematics(chain, near, [.25, 0, .10], [0, 0, -1])
        self.assertLess(again[0]['change'], math.radians(3)); self.assertEqual(again[0]['labels'], found[1]['labels'])

    def test_out_of_reach_limits_and_locked_joints_are_reported(self):
        chain = self.chain(); found, closest = ik5.inverse_kinematics(chain, self.q(), [.7, 0, .2])
        self.assertFalse(found); reason, distance, reach = ik5.unreachable_reason(chain, self.q(), [.7, 0, .2], closest)
        self.assertEqual(reason, 'reach'); self.assertGreater(distance, reach); self.assertAlmostEqual(reach, .6014, places=3)
        for joint in self.model['joints']:
            if joint['name'] in ('joint_2', 'joint_3'): joint['lower'], joint['upper'] = -.2, .2
        chain = self.chain(); found, closest = ik5.inverse_kinematics(chain, self.q(), [.25, 0, .10])
        self.assertFalse(found); self.assertEqual(ik5.unreachable_reason(chain, self.q(), [.25, 0, .10], closest)[0], 'limits')
        self.model = parse_urdf(DOC.read_bytes()); locked = dict(self.on, joint_1=False)
        chain = self.chain(enabled=locked); q = self.q([.4, 0, 0, 0, 0])
        found, _ = ik5.inverse_kinematics(chain, q, [.25, 0, .10]); self.assertEqual(chain.locked, ['joint_1'])
        self.assertTrue(all(r['positions']['joint_1'] == .4 for r in found))

    def test_five_axes_cannot_tilt_sideways_but_keep_position(self):
        chain = self.chain(); sideways = [0, math.sin(math.radians(40)), -math.cos(math.radians(40))]
        found, _ = ik5.inverse_kinematics(chain, self.q(), [.30, 0, .10], sideways)
        self.assertTrue(found); self.assertLess(found[0]['position_error'], ik5.POSITION_TOL)
        self.assertGreater(found[0]['axis_error'], math.radians(5))

    def test_jog_steps_are_exact_continuous_and_reject_impossible_moves(self):
        chain = self.chain(); found, _ = ik5.inverse_kinematics(chain, self.q(), [.25, 0, .10], [0, 0, -1]); q = found[0]['positions']
        start, _, _ = chain.forward(q)
        for _ in range(8):
            result = ik5.jog(chain, q, I4, [0, .005, 0], [0, 0, 0])
            self.assertLess(result['position_error'], ik5.POSITION_TOL); self.assertLess(result['axis_error'], math.radians(.05))
            self.assertLess(result['change'], math.radians(3)); q = result['positions']
        end, _, _ = chain.forward(q); self.assertAlmostEqual(end[1][3]-start[1][3], .04, places=6)
        result = ik5.jog(chain, q, None, [0, 0, .01], [0, 0, 0]); moved, _, _ = chain.forward(result['positions'])
        self.assertAlmostEqual(moved[2][3]-end[2][3], -.01, places=6)  # tool +Z points down here
        roll = ik5.jog(chain, q, None, [0, 0, 0], [0, 0, math.radians(10)])
        self.assertAlmostEqual(roll['positions']['joint_5']-q['joint_5'], math.radians(10), places=4)
        self.assertLess(max(abs(roll['positions'][n]-q[n]) for n in NAMES[:4]), 1e-6)
        sideways = ik5.jog(chain, q, None, [0, 0, 0], [math.radians(10), 0, 0])
        self.assertGreater(sideways['axis_error'], math.radians(5)); self.assertLess(sideways['position_error'], ik5.POSITION_TOL)
        vertical = ik5.jog(chain, self.q(), I4, [0, 0, .005], [0, 0, 0])
        self.assertGreater(vertical['position_error'], .004); self.assertLess(vertical['sigma'], ik5.SINGULAR)


class StudioCartesianTests(StudioFixture):
    def setUp(self):
        super().setUp(); self.s.load_reference(); self.c.spawn = Mock(); self.c.move_group = Mock()

    def assert_no_motion(self):
        self.c.write.assert_not_called(); self.c.spawn.assert_not_called(); self.c.move_group.assert_not_called()

    def tcp(self):
        return tcp(self.s.model, self.s.current_positions(), self.s.calibration, self.s.tip, self.s.tool)

    def test_point_ik_in_work_frame_and_down_orientation_updates_preview_only(self):
        self.s.edit_scene(dict(op='studio_frame_save', name='Tavolo', xyz=[.2, -.05, .02], rpy=[0, 0, math.pi/2]))
        frame = self.s.work_frames[0]['id']; pos_before = list(self.c.pos)
        self.s.action(dict(op='studio_ik', target=[.05, -.02, .08], frame=frame, orientation='down'))
        report = self.s.cartesian.report; self.assertTrue(report['ok']); self.assertFalse(self.s.follow)
        point = self.tcp(); self.assertAlmostEqual(point[0], .22, places=4); self.assertAlmostEqual(point[1], 0., places=4); self.assertAlmostEqual(point[2], .10, places=4)
        self.assertLess(report['solutions'][0]['axis_error_deg'], .1); self.assertEqual(self.c.pos, pos_before)
        readout = self.s.state()['cartesian']['readout']; table = next(f for f in readout['frames'] if f['id'] == frame)
        self.assertAlmostEqual(table['xyz'][0], 50, places=1); self.assertAlmostEqual(table['axis'][2], -1, places=4)
        self.assert_no_motion()

    def test_legacy_request_target_choice_and_jog(self):
        self.s.action(dict(op='studio_ik', target=[.25, .05, .15])); self.assertTrue(self.s.cartesian.report['ok'])
        self.s.edit_scene(dict(op='studio_target_save', name='Presa', frame_id='base', xyz=[.24, .0, .06], rpy=[math.pi, 0, .3]))
        target = self.s.cartesian_targets[0]['id']
        self.s.action(dict(op='studio_ik_target', id=target, orientation='full')); report = self.s.cartesian.report
        self.assertTrue(report['ok']); self.assertEqual(self.s.selected_target, target)
        self.assertLess(report['solutions'][0]['roll_error_deg'], .2); self.assertGreaterEqual(len(report['solutions']), 2)
        self.s.action(dict(op='studio_ik_choose', index=1)); self.assertEqual(self.s.cartesian.report['chosen'], 1)
        self.assertAlmostEqual(self.tcp()[2], .06, places=4)
        before = self.tcp(); self.s.action(dict(op='studio_jog', frame='base', translation=[5, 0, 0], rotation=[0, 0, 0], keep_axis=True))
        self.assertTrue(self.s.cartesian.report['ok']); self.assertAlmostEqual(self.tcp()[0]-before[0], .005, places=6)
        self.assert_no_motion()

    def test_rejections_leave_preview_unchanged(self):
        self.s.action(dict(op='studio_ik', target=[.25, 0, .10], orientation='down')); before = dict(self.s.preview)
        self.s.action(dict(op='studio_ik', target=[.9, 0, .1])); report = self.s.cartesian.report
        self.assertFalse(report['applied']); self.assertEqual(report['reason'], 'reach'); self.assertEqual(self.s.preview, before)
        self.assertIn('fuori portata', self.s.status)
        self.s.action(dict(op='studio_jog', frame='tool', translation=[0, 0, 0], rotation=[10, 0, 0]))
        self.assertEqual(self.s.cartesian.report['reason'], 'orientation'); self.assertEqual(self.s.preview, before)
        with self.assertRaises(ValueError): self.s.action(dict(op='studio_jog', frame='base', translation=[80, 0, 0]))
        with self.assertRaises(ValueError): self.s.action(dict(op='studio_ik', target=[.2, 0, .1], frame='tool'))
        self.s.action(dict(op='studio_ik', target=[.25, .05, .15]))
        self.s.calibration['joint_2']['offset'] = .01
        with self.assertRaises(ValueError): self.s.action(dict(op='studio_ik_choose', index=0))
        self.assert_no_motion()
