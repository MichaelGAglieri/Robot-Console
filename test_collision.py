# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import json
import math
from unittest.mock import Mock
import collision
from robot_model import parse_urdf
from test_studio import StudioFixture, SIMPLE


def doc(*degrees, grip=0.):
    q = {'joint_%d' % (i+1): math.radians(v) for i, v in enumerate(degrees)}; q['__gripper'] = grip; return q


class GeometryTests(StudioFixture):
    def setUp(self):
        super().setUp(); self.s.load_reference(); self.g = self.s.geometry()

    def test_capsules_fit_every_mesh_link_and_reference_pose_is_clear(self):
        names = {b['name'] for b in self.g.bodies}
        for link in ('base_link', 'link_1', 'link_2', 'link_3', 'link_4', 'link_5', 'lab_finger_1'): self.assertIn(link, names)
        arm = [b for b in self.g.bodies if b['name'] == 'link_3']; ends = [p for b in arm for p in (b['a'], b['b'])]
        self.assertGreater(len(arm), 1)  # sliced, so joint housings do not inflate the tube
        self.assertGreater(max(math.dist(x, y) for x in ends for y in ends)+2*min(b['r'] for b in arm), .2)
        self.assertLess(max(b['r'] for b in arm), .07)
        for pose in (doc(0, 0, 0, 0, 0), doc(-19.3, 5.6, 98.7, 75.6, 0), doc(30, 20, 60, 40, 90, grip=1)):
            self.assertEqual(self.g.check(pose, None, [], True, .01), [])

    def test_table_self_collision_and_obstacles_are_detected(self):
        hits = self.g.check(doc(0, 60, 90, 30, 0), None, [], True, .01)
        self.assertTrue(any(h['kind'] == 'floor' and h['a'] == 'link_5' for h in hits))
        self.assertFalse([h for h in self.g.check(doc(0, 60, 90, 30, 0), None, [], False, .01) if h['kind'] == 'floor'])
        folded = self.g.check(doc(0, 0, 150, 150, 0), None, [], True, .01)
        self.assertTrue(any(h['kind'] == 'self' and {h['a'], h['b']} == {'link_2', 'link_5'} for h in folded))
        box = dict(name='Pezzo', center=[.25, 0, .07], size=[.05, .05, .02])
        self.assertTrue(any(h['b'] == 'Pezzo' for h in self.g.check(doc(-19.3, 5.6, 98.7, 75.6, 0), None, [box], True, .01)))

    def test_single_joint_sweeps_stop_where_the_arm_meets_itself_or_the_table(self):
        def first_hit(joint, sign):
            for angle in range(0, 181):
                values = [0]*5; values[joint-1] = sign*angle
                if self.g.check(doc(*values), None, [], True, .01): return angle
            return None
        self.assertTrue(80 <= first_hit(2, 1) <= 95)   # upper arm horizontal near the table
        self.assertTrue(125 <= first_hit(3, 1) <= 145)  # gripper reaches the table
        self.assertTrue(90 <= first_hit(4, 1) <= 110)   # gripper folds onto the forearm
        self.assertIsNone(first_hit(1, 1)); self.assertIsNone(first_hit(1, -1))
        self.assertTrue((first_hit(5, 1) or 181) >= 120)  # gripper spin: conservative capsule near the margin

    def test_segment_distance_and_capsule_fit(self):
        self.assertAlmostEqual(collision.segment_distance([0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]), 1)
        self.assertAlmostEqual(collision.segment_distance([0, 0, 0], [1, 0, 0], [.5, -1, 1], [.5, 1, 1]), 1)
        self.assertAlmostEqual(collision.segment_distance([0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]), 1)
        cap = collision.fit_capsule([[x, y, z] for x in (-.01, .01) for y in (-.01, .01) for z in [i/10 for i in range(11)]])
        self.assertAlmostEqual(abs(cap['a'][2]-cap['b'][2])+2*cap['r'], 1, delta=.03); self.assertAlmostEqual(cap['r'], math.sqrt(2)*.01, places=3)

    def test_models_without_geometry_keep_the_joint_segment_check(self):
        g = collision.Geometry(parse_urdf(SIMPLE))
        box = dict(name='middle', center=[.5, 0, 0], size=[.02]*3)
        self.assertTrue(g.check({'yaw': 0}, None, [box], False, .0))
        self.assertFalse(g.check({'yaw': math.pi/2}, None, [box], False, .0))


class ValidationTests(StudioFixture):
    def setUp(self):
        super().setUp(); self.s.load_reference(); c = self.c
        c.action(dict(op='connect', mode='demo')); c.action(dict(op='home_set')); c.limits = [[-180., 180.]]*6

    def pose(self, name, angles, grip='non comandata', mode='demo'):
        path = [dict(axis=i, delta=float(v)) for i, v in enumerate(angles) if v]
        return dict(name=name, mode=mode, pos=list(map(float, angles))+[0.]*(6-len(angles)), path=path, grip=grip, dwell=0, enabled=True)

    def test_clean_sequence_passes_and_every_leg_is_sampled(self):
        self.c.sequence = [self.pose('Sopra', [-19.3, 5.6, 98.7, 75.6, 0]), self.pose('Accanto', [10, 5, 90, 80, 0])]
        self.s.action(dict(op='studio_validate', source='sequence')); report = self.s.validation
        self.assertTrue(report['ok'], report['issues']); self.assertEqual(report['poses'], 2)
        self.assertGreaterEqual(report['samples'],130)  # current -> first -> second, simultaneous; no hidden detour

    def test_route_through_the_table_is_located_and_blocks_play(self):
        self.c.sequence = [self.pose('Presa bassa', [0, 60, 90, 30, 0])]
        self.s.action(dict(op='studio_validate', source='sequence')); report = self.s.validation
        self.assertFalse(report['ok']); self.assertTrue(report['issues'][0]['where'].startswith('verso posa 1 · Presa bassa'))
        self.assertIn('interferenza', report['issues'][0]['detail'])
        self.assertTrue(any('piano di lavoro' in i['detail'] for i in report['issues']))
        self.assertFalse(any('ritorno' in i['where'] for i in report['issues']))
        self.c.spawn = Mock()
        with self.assertRaisesRegex(ValueError, 'Validazione'): self.c.action(dict(op='play'))
        self.c.spawn.assert_not_called()
        self.s.action(dict(op='studio_workcell', floor=False))
        self.s.action(dict(op='studio_validate', source='sequence')); self.assertTrue(self.s.validation['ok'], self.s.validation['issues'])

    def test_program_blocks_limits_and_unverified_robot(self):
        self.c.sequence = [self.pose('Piegato', [0, 0, 150, 150, 0])]
        self.s.blocks = self.s.validate_blocks([dict(kind='pose', index=0), dict(kind='sensor', sensor='s', expected=1, timeout=1)])
        self.s.define_sensor('s', 'digital')
        self.s.action(dict(op='studio_validate', source='program')); report = self.s.validation
        self.assertFalse(report['ok']); self.assertIn('blocco 1', report['issues'][0]['where']); self.assertTrue(report['notes'])
        with self.assertRaisesRegex(ValueError, 'Validazione'): self.s.run_program()
        self.c.limits[2] = [-180., 100.]
        self.s.action(dict(op='studio_validate', source='program'))
        self.assertTrue(any('J3 fuori dai limiti' in i['detail'] for i in self.s.validation['issues']))
        # Real robot with a model not declared to match: warn in the log, do not block.
        self.c.limits[2] = [-180., 180.]; self.c.mode = 'robot'; self.c.multi_axis = True; self.s.verified = False
        for pose in self.c.sequence: pose['mode'] = 'robot'
        self.c.spawn = Mock(); self.s.run_program(); self.c.spawn.assert_called_once()
        self.assertTrue(any('Validazione' in e for e in self.c.events))

    def test_workcell_is_saved_and_changes_plans(self):
        self.c.connected = False
        self.s.action(dict(op='studio_workcell', floor=False, margin=25))
        self.assertEqual(self.s.workcell, dict(floor=False, margin=.025))
        saved = json.loads((self.s.folder/'project.json').read_text()); self.assertEqual(saved['workcell'], dict(floor=False, margin=.025))
        with self.assertRaises(ValueError): self.s.action(dict(op='studio_workcell', margin=500))


class GripperValidationTests(StudioFixture):
    def setUp(self):
        super().setUp(); self.c.limits = [[-180., 180.]]*6; self.c.grip = 'chiudi'
        self.c.sequence = [dict(name='A', pos=[5., 0, 0, 0, 0, 0],
                               path=[dict(axis=0, delta=5.)], dwell=0,
                               grip='non comandata', enabled=True, mode='demo')]

    def test_gripper_block_changes_geometry_before_the_following_path(self):
        self.s.blocks = self.s.validate_blocks([dict(kind='grip', command='apri'), dict(kind='pose', index=0)])
        self.s.collision_report = Mock(side_effect=lambda q: ['dita / ostacolo'] if q['__gripper'] == 1 else [])
        self.s.action(dict(op='studio_validate', source='program'))
        self.assertFalse(self.s.validation['ok'])
        self.assertTrue(any('blocco 1' in issue['where'] for issue in self.s.validation['issues']))
        self.assertTrue(any('verso blocco 2' in issue['where'] for issue in self.s.validation['issues']))
        self.c.write.assert_not_called()

    def test_expanded_repeats_keep_gripper_order_and_do_not_invent_pose_actions(self):
        self.s.blocks = self.s.validate_blocks([dict(kind='grip', command='apri'), dict(kind='pose', index=0),
                                               dict(kind='grip', command='chiudi'), dict(kind='repeat', start=0, count=2)])
        self.s.collision_report = Mock(return_value=[])
        self.s.action(dict(op='studio_validate', source='program'))
        states = [call.args[0]['__gripper'] for call in self.s.collision_report.call_args_list]
        self.assertTrue(self.s.validation['ok']); self.assertEqual(self.s.validation['poses'], 2)
        self.assertEqual(states[0], 0); self.assertEqual(states[-1], 0)
        self.assertGreaterEqual(sum(a != b for a, b in zip(states, states[1:])), 4)
        self.c.write.assert_not_called()

    def test_gripper_only_program_is_checked_before_execution(self):
        self.c.action(dict(op='connect', mode='demo')); self.c.action(dict(op='home_set'))
        self.s.blocks = self.s.validate_blocks([dict(kind='grip', command='apri')])
        self.s.collision_report = Mock(side_effect=lambda q: ['dita / ostacolo'] if q['__gripper'] == 1 else [])
        self.c.spawn = Mock(); self.c.write.reset_mock()
        with self.assertRaisesRegex(ValueError, 'Validazione'): self.s.run_program()
        self.c.spawn.assert_not_called(); self.c.write.assert_not_called()
        self.assertEqual(self.s.validation['poses'], 0)

    def test_repeat_sequence_checks_next_cycle_with_last_gripper_state(self):
        self.c.action(dict(op='connect', mode='demo')); self.c.action(dict(op='home_set'))
        self.c.limits = [[-180., 180.]]*6
        self.c.sequence[0]['grip'] = 'apri'
        # Closed fingers clear the outbound leg; open fingers collide only on a later outbound leg.
        seen = {'first_return': False}
        def collision(q):
            angle = math.degrees(q['joint_1'])
            if q['__gripper'] == 1 and abs(angle) < 1e-6: seen['first_return'] = True
            return ['dita / ostacolo'] if seen['first_return'] and q['__gripper'] == 1 and 1 < angle < 4 else []
        self.s.collision_report = Mock(side_effect=collision); self.c.spawn = Mock()
        with self.assertRaisesRegex(ValueError, 'Validazione'):
            self.c.action(dict(op='play', repeat=True, return_home=True))
        self.c.spawn.assert_not_called()
        self.assertTrue(any('ciclo 2' in issue['where'] for issue in self.s.validation['issues']))
