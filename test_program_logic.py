# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import threading
import time
import unittest
import program_lang
from test_program import ProgramBase


class LanguageTests(unittest.TestCase):
    def test_expressions_are_evaluated_without_python_access(self):
        tree = program_lang.parse('strato*20 + 5 >= 45 and not fermo')
        self.assertEqual(program_lang.names(tree), {'strato', 'fermo'})
        self.assertTrue(program_lang.evaluate(tree, dict(strato=2, fermo=False)))
        self.assertEqual(program_lang.evaluate(program_lang.parse('7 // 2 + 7 % 2 - -1'), {}), 5)
        self.assertTrue(program_lang.evaluate(program_lang.parse('1 < x <= 3'), dict(x=3)))
        for text in ("__import__('os')", 'x.y', 'x[0]', 'lambda: 1', "'testo'", '(x := 1)', '', 'a +'):
            with self.assertRaises(ValueError): program_lang.parse(text)
        with self.assertRaisesRegex(ValueError, 'divisione'): program_lang.evaluate(program_lang.parse('1/x'), dict(x=0))
        with self.assertRaisesRegex(ValueError, 'sconosciuto'): program_lang.evaluate(program_lang.parse('y'), {})

    def test_structure_is_balanced_and_bounded(self):
        B = lambda kind: dict(kind=kind)
        match = program_lang.structure([B('loop'), B('if'), B('note'), B('else'), B('note'), B('end'), B('end')])
        self.assertEqual((match[0]['end'], match[1]['else'], match[1]['end'], match[3]['end']), (6, 3, 5, 5))
        self.assertEqual(program_lang.depths([B('loop'), B('if'), B('note'), B('else'), B('end'), B('end')]), [0, 1, 2, 1, 1, 0])
        for bad in ([B('loop')], [B('end')], [B('else')], [B('if'), B('else'), B('else'), B('end')], [B('loop')]*9+[B('end')]*9):
            with self.assertRaises(ValueError): program_lang.structure(bad)
        for name in ('strato', 'J_2'): self.assertEqual(program_lang.check_name(name), name)
        for name in ('2x', 'a b', 'and', ''):
            with self.assertRaises(ValueError): program_lang.check_name(name)


class ProgramLogicTests(ProgramBase):
    def setUp(self):
        super().setUp(); self.s.define_sensor('presente', 'digital')

    def blocks(self, blocks):
        self.s.action(dict(op='studio_blocks', blocks=blocks))

    def pick_loop(self, iterations=3):
        """Open first, then for every cycle: above the part; if it is there, take it to the drop point."""
        t = self.t
        return [dict(kind='grip', name='Apri', command='apri'),
                dict(kind='loop', name='Ciclo', times=str(iterations), variable='pezzo'),
                dict(kind='movej', name='Sopra il pezzo', to='target', target=t['Pezzo'], offset=[0, 0, 60]),
                dict(kind='if', name='Se presente', condition='presente == 1'),
                dict(kind='movel', name='Scendi', to='target', target=t['Pezzo']),
                dict(kind='grip', name='Chiudi', command='chiudi'),
                dict(kind='movel', name='Risali', to='target', target=t['Pezzo'], offset=[0, 0, 60]),
                dict(kind='movej', name='Sopra il deposito', to='target', target=t['Deposito'], offset=[0, 0, 60]),
                dict(kind='grip', name='Apri', command='apri'),
                dict(kind='else', name='Altrimenti'),
                dict(kind='note', name='Pezzo assente'),
                dict(kind='end', name='Fine se'),
                dict(kind='end', name='Fine ciclo')]

    def test_variables_and_nested_loops_stack_parts_in_layers(self):
        t = self.t
        self.blocks([dict(kind='set', name='Passo', variable='passo', value='20'),
                     dict(kind='loop', name='Strati', times='2', variable='strato'),
                     dict(kind='loop', name='Ripeti', times='3'),
                     dict(kind='note', name='Conta'),
                     dict(kind='end', name='Fine'),
                     dict(kind='movel', name='Appoggia', to='target', target=t['Deposito'], offset=[0, 0, 0], offset_expr=['', '', '40 - strato*passo']),
                     dict(kind='end', name='Fine strati')])
        self.c.connected = False
        self.s.edit_scene(dict(op='studio_target_save', id=t['Deposito'], name='Deposito', frame_id=self.s.work_frames[0]['id'], xyz=[.25, -.06, .06], rpy=[3.141592653589793, 0, 0]))
        self.c.pos = [-19.34, 5.64, 98.75, 75.61, 0., 0.]  # tool down at (250, 0, 100) mm
        self.c.connected = True
        plan = self.program_plan(); program = plan['program']
        self.assertEqual(sum(s['kind'] == 'note' for s in plan['stages']), 6)
        heights = [line['length_mm'] for line in program['lines']]
        self.assertEqual(len(heights), 2); self.assertEqual(program['branches'], 1); self.assertEqual(program['decisions'], [])
        end = self.tip(); self.assertAlmostEqual(end[2], .1, places=3)  # nothing moved while planning
        from robot_model import tcp
        last = {n: __import__('math').radians(v) for n, v in zip(['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5'], plan['targets'])}
        last['__gripper'] = 0; self.assertAlmostEqual(tcp(self.s.model, last, self.s.calibration, self.s.tip, self.s.tool)[2], .06+.04-.02, places=3)
        bad = [dict(kind='set', name='x', variable='x', value='presente'), dict(kind='movej', name='H', to='home')]
        self.blocks(bad)
        with self.assertRaisesRegex(ValueError, 'sensori .*presente.* solo nelle condizioni'): self.program_plan()
        self.blocks([dict(kind='loop', name='L', times='y'), dict(kind='movej', name='H', to='home'), dict(kind='end', name='F')])
        with self.assertRaisesRegex(ValueError, 'variabile non definita: y'): self.program_plan()
        self.blocks([dict(kind='loop', name='L', times='2.5'), dict(kind='movej', name='H', to='home'), dict(kind='end', name='F')])
        with self.assertRaisesRegex(ValueError, 'intero'): self.program_plan()
        with self.assertRaisesRegex(ValueError, 'Fine'): self.blocks([dict(kind='loop', name='L', times='2'), dict(kind='movej', name='H', to='home')])

    def test_every_sensor_branch_is_planned_and_merged(self):
        self.blocks(self.pick_loop(3)); plan = self.program_plan(); program = plan['program']
        self.assertEqual(program['branches'], 7)  # root + two outcomes per cycle, merged after each cycle
        self.assertEqual(program['decisions'], [dict(block_index=3, condition='presente == 1', preview=False, occurrences=3)])
        self.assertFalse(any(s['kind'] == 'grip' and s['command'] == 'chiudi' for s in plan['stages']))
        shown = self.s.movej.plan['id']
        self.s.action(dict(op='studio_program_plan', scenario={'3': True})); plan = self.s.movej.plan
        self.assertNotEqual(plan['id'], shown); self.assertEqual(plan['program']['decisions'][0]['preview'], True)
        self.assertEqual(sum(s['kind'] == 'grip' and s['command'] == 'chiudi' for s in plan['stages']), 3)
        self.assertGreater(plan['program']['checked_samples'], plan['sample_count'])
        self.s.action(dict(op='studio_validate', source='program')); self.assertTrue(self.s.validation['ok'])
        self.assertEqual(self.s.movej.plan['program']['decisions'][0]['preview'], True)  # validation keeps the chosen branch
        self.assertTrue(any('7 rami' in n for n in self.s.validation['notes']))

    def test_a_problem_in_a_branch_not_shown_is_still_found(self):
        blocks = self.pick_loop(1); blocks[4] = dict(blocks[4], offset=[0, 0, -30])  # MoveL into the table, only if present
        self.blocks(blocks)
        with self.assertRaisesRegex(ValueError, r'Blocco 5 · Scendi · tratto \d+/\d+ \(ramo: Se al blocco 4 vero\): interferenza'): self.program_plan()
        self.assertEqual(self.s.movej.problem['block'], 4)

    def test_branches_that_never_merge_are_bounded(self):
        # Every reading changes a variable differently: the states never coincide, 2^10 paths.
        self.blocks([dict(kind='set', name='n', variable='n', value='0'), dict(kind='loop', name='L', times='10'),
                     dict(kind='if', name='S', condition='presente'), dict(kind='set', name='1', variable='n', value='n*2 + 1'),
                     dict(kind='else', name='A'), dict(kind='set', name='0', variable='n', value='n*2'),
                     dict(kind='end', name='F'), dict(kind='end', name='F'), dict(kind='movej', name='H', to='home')])
        with self.assertRaisesRegex(ValueError, 'oltre 128 rami'): self.program_plan()

    def feed(self, value, stop):
        """A sensor adapter: fresh, non-simulated readings every 50 ms."""
        while not stop.is_set(): self.s.sensor_value('presente', value(), source='adattatore'); time.sleep(.05)

    def run_with_sensor(self, value, step=False):
        stop = threading.Event(); worker = threading.Thread(target=self.feed, args=(value, stop), daemon=True); worker.start()
        try:
            plan = self.program_plan(); self.start(plan); self.wait(timeout=30)
        finally: stop.set(); worker.join()
        return plan

    def verified_robot(self):
        self.robot(); self.c.connected = False; self.s.action(dict(op='studio_verified', confirmed=True)); self.c.connected = True

    def test_execution_follows_the_sensor_through_planned_branches_only(self):
        self.verified_robot(); self.blocks(self.pick_loop(3))
        readings = iter([1, 0, 1]); current = {'v': 1}
        def value():
            return current['v']
        def on_decision(original=self.s.movej.decide):
            def decide(end):
                current['v'] = next(readings); time.sleep(.12); return original(end)
            return decide
        self.s.movej.decide = on_decision()
        plan = self.run_with_sensor(value)
        movej = self.s.movej
        self.assertTrue(movej.exec_done, movej.exec_error)
        self.assertEqual([d['result'] for d in movej.exec_decisions], [True, False, True])
        self.assertEqual(movej.state()['exec_name'], '')  # cleared at the end; set per stage while running
        grips = [line.strip() for line in self.lines if line.strip() in ('apri', 'chiudi')]
        self.assertEqual(grips, ['apri', 'chiudi', 'apri', 'chiudi', 'apri'])
        # Every ~multi line belongs to a planned segment, in the order the decisions selected.
        tree = plan['tree']; segment = tree[0]; expected = []; outcomes = iter([True, False, True])
        while True:
            expected += ['~multi '+' '.join('%.2f %.2f' % (d, v) for d, v in zip(s['deltas'], s['requested']))+'\n'
                         for s in segment['stages'] if s['kind'] == 'movej' and s['axes']]
            if not segment['end']: break
            segment = tree[segment['end']['next'][0 if next(outcomes) else 1]]
        self.assertEqual(self.multi_lines(), expected)

    def test_real_robot_refuses_simulated_or_stale_sensor_values(self):
        self.verified_robot(); self.blocks(self.pick_loop(1)); plan = self.program_plan()
        self.s.sensor_value('presente', 1)  # source 'simulato'
        self.start(plan); self.wait(timeout=30)
        self.assertIn('dato simulato non vale sul robot reale', self.s.movej.exec_error)
        self.assertEqual([line.strip() for line in self.lines if line.strip() in ('apri', 'chiudi')], ['apri'])

    def test_sensor_wait_times_out_or_continues(self):
        self.verified_robot()
        self.blocks([dict(kind='movej', name='A', to='joints', angles=[2, 0, 0, 0, 0, 0]),
                     dict(kind='sensor', name='Attendi pezzo', sensor='presente', expected=1, timeout=.6),
                     dict(kind='movej', name='H', to='home')])
        self.run_with_sensor(lambda: 0)
        self.assertIn('Timeout sensore: presente', self.s.movej.exec_error); self.assertEqual(self.c.pos[0], 2.)
        self.c.action(dict(op='home_set')) if self.c.mode == 'demo' else None
        self.c.pos = [0.]*6; self.c.trail = []; self.c.home = True
        self.run_with_sensor(lambda: 1)
        self.assertTrue(self.s.movej.exec_done, self.s.movej.exec_error); self.assertEqual(self.c.pos, [0.]*6)
