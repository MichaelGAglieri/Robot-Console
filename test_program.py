# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import json
import math
import time
from robot_model import tcp
from studio import Studio
from test_movej_execution import MoveJExecutionBase

NAMES = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5']


class ProgramBase(MoveJExecutionBase):
    """DOC model, a table frame and two tool-down targets: a piece and a drop point."""

    def setUp(self):
        super().setUp(); s, c = self.s, self.c; s.load_reference(); c.connected = False
        s.edit_scene(dict(op='studio_frame_save', name='Tavolo', xyz=[0, 0, 0], rpy=[0, 0, 0]))
        frame = s.work_frames[0]['id']
        for name, xyz in (('Pezzo', [.25, -.06, .04]), ('Deposito', [.22, .10, .04])):
            s.edit_scene(dict(op='studio_target_save', name=name, frame_id=frame, xyz=xyz, rpy=[math.pi, 0, 0]))
        c.connected = True; self.t = {x['name']: x['id'] for x in s.cartesian_targets}

    def pick_and_place(self, home=True):
        t = self.t
        blocks = [dict(kind='movej', name='Sopra il pezzo', to='target', target=t['Pezzo'], offset=[0, 0, 60]),
                  dict(kind='movel', name='Scendi', to='target', target=t['Pezzo'], speed=50),
                  dict(kind='grip', name='Chiudi', command='chiudi'),
                  dict(kind='movel', name='Risali', to='target', target=t['Pezzo'], offset=[0, 0, 60], speed=50),
                  dict(kind='movej', name='Sopra il deposito', to='target', target=t['Deposito'], offset=[0, 0, 60]),
                  dict(kind='movel', name='Appoggia', to='target', target=t['Deposito'], speed=50),
                  dict(kind='grip', name='Apri', command='apri'),
                  dict(kind='movel', name='Allontanati', to='target', target=t['Deposito'], offset=[0, 0, 60])]
        if home: blocks.append(dict(kind='movej', name='HOME', to='home'))
        self.s.action(dict(op='studio_blocks', blocks=blocks))

    def program_plan(self):
        self.s.action(dict(op='studio_program_plan')); return self.s.movej.plan

    def start(self, plan, step=False):
        self.s.action(dict(op='studio_program_execute', id=plan['id'], confirmed=True, step=step))

    def tip(self):
        q = {n: math.radians(self.c.pos[i]) for i, n in enumerate(NAMES)}; q['__gripper'] = 0
        return tcp(self.s.model, q, self.s.calibration, self.s.tip, self.s.tool)


class ProgramPlanTests(ProgramBase):
    def test_pick_and_place_is_planned_block_by_block(self):
        self.pick_and_place(); plan = self.program_plan(); program = plan['program']
        self.assertEqual([b['index'] for b in program['blocks']], list(range(9)))
        self.assertEqual(self.lines, [])  # planning sends nothing
        self.assertTrue(program['cartesian']); self.assertEqual(len(program['lines']), 4)
        for line in program['lines']:
            self.assertAlmostEqual(line['length_mm'], 60, delta=.2); self.assertLessEqual(line['max_deviation_mm'], .5)
        grips = [s['command'] for s in plan['stages'] if s['kind'] == 'grip']; self.assertEqual(grips, ['chiudi', 'apri'])
        self.assertEqual(plan['targets'], [0.]*6)
        self.assertAlmostEqual(plan['duration'], sum(b['duration'] for b in program['blocks']), places=9)
        # Every MoveL stage is a straight descent or rise above the targets, tool pointing down.
        for stage in plan['stages']:
            if stage['block_index'] in (1, 3, 5, 7): self.assertEqual(stage['speed'], .5 if stage['block_index'] != 7 else 1.)
        down = [x for x in plan['samples'] if x['time'] >= program['blocks'][1]['start_time'] and x['time'] <= program['blocks'][2]['start_time']]
        self.assertTrue(all(abs(x['tcp'][0]-.25) < .001 and abs(x['tcp'][1]+.06) < .001 for x in down))
        report = self.s.validation
        self.s.action(dict(op='studio_validate', source='program')); report = self.s.validation
        self.assertTrue(report['ok'], report); self.assertEqual(report['poses'], 7); self.assertEqual(report['samples'], self.s.movej.plan['sample_count'])

    def test_instruction_speed_scales_the_joint_speeds_of_muovi_e_osserva(self):
        self.s.action(dict(op='studio_blocks', blocks=[dict(kind='movej', name='Lento', to='joints', angles=[10, 0, 0, 0, 0, 0], speed=10),
                                                         dict(kind='movej', name='Veloce', to='joints', angles=[20, 0, 0, 0, 0, 0])]))
        self.c.axis_speeds[0] = 5.; plan = self.program_plan(); slow, fast = plan['stages']
        self.assertEqual(slow['requested'][0], 1.)   # 10% of 5 °/s floored to the Mega's 1 °/s
        self.assertEqual(fast['requested'][0], 5.)
        self.assertAlmostEqual(slow['duration']/fast['duration'], 5, delta=.6)
        self.c.axis_speeds[0] = 20.; plan = self.program_plan()
        self.assertEqual(plan['stages'][0]['requested'][0], 2.)
        with self.assertRaises(ValueError): self.s.validate_blocks([dict(kind='movej', to='home', speed=5)])

    def test_problems_are_located_on_their_block(self):
        self.pick_and_place(); c = self.c; c.connected = False
        self.s.edit_scene(dict(op='studio_target_save', id=self.t['Deposito'], name='Deposito', frame_id=self.s.work_frames[0]['id'], xyz=[.70, 0, .04], rpy=[math.pi, 0, 0]))
        c.connected = True
        with self.assertRaisesRegex(ValueError, 'Blocco 5 · Sopra il deposito: Deposito irraggiungibile: fuori portata'): self.program_plan()
        self.assertEqual(self.s.movej.problem['block'], 4); self.assertIsNone(self.s.movej.plan)
        # An obstacle across the descent onto the piece stops the plan on the MoveL block.
        c.connected = False
        self.s.edit_scene(dict(op='studio_target_save', id=self.t['Deposito'], name='Deposito', frame_id=self.s.work_frames[0]['id'], xyz=[.22, .10, .04], rpy=[math.pi, 0, 0]))
        self.s.obstacles = [dict(name='Staffa', center=[.25, -.06, .055], size=[.08, .08, .006])]; c.connected = True
        with self.assertRaisesRegex(ValueError, 'Blocco 2 · Scendi · tratto 1/\\d: interferenza a'): self.program_plan()
        self.assertEqual(self.s.movej.problem['block'], 1)
        self.s.action(dict(op='studio_validate', source='program')); report = self.s.validation
        self.assertFalse(report['ok']); self.assertTrue(report['issues'][0]['where'].startswith('Blocco 2 · Scendi'))
        self.assertIn('Staffa', report['issues'][0]['detail'])

    def test_program_is_saved_in_the_project_and_edits_make_the_plan_stale(self):
        self.pick_and_place(); plan = self.program_plan()
        saved = json.loads((self.s.folder/'project.json').read_text())['blocks']
        self.assertEqual([b['kind'] for b in saved], ['movej', 'movel', 'grip', 'movel', 'movej', 'movel', 'grip', 'movel', 'movej'])
        self.assertEqual(saved[1]['speed'], 50); self.assertEqual(saved[0]['offset'], [0, 0, 60]); self.assertEqual(saved[1]['tolerance'], .5)
        reopened = Studio(self.folder, self.c, builtin=False); self.assertEqual(reopened.blocks, self.s.blocks)
        blocks = [dict(b) for b in self.s.blocks]; blocks[1]['speed'] = 80
        self.s.action(dict(op='studio_blocks', blocks=blocks))
        with self.assertRaisesRegex(ValueError, 'scaduto'): self.start(plan)
        for bad in (dict(kind='movej', to='somewhere'), dict(kind='movel', to='point', frame='tool', xyz=[0, 0, 0]),
                    dict(kind='movel', to='target', target=''), dict(kind='movej', to='joints', angles=[0]*5)):
            with self.assertRaises(ValueError): self.s.validate_blocks([bad])

    def test_sensor_waits_are_planned_and_the_legacy_runner_is_kept_apart(self):
        blocks = [dict(kind='movej', name='A', to='joints', angles=[5, 0, 0, 0, 0, 0]), dict(kind='sensor', name='S', sensor='s', timeout=3)]
        self.s.define_sensor('s', 'digital'); self.s.action(dict(op='studio_blocks', blocks=blocks))
        stages = self.program_plan()['stages']
        self.assertEqual([s['kind'] for s in stages], ['movej', 'sensor']); self.assertEqual((stages[1]['timeout'], stages[1]['duration']), (3, 0.))
        with self.assertRaisesRegex(ValueError, 'MoveJ/MoveL'): self.s.run_program()
        blocks[1]['sensor'] = 'altro'; self.s.action(dict(op='studio_blocks', blocks=blocks))
        with self.assertRaisesRegex(ValueError, 'Blocco 2 · S: sensore non definito: altro'): self.program_plan()

    def test_repeat_plans_each_cycle_from_where_the_previous_ended(self):
        blocks = [dict(kind='movej', name='Avanti', to='joints', angles=[5, 0, 0, 0, 0, 0]), dict(kind='movej', name='Indietro', to='home'),
                  dict(kind='repeat', name='Ripeti', start=0, count=3)]
        self.s.action(dict(op='studio_blocks', blocks=blocks)); plan = self.program_plan()
        self.assertEqual([s['block_index'] for s in plan['stages']], [0, 1]*3)
        self.assertEqual([s['targets'][0] for s in plan['stages']], [5, 0]*3)


class ProgramExecutionTests(ProgramBase):
    def test_pick_and_place_runs_exactly_the_previewed_plan(self):
        self.robot(); self.pick_and_place(); plan = self.program_plan()
        with self.assertRaisesRegex(ValueError, 'corrispondenza fisica'): self.start(plan)
        self.c.connected = False; self.s.action(dict(op='studio_verified', confirmed=True)); self.c.connected = True
        plan = self.program_plan(); self.start(plan); self.wait()
        movej = self.s.movej.state(); self.assertTrue(movej['exec_done'], movej['exec_error'])
        expected = ['~multi '+' '.join('%.2f %.2f' % (d, v) for d, v in zip(s['deltas'], s['requested']))+'\n'
                    for s in plan['stages'] if s['kind'] == 'movej' and s['axes']]
        self.assertEqual(self.multi_lines(), expected)  # same groups, same speeds, same order
        self.assertEqual([line for line in self.lines if line.strip() in ('apri', 'chiudi')], ['chiudi\n', 'apri\n'])
        self.assertEqual(self.c.pos, [0.]*6); self.assertEqual(self.c.trail, [])  # ended at HOME: nothing to retrace
        self.assertEqual(len(movej['exec_measured']), len(plan['stages']))

    def test_step_by_step_holds_before_each_block_and_shows_it(self):
        self.robot(); self.c.connected = False; self.s.action(dict(op='studio_verified', confirmed=True)); self.c.connected = True
        self.pick_and_place(home=False); plan = self.program_plan(); self.start(plan, step=True)
        self.wait(lambda: self.s.movej.step_waiting)
        first = plan['stages'][0]; self.assertEqual(self.c.pos, first['targets'])
        self.assertEqual(plan['stages'][self.s.movej.exec_stage]['block_index'], 0)
        self.assertEqual(len(self.multi_lines()), 1)
        self.s.action(dict(op='studio_program_step')); self.wait(lambda: self.s.movej.step_waiting and plan['stages'][self.s.movej.exec_stage+1]['block_index'] == 2)
        self.assertEqual(len(self.multi_lines()), 1+len([s for s in plan['stages'] if s['block_index'] == 1]))
        end = self.tip(); self.assertAlmostEqual(end[0], .25, places=3); self.assertAlmostEqual(end[2], .04, places=3)  # on the piece
        time.sleep(.5); self.s.action(dict(op='studio_program_continue')); self.wait()
        # Simulated DONE comes after ~0.1 s: a 0.5 s operator pause would show up if it were counted.
        for m in self.s.movej.exec_measured: self.assertLess(m['actual'], .45 if m['kind'] == 'movej' else 2.)
        self.assertTrue(self.s.movej.exec_done, self.s.movej.exec_error); self.assertNotEqual(self.c.trail, [])  # away from HOME
        with self.assertRaisesRegex(ValueError, 'passo passo'): self.s.action(dict(op='studio_program_step'))

    def test_stop_while_waiting_for_the_next_step_ends_without_resume(self):
        self.s.action(dict(op='studio_blocks', blocks=[dict(kind='movej', name='A', to='joints', angles=[2, 0, 0, 0, 0, 0]),
                                                        dict(kind='movej', name='B', to='joints', angles=[4, 0, 0, 0, 0, 0])]))
        plan = self.program_plan(); self.start(plan, step=True); self.wait(lambda: self.s.movej.step_waiting)
        self.s.action(dict(op='studio_cancel')); self.wait()
        self.assertIn('Interrotto', self.s.movej.exec_error); self.assertEqual(self.c.pos[0], 2.)
        with self.assertRaisesRegex(ValueError, 'home'): self.start(plan)  # STOP drops HOME; the plan never resumes

    def test_anteprima_execution_matches_the_estimated_duration(self):
        self.s.action(dict(op='studio_blocks', blocks=[dict(kind='movej', name='A', to='joints', angles=[6, 0, 0, 0, 0, 0], speed=50),
                                                        dict(kind='wait', name='Pausa', seconds=.3), dict(kind='movej', name='HOME', to='home')]))
        plan = self.program_plan(); self.start(plan); self.wait()
        measured = self.s.movej.state()['exec_measured']; self.assertEqual(len(measured), 3)
        for m in measured: self.assertAlmostEqual(m['actual'], m['planned'], delta=.25)
        self.assertEqual(self.c.pos, [0.]*6); self.assertEqual(self.c.trail, []); self.assertEqual(self.c.cycle, 1)
