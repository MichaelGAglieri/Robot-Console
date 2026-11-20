# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Subprograms use the existing checked plan/executor. All controllers are simulated."""
import copy
import json
import threading
import time
from studio import Studio
from test_program import ProgramBase


def block(kind, **values): return dict(kind=kind, name=kind, **values)
def definition(name, params=()): return block('function', function=name, parameters=list(params))
def call(name, args=None, **values): return block('call', function=name, arguments=args or {}, **values)
def end(): return block('end')
def note(text): return dict(kind='note', name=text)
def move(angle): return block('movej', to='joints', angles=[angle, 0, 0, 0, 0, 0])


class FunctionTests(ProgramBase):
    def blocks(self, blocks): self.s.action(dict(op='studio_blocks', blocks=blocks))
    def verified_robot(self):
        self.robot(); self.c.connected=False; self.s.action(dict(op='studio_verified', confirmed=True)); self.c.connected=True

    def test_definition_skipped_forward_call_and_local_scopes(self):
        self.blocks([block('set', variable='n', value='7'), call('inc', {'n':'n + 1'}, result='answer'),
                     block('if', condition='n == 7 and answer == 9'), note('caller intact'), end(),
                     definition('inc', ['n']), block('set', variable='n', value='n+1'), block('return', value='n'), end()])
        plan=self.program_plan()
        self.assertEqual([s['name'] for s in plan['stages']], ['caller intact'])
        self.assertEqual(self.lines, []); self.assertEqual(self.c.pos, [0.]*6)
        self.blocks([definition('unused'), move(12), end(), note('main')])
        self.assertEqual([s['name'] for s in self.program_plan()['stages']], ['main'])

    def test_nested_calls_and_early_return_restore_caller_loop(self):
        self.blocks([definition('inner', ['n']), block('loop', times='3'), block('if', condition='n >= 0'),
                     block('return', value='n*2'), end(), end(), block('return', value='0'), end(),
                     definition('outer', ['x']), call('inner', {'n':'x'}, result='y'), block('return', value='y+1'), end(),
                     block('loop', times='3', variable='i'), call('outer', {'x':'i'}, result='r'),
                     block('if', condition='r == i*2 + 1'), note('correct'), end(), end()])
        plan=self.program_plan(); self.assertEqual(len(plan['stages']), 3)
        self.assertTrue(all(s['name']=='correct' for s in plan['stages']))

    def test_callee_cannot_read_implicit_caller_variables_or_leak_locals(self):
        self.blocks([block('set', variable='secret', value='1'), definition('f'), block('return', value='secret'), end(), call('f')])
        with self.assertRaisesRegex(ValueError, 'Richiamo 5.*Blocco 3.*non definita: secret'): self.program_plan()
        self.blocks([definition('f'), block('set', variable='secret', value='1'), end(), call('f'), block('set', variable='x', value='secret')])
        with self.assertRaisesRegex(ValueError, 'Blocco 5.*non definita: secret'): self.program_plan()

    def test_repeated_calls_resolve_different_cartesian_arguments(self):
        self.blocks([definition('above', ['h']), block('movej', to='target', target=self.t['Pezzo'], offset_expr=['','','h']), end(),
                     call('above', {'h':'60'}), call('above', {'h':'40'}), block('movej', to='home')])
        plan=self.program_plan(); a,b,home=plan['stages']
        self.assertNotEqual(a['targets'], b['targets']); self.assertEqual(home['targets'], [0.]*6)
        self.assertEqual(a['call_path'][0]['call_index'], 3); self.assertEqual(b['call_path'][0]['call_index'], 4)
        self.assertIn('Richiamo 4 → above', a['name']); self.assertEqual(self.lines, [])

    def test_sensor_branches_preserve_call_return_values_and_continuation(self):
        self.s.define_sensor('presente','digital')
        self.blocks([definition('sense', ['base']), block('if', condition='presente'), block('return', value='base+1'),
                     block('else'), block('return', value='base+2'), end(), end(),
                     call('sense', {'base':'10'}, result='a'), call('sense', {'base':'20'}, result='b'),
                     block('if', condition='a == 11 and b == 21'), note('both true'), block('else'), note('other'), end()])
        self.s.action(dict(op='studio_program_plan', scenario={'1':True})); plan=self.s.movej.plan
        self.assertEqual([s['name'] for s in plan['stages']], ['both true'])
        self.assertEqual(plan['program']['decisions'][0]['occurrences'], 2)
        self.assertGreaterEqual(plan['program']['branches'], 7)
        self.s.action(dict(op='studio_program_plan', scenario={'1':False}))
        self.assertEqual([s['name'] for s in self.s.movej.plan['stages']], ['other'])

    def test_bad_unshown_sensor_branch_reports_body_and_callsite(self):
        self.s.define_sensor('presente','digital')
        self.blocks([definition('f'), block('if', condition='presente'), move(360), end(), end(), call('f'), note('main')])
        with self.assertRaisesRegex(ValueError, 'Richiamo 6 → f / Blocco 3'): self.program_plan()
        self.assertEqual(self.s.movej.problem['block'], 2); self.assertEqual(self.lines, [])

    def test_argument_and_result_contracts(self):
        for args in ({}, {'wrong':'2'}, {'x':'2','extra':'3'}):
            with self.subTest(args=args):
                self.blocks([definition('f',['x']), note('body'), end(), call('f', args)])
                with self.assertRaisesRegex(ValueError,'non corrispondenti'): self.program_plan()
        self.blocks([definition('f'), note('body'), end(), call('f', result='x')])
        with self.assertRaisesRegex(ValueError,'non restituisce'): self.program_plan()
        self.blocks([call('missing')])
        with self.assertRaisesRegex(ValueError,'assente o disabilitata'): self.program_plan()
        disabled=definition('f'); disabled['enabled']=False
        self.blocks([disabled, note('body'), end(), call('f')])
        with self.assertRaisesRegex(ValueError,'assente o disabilitata'): self.program_plan()

    def test_sensors_remain_runtime_inputs_not_function_arguments_or_results(self):
        self.s.define_sensor('presente','digital')
        cases=[([definition('f',['x']), note('body'), end(), call('f',{'x':'presente'})], 'solo nelle condizioni'),
               ([definition('f',['presente']), note('body'), end(), call('f',{'presente':'1'})], 'coincide con un sensore'),
               ([definition('f'), block('return',value='presente'), end(), call('f')], 'solo nelle condizioni'),
               ([definition('f'), block('return',value='1'), end(), call('f',result='presente')], 'coincide con un sensore')]
        for blocks,message in cases:
            self.blocks(blocks)
            with self.assertRaisesRegex(ValueError,message): self.program_plan()

    def test_recursion_and_depth_are_rejected_before_execution(self):
        for blocks in ([definition('f'), call('f'), end(), call('f')],
                       [definition('f'),call('g'),end(),definition('g'),call('f'),end(),call('f')]):
            self.blocks(blocks)
            with self.assertRaisesRegex(ValueError,'Ricorsione'): self.program_plan()
        blocks=[]
        for i in range(9): blocks += [definition('f'+str(i)), call('f'+str(i+1)) if i<8 else note('deep'), end()]
        self.blocks(blocks+[call('f0')])
        with self.assertRaisesRegex(ValueError,'oltre 8 livelli'): self.program_plan()
        self.assertEqual(self.lines, [])

    def test_definitions_must_be_unique_top_level_and_well_formed(self):
        bads=[[definition('f'),end(),definition('f'),end()], [definition('f',['x','x']),end()],
              [definition('f',['p'+str(i) for i in range(9)]),end()],
              [block('loop',times='1'),definition('f'),end(),end()], [definition('f'),definition('g'),end(),end()],
              [block('return')], [definition('f')], [definition('f'),end(),block('repeat',start=0)],
              [call('f',{'x':"__import__('os')"})]]
        for blocks in bads:
            with self.subTest(blocks=blocks):
                with self.assertRaises(ValueError): self.blocks(blocks)
        with self.assertRaisesRegex(ValueError,'Massimo 32'):
            self.blocks([b for i in range(33) for b in (definition('f'+str(i)),end())])

    def test_function_edits_invalidate_plan_and_project_roundtrip(self):
        self.blocks([definition('f',['x']), block('return',value='x+1'),end(),call('f',{'x':'1'},result='a'),note('main')])
        plan=self.program_plan(); saved=json.loads((self.s.folder/'project.json').read_text())['blocks']
        self.assertEqual(saved,self.s.blocks)
        reopened=Studio(self.folder,self.c,builtin=False); self.assertEqual(reopened.blocks,saved)
        changed=copy.deepcopy(saved); changed[1]['value']='x+2'; self.blocks(changed)
        with self.assertRaisesRegex(ValueError,'scaduto'): self.start(plan)
        self.assertEqual(self.lines, [])

    def test_function_execution_matches_the_checked_groups_and_speeds(self):
        self.verified_robot()
        self.blocks([definition('f'),move(2),move(0),end(),call('f'),call('f')])
        plan=self.program_plan(); self.start(plan);self.wait()
        self.assertTrue(self.s.movej.exec_done,self.s.movej.exec_error)
        expected=['~multi '+' '.join('%.2f %.2f'%(d,v) for d,v in zip(s['deltas'],s['requested']))+'\n'
                  for s in plan['stages'] if s['kind']=='movej' and s['axes']]
        self.assertEqual(self.multi_lines(),expected);self.assertEqual(len(expected),4)

    def test_step_mode_stops_between_same_body_in_adjacent_calls(self):
        self.verified_robot(); self.blocks([definition('f'),move(2),end(),call('f'),call('f')])
        plan=self.program_plan(); self.start(plan,step=True);self.wait(lambda:self.s.movej.step_waiting)
        self.assertIn('Richiamo 5 → f', self.s.movej.state()['exec_next_name'])
        self.assertEqual(self.s.movej.exec_stage,0); self.s.action(dict(op='studio_program_step'));self.wait()
        self.assertTrue(self.s.movej.exec_done);self.assertEqual(len(self.s.movej.exec_measured),2)

    def test_step_mode_distinguishes_iterations_of_one_callsite(self):
        self.verified_robot(); self.blocks([definition('f'),move(2),end(),block('loop',times='3'),call('f'),end()])
        plan=self.program_plan(); self.assertEqual(len({json.dumps(s['call_path']) for s in plan['stages']}),3)
        self.start(plan,step=True)
        for completed in (1,2):
            self.wait(lambda:self.s.movej.step_waiting and self.s.movej.exec_stage==completed-1)
            self.s.action(dict(op='studio_program_step'))
        self.wait();self.assertTrue(self.s.movej.exec_done);self.assertEqual(len(self.s.movej.exec_measured),3)

    def test_stop_inside_call_ends_without_resuming(self):
        self.blocks([definition('f'),move(2),move(4),end(),call('f')]); plan=self.program_plan()
        self.start(plan,step=True);self.wait(lambda:self.s.movej.step_waiting)
        self.s.action(dict(op='studio_cancel')); self.wait()
        self.assertIn('Interrotto',self.s.movej.exec_error); self.assertEqual(self.c.pos[0],2)
        with self.assertRaises(ValueError): self.s.action(dict(op='studio_program_step'))
        self.assertFalse(self.c.home)

    def test_motion_budget_cannot_be_bypassed_with_calls(self):
        self.blocks([definition('f'),move(2),end(),block('loop',times='1000'),call('f'),end()])
        with self.assertRaisesRegex(ValueError,'(?i)tropp|oltre|massimo'): self.program_plan()
        self.assertEqual(self.lines, [])

    def test_function_pick_place_is_identical_to_flat_program_and_movel_step(self):
        from examples.python_subprograms import program
        self.verified_robot();self.pick_and_place();blocks=copy.deepcopy(self.s.blocks);blocks[7]['speed']=50;self.blocks(blocks);flat=self.program_plan()
        self.blocks(program(self.t));plan=self.program_plan()
        for field in ('targets','duration','sample_count'): self.assertEqual(plan[field],flat[field])
        self.assertEqual([s['targets'] for s in plan['stages']],[s['targets'] for s in flat['stages']])
        self.assertEqual([s.get('requested') for s in plan['stages']],[s.get('requested') for s in flat['stages']])
        self.start(plan,step=True);self.wait(lambda:self.s.movej.step_waiting)
        self.assertEqual(self.s.movej.exec_next_block,2) # descent: first MoveL inside prendi
        self.s.action(dict(op='studio_program_step'))
        self.wait(lambda:self.s.movej.step_waiting and self.s.movej.exec_next_block==3) # grip, after every MoveL segment
        expected=1+sum(s['block_index']==2 for s in plan['stages'])
        self.assertEqual(len(self.multi_lines()),expected)
        self.s.action(dict(op='studio_program_continue'));self.wait(timeout=30)
        self.assertTrue(self.s.movej.exec_done,self.s.movej.exec_error);self.assertEqual(self.c.pos,[0.]*6)

    def test_nested_motion_trace_and_bad_return_branch(self):
        self.blocks([definition('inner'),move(1),end(),definition('outer'),call('inner'),end(),call('outer')])
        stage=self.program_plan()['stages'][0]
        self.assertEqual([f['function'] for f in stage['call_path']],['outer','inner'])
        self.assertIn('Richiamo 7 → outer / Richiamo 5 → inner',stage['name'])
        self.s.define_sensor('presente','digital')
        self.blocks([definition('f'),block('if',condition='presente'),block('return',value='1'),end(),end(),call('f',result='x'),note('main')])
        with self.assertRaisesRegex(ValueError,'non restituisce'):self.program_plan()
        self.assertEqual(self.lines,[])
