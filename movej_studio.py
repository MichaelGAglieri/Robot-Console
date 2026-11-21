# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Studio adapter for MoveJ plans. Planning, seeking and animation are virtual; `execute`
hands exactly the validated plan to movej_run through Controller.spawn after confirmation."""
import copy
import hashlib
import json
import math
import threading
import time
import uuid
from movej_preview import build_plan, coordinates, position_at, PlanError
from movej_run import run_plan, run_tree, stage_start_matches
from program_plan import ProgramPlanner, ProgramError, is_motion_program
from program_lang import parse, evaluate
from movel import plan_line
from ik5 import Chain
from robot_model import number
from robot_model import tcp


class MoveJPreview:
    def __init__(self, studio):
        self.s = studio; self.plan = None; self.running = False; self.elapsed = 0.
        self.started = 0.; self.error = ''; self.visual_active = False
        self.grip = 'non comandata'; self.stage = -1; self.seed = {}
        self.executing = False; self.exec_stage = -1; self.exec_error = ''; self.exec_done = False; self.pose_indices = set()
        self.exec_measured = []; self.stage_started = 0.; self.movel = None
        # Offline programs: the block that failed planning, and step-by-step execution.
        self.problem = None; self.step_mode = False; self.step_waiting = False; self.step_block = None
        self.step_event = threading.Event()
        # Offline programs run as a tree: the stage in progress, its block and the conditions met.
        self.exec_current = None; self.exec_block = -1; self.exec_next_block = -1; self.exec_decisions = []; self.exec_name = ''; self.exec_next_name = ''

    def ready(self):
        # Planning and animation are pure geometry, in Anteprima or with the robot connected.
        c = self.s.controller
        if c.busy or c.playing or c.firmware_busy or self.s.program_running or self.executing:
            raise ValueError('Attendi il controllore fermo prima dell’anteprima MoveJ.')

    def context(self):
        s = self.s; c = s.controller
        values = [c.group_context(), c.connected, c.grip, s.model['source_hash'], s.mapping,
                  s.calibration, s.effective_enabled(), s.tool, s.tip, s.obstacles, s.workcell, s.blocks, c.sequence,
                  s.work_frames, s.cartesian_targets, sorted(s.sensors), s.outputs]
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def model_positions(self, q, grip, *, allow_unmapped=False):
        s = self.s; c = s.controller; positions = self.seed.copy(); mapped = set()
        for joint in s.independent():
            name = joint['name']; axis = s.mapping[name]
            if axis >= 0:
                if axis in mapped: raise ValueError('Mapping MoveJ duplicato.')
                if joint['kind'] == 'prismatic': raise ValueError('MoveJ di questo incremento richiede giunti rotativi.')
                mapped.add(axis); positions[name] = math.radians(q[axis])
                if not s.effective_enabled()[name] and abs(q[axis]-c.pos[axis]) > .005:
                    raise ValueError('MoveJ richiede un giunto escluso: '+name)
            value = positions.get(name, 0.) * s.calibration[name]['sign'] + s.calibration[name]['offset']
            if not joint['lower']-1e-6 <= value <= joint['upper']+1e-6:
                raise ValueError('MoveJ fuori dai limiti URDF calibrati: '+name)
        if not allow_unmapped and any(abs(v-c.pos[i]) > .005 and i not in mapped for i, v in enumerate(q)):
            raise ValueError('MoveJ richiede un asse non associato al modello.')
        positions['__gripper'] = 1. if grip == 'apri' else 0.
        return positions

    def evaluate(self, q, grip, *, allow_unmapped=False):
        positions = self.model_positions(q, grip, allow_unmapped=allow_unmapped)
        return tcp(self.s.model, positions, self.s.calibration, self.s.tip, self.s.tool), self.s.collision_report(positions)

    @staticmethod
    def transition_instructions(start, target, name, block_index=-1, motion=None):
        from server import sequence_units
        point=start[:]
        result=[]
        for unit,pause in sequence_units(point,target,motion):
            for edge in unit:
                axis=edge['axis']
                point[axis]=round(point[axis]+edge['delta'],2)
            joint=unit[0]['axis']+1
            label=f'{name} · J{joint}' if motion and motion['mode']=='ordered' else name
            result.append(dict(kind='movej',name=label,target=point[:],block_index=block_index))
            if pause:
                result.append(dict(kind='wait',name=f'Pausa dopo J{joint}',seconds=pause,block_index=block_index))
        return result

    def pose_instructions(self, index, block_index=-1, start=None, motion=None):
        sequence = self.s.controller.sequence
        if type(index) != int or not 0 <= index < len(sequence): raise ValueError('Posa MoveJ non presente.')
        pose = sequence[index]
        if not pose.get('enabled', True): return []
        self.pose_indices.add(index)
        point=list(self.s.controller.pos if start is None else start)
        result=self.transition_instructions(point,coordinates(pose['pos']),pose['name'],block_index,motion)
        if pose.get('grip') in ('apri', 'chiudi'):
            result.append(dict(kind='grip', name=pose['grip'], command=pose['grip'], seconds=1.5, block_index=block_index))
        result.append(dict(kind='wait', name=pose['name'], seconds=pose.get('dwell', 0.), block_index=block_index))
        return result

    def movel_instructions(self, request, start):
        """Straight TCP line from the commanded pose, as MoveJ waypoints (degrees, 0.01°)."""
        s = self.s; c = s.controller
        frame_key = request.get('frame', 'base')
        if frame_key == 'tool': raise ValueError('Per MoveL scegli la base o un riferimento di lavoro.')
        frame = s.cartesian.frame(frame_key); local = request.get('target')
        if not isinstance(local, list) or len(local) != 3: raise ValueError('MoveL richiede X, Y e Z.')
        local = [number(v, -10, 10) for v in local]
        target = [sum(frame[i][k]*local[k] for k in range(3))+frame[i][3] for i in range(3)]
        mode = request.get('orientation', 'keep')
        if mode not in ('keep', 'free'): raise ValueError('Orientamento MoveL non valido.')
        tolerance = number(request.get('tolerance', .5), .05, 5)/1000
        q0 = dict(self.seed); enabled = s.effective_enabled(); usable = {}
        for joint in s.independent():
            name = joint['name']; axis = s.mapping[name]; usable[name] = enabled[name] and axis >= 0
            if axis >= 0: q0[name] = math.radians(start[axis])
        chain = Chain(s.model, s.tip, s.tool, s.calibration, usable)
        for name in chain.variables:
            # Controller limits apply too, so the line stops where the robot would refuse it.
            lo, hi = chain.limits[name]; clo, chi = c.limits[s.mapping[name]]
            chain.limits[name] = (max(lo, math.radians(clo)), min(hi, math.radians(chi)))
        result = plan_line(chain, q0, target, mode == 'keep', tolerance)
        count = result['segments']; instructions = []
        for i, q in enumerate(result['waypoints'][1:]):
            angles = start[:]
            for name in chain.variables: angles[s.mapping[name]] = round(math.degrees(q[name]), 2)
            instructions.append(dict(kind='movej', name='MoveL %d/%d' % (i+1, count), target=angles))
        self.movel = dict(length_mm=result['length']*1000, segments=count, max_deviation_mm=result['max_deviation']*1000,
                          end_error_mm=result['end_error']*1000, tolerance_mm=tolerance*1000, orientation=mode,
                          axis_error_deg=None if result['axis_error'] is None else math.degrees(result['axis_error']),
                          roll_error_deg=None if result['roll_error'] is None else math.degrees(result['roll_error']),
                          singular=result['singular'], start_mm=[v*1000 for v in result['start']], target_mm=[v*1000 for v in target])
        return instructions

    def prepare(self, request):
        self.ready()
        if self.running: raise ValueError('Ferma prima l’animazione MoveJ.')
        s = self.s; c = s.controller; self.plan = None; self.error = ''; self.elapsed = 0.
        self.pose_indices = set(); self.exec_stage = -1; self.exec_error = ''; self.exec_done = False
        self.exec_measured = []; self.movel = None; self.problem = None; planner = None
        self.seed = s.current_positions().copy()
        try:
            start = coordinates(c.pos)
            if any(not lo <= v <= hi for v, (lo, hi) in zip(start, c.limits)):
                raise ValueError('Posizione iniziale fuori dai limiti applicati.')
            source = request.get('source', 'joints'); instructions = []; collision_notes=[]
            motion=c.require_sequence_motion() if source=='sequence' else None
            ordered=motion is not None and motion['mode']=='ordered'
            warnings_only=source in ('sequence','home') and not c.operator_collision_checks
            def operator_evaluate(q,grip):
                point,hits=(self.evaluate(q,grip,allow_unmapped=True) if ordered else self.evaluate(q,grip))
                if warnings_only and hits:
                    note='Interferenza modello (solo avviso): '+', '.join(hits[:3])
                    if note not in collision_notes and len(collision_notes)<200:collision_notes.append(note)
                    return point,[]
                return point,hits
            if source == 'joints': instructions = [dict(kind='movej', name='Angoli assoluti', target=coordinates(request.get('targets')))]
            elif source == 'studio':
                target = start[:]
                for joint in s.independent():
                    axis = s.mapping[joint['name']]
                    if axis >= 0: target[axis] = math.degrees(self.seed[joint['name']])
                    elif abs(self.seed.get(joint['name'], 0.)) > 1e-6:
                        raise ValueError('Il giunto '+joint['name']+' non è associato a un motore.')
                instructions = [dict(kind='movej', name='Giunti Studio', target=target)]
            elif source == 'pose': instructions = self.pose_instructions(request.get('index'),start=start)
            elif source in ('sequence','home'):
                point=start[:]
                if source=='sequence':
                    for index,pose in enumerate(c.sequence):
                        if not pose.get('enabled',True):continue
                        c.validate_pose(pose)
                        instructions.extend(self.pose_instructions(index,index,start=point,motion=motion))
                        point=coordinates(pose['pos'])
                    if not instructions:raise ValueError('Abilita almeno una posa per riprodurre la sequenza.')
                if source=='home' or request.get('return_home') is True:
                    instructions.extend(self.transition_instructions(point,[0.]*6,'HOME',motion=motion))
                    if not instructions:instructions=[dict(kind='note',name='Già a HOME',seconds=0.)]

            elif source == 'movel': instructions = self.movel_instructions(request, start)
            elif source == 'program' and (is_motion_program(s.blocks) or request.get('offline') is True):
                scenario = request.get('scenario') or {}
                if not isinstance(scenario, dict) or any(type(v) != bool for v in scenario.values()): raise ValueError('Scelta dei rami non valida.')
                planner = ProgramPlanner(self); context = self.context()
                built = planner.build(start, c.grip, lambda d, q, scale=1.: c.group_plan(d, starts=q, scale=scale), self.evaluate, context, scenario)
                self.plan = dict(id=uuid.uuid4().hex, context=context, starts=start, targets=built['targets'], stages=built['stages'],
                                 samples=built['samples'], duration=built['duration'], initial_grip=c.grip, sample_count=len(built['samples']),
                                 max_joint_step_deg=1., preview_only=True, tree=built['tree'], scenario=scenario,
                                 source=source, pose_indices=sorted(self.pose_indices), movel=None, program=planner.summary(built, built))
                self.visual_active = False
                p = self.plan['program']
                s.status = ('Programma pianificato: %d istruzioni, durata stimata %.1f s; anteprima ed esecuzione usano questo piano.' % (len(p['blocks']), self.plan['duration'])
                            + (' Rami verificati: %d.' % p['branches'] if p['branches'] > 1 else ''))
                return
            elif source == 'program':
                for index, block in s.expanded_program():
                    if block['kind'] == 'pose': instructions.extend(self.pose_instructions(block['index'], index))
                    elif block['kind'] in ('wait', 'grip', 'note'):
                        instructions.append(dict(kind=block['kind'], name=block['name'], block_index=index,
                                                 seconds=1.5 if block['kind']=='grip' else block.get('seconds', 0.), command=block.get('command', '')))
                    else: raise ValueError('L’anteprima MoveJ non simula attese sensore o istruzioni sconosciute.')
            else: raise ValueError('Sorgente MoveJ non valida.')
            if not instructions: raise ValueError('Nessuna posa o istruzione abilitata per MoveJ.')
            if request.get('return_to_start') is True:
                instructions.append(dict(kind='movej', name='Ritorno al punto iniziale', target=start))
            context = self.context()
            plan_limits=dict(max_instructions=1000,max_moves=384) if ordered else {}
            self.plan = build_plan(start, instructions, lambda d, q, scale=1.: c.group_plan(d, starts=q, scale=scale),
                                   operator_evaluate, context, c.grip, **plan_limits)
            self.plan['model_warnings']=collision_notes
            self.plan['allow_unmapped']=ordered
            self.plan['controller_context']=c.group_context();self.plan['source'] = source; self.plan['pose_indices'] = sorted(self.pose_indices); self.visual_active = False
            self.plan['movel'] = self.movel if source == 'movel' else None
            self.plan['program'] = None
            s.status = ('Piano MoveL pronto: %d tratti, deviazione massima %.2f mm.' % (self.movel['segments'], self.movel['max_deviation_mm'])
                        if source == 'movel' else 'Operatore · interfaccia 3D solo avvisi: controlla il percorso fisico.' if warnings_only else 'Piano MoveJ virtuale pronto; nessun percorso salvato o comando fisico modificato.')
        except ProgramError as error:
            self.error = str(error); self.problem = dict(block=error.block, where=error.where, detail=error.detail, angles=c.pos[:])
            s.status = 'Programma non pianificabile: '+str(error); raise
        except (ValueError, TypeError, KeyError) as error:
            self.error = str(error); raise

    def validate(self, plan_id):
        self.ready()
        if self.error or not self.plan or self.plan.get('executed') or plan_id != self.plan['id'] or self.context() != self.plan['context']:
            raise ValueError('Piano MoveJ scaduto: ripianifica dopo le modifiche.')

    def render(self):
        from server import motion_fraction
        q, self.grip, self.stage = position_at(self.plan, self.elapsed, motion_fraction)
        self.s.preview = self.model_positions(q, self.grip, allow_unmapped=self.plan.get('allow_unmapped',False)); self.s.follow = False; self.visual_active = True

    def seek(self, plan_id, elapsed):
        self.validate(plan_id)
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or not 0 <= elapsed <= self.plan['duration']:
            raise ValueError('Tempo dell’anteprima non valido.')
        self.running = False; self.elapsed = elapsed; self.render()

    def play(self, plan_id):
        self.validate(plan_id); self.elapsed = 0.; self.started = time.monotonic(); self.running = True; self.render()

    def stop(self):
        self.tick(); self.running = False

    def clear(self):
        self.running = False
        if self.executing: return  # the worker owns its plan; keep its status visible
        self.plan = None; self.visual_active = False; self.elapsed = 0.; self.error = ''; self.problem = None
        self.exec_stage = -1; self.exec_error = ''; self.exec_done = False; self.exec_measured = []
        self.exec_block = self.exec_next_block = -1; self.exec_decisions = []

    def on_stage(self, index):
        # Measured wall time per stage: on the robot this includes ACK/DONE and USB latency.
        now = time.monotonic(); stages = self.plan['stages'] if self.plan else []
        if 0 <= self.exec_stage < len(stages):
            stage = stages[self.exec_stage]
            self.exec_measured.append(dict(index=self.exec_stage, kind=stage['kind'], planned=stage['duration'], actual=now-self.stage_started))
        self.exec_stage = index; self.stage_started = now

    def on_tree_stage(self, stage):
        """Like on_stage for program trees; sensor waits have no estimate and are not compared."""
        now = time.monotonic(); done = self.exec_current
        if done is not None and done['kind'] != 'sensor':
            self.exec_measured.append(dict(index=self.exec_stage, kind=done['kind'], planned=done['duration'], actual=now-self.stage_started))
        self.exec_current = stage; self.exec_stage += 1; self.stage_started = now
        self.exec_block = stage['block_index'] if stage else -1; self.exec_name = stage['name'] if stage else ''

    def read_sensor(self, name):
        """Current value of a defined input. On the real robot only fresh, non-simulated data count."""
        return self.s.io.read_sensor(name)

    def decide(self, end):
        """Evaluate a planned condition with the live sensors; both outcomes were planned."""
        env = dict(end['variables'])
        try:
            for name in end['sensors']: env[name] = self.read_sensor(name)
            result = bool(evaluate(parse(end['condition']), env))
        except ValueError as error:
            raise ValueError('Condizione del blocco %d (%s): %s.' % (end['block']+1, end['condition'], error)) from error
        self.exec_decisions = (self.exec_decisions+[dict(block_index=end['block'], result=result)])[-50:]
        self.s.controller.log('Condizione blocco %d «%s»: %s.' % (end['block']+1, end['condition'], 'vera' if result else 'falsa'))
        return result

    def execute(self, request):
        """Run the previewed plan on the connected controller (Anteprima or robot)."""
        s = self.s; c = s.controller
        if request.get('confirmed') is not True: raise ValueError('Conferma esplicita richiesta.')
        with c.lock:
            c.check()
            if self.running: raise ValueError('Ferma prima l’animazione MoveJ.')
            self.validate(request.get('id')); plan = self.plan
            cartesian = plan.get('source') in ('studio', 'movel') or bool((plan.get('program') or {}).get('cartesian'))
            if c.mode == 'robot':
                if cartesian and not s.verified:
                    raise ValueError('Conferma prima la corrispondenza fisica di modello, mapping e calibrazione.')
                for index in plan.get('pose_indices', []):
                    if c.sequence[index].get('mode') != c.mode:
                        raise ValueError('La posa %d è stata registrata in Anteprima: registrala sul robot reale.' % (index+1))
            if not stage_start_matches(c, dict(starts=plan['starts'])):
                raise ValueError('Piano MoveJ scaduto: ripianifica dopo le modifiche.')
            program = plan.get('program') is not None
            self.executing = True; self.exec_stage = -1; self.exec_error = ''; self.exec_done = False; self.exec_measured = []
            self.visual_active = False; s.follow = True
            self.step_mode = program and request.get('step') is True; self.step_block = None
            self.step_waiting = False; self.step_event.clear()
            self.exec_current = None; self.exec_block = self.exec_next_block = -1; self.exec_decisions = []; self.exec_name = ''; self.exec_next_name = ''

            def gate(index, stage, gen):
                # Step by step: run the first block, then hold before every new block until released.
                block = stage.get('block_index', -1)
                step_key = (block, json.dumps(stage.get('call_path', []), sort_keys=True))
                if not self.step_mode or step_key == self.step_block: return
                if self.step_block is None: self.step_block = step_key; return
                self.step_waiting = True; self.exec_next_block = block; self.exec_next_name = stage['name']
                s.status = 'Passo passo: premi «Istruzione successiva» per il blocco %d.' % (block+1)
                held = time.monotonic()
                try:
                    while self.step_mode and not self.step_event.is_set():
                        c.wait_ready(gen); time.sleep(.03)
                finally:
                    # The operator's pause is not part of the measured stage duration.
                    self.step_waiting = False; self.stage_started += time.monotonic()-held
                self.step_event.clear(); self.step_block = step_key

            def work(gen):
                try:
                    if program: run_tree(c, plan['tree'], gen, self.on_tree_stage, lambda stage: gate(None, stage, gen), self.read_sensor, self.decide, s.io.write_output)
                    else: run_plan(c, plan, gen, self.on_stage, lambda index, stage: gate(index, stage, gen))
                except Exception as error:
                    self.exec_error = str(error); s.status = 'MoveJ interrotto: '+str(error); raise
                else:
                    self.exec_done = True; s.status = 'MoveJ eseguito: %d tratti completati.' % len(plan['stages'])
                    c.log('MoveJ completato: %d tratti · %s' % (len(plan['stages']), 'anteprima' if c.mode == 'demo' else 'DONE firmware, posizione non misurata'))
                    if program:
                        s.status = 'Programma eseguito: %d istruzioni completate.' % len(plan['program']['blocks'])
                        with c.lock:
                            c.cycle += 1
                            # Back at HOME by commanded count: no route left to retrace.
                            if all(abs(v) <= .005 for v in c.pos): c.trail.clear(); c.log('Programma terminato in HOME.')
                finally:
                    plan['execution_result'] = dict(done=self.exec_done, error=self.exec_error, measured=copy.deepcopy(self.exec_measured), decisions=copy.deepcopy(self.exec_decisions))
                    plan['executed'] = True; self.executing = False; self.step_mode = False

            s.status = 'MoveJ in esecuzione: STOP interrompe senza ripresa automatica.'
            c.playing = True; c.spawn(work)

    def release(self, continuous=False):
        """Step by step: let the next block run, or finish the program without stopping."""
        if not self.executing or not self.step_mode: raise ValueError('Nessun programma passo passo in attesa.')
        if continuous: self.step_mode = False; self.s.status = 'Programma: esecuzione continua fino alla fine.'
        self.step_event.set()

    def tick(self):
        if not self.plan or self.executing or self.plan.get('executed'): return
        try: self.validate(self.plan['id'])
        except ValueError as error:
            self.running = False; self.error = str(error); return
        if self.running:
            self.elapsed = min(self.plan['duration'], time.monotonic()-self.started)
            self.render()
            if self.elapsed >= self.plan['duration']: self.running = False

    def state(self):
        plan = self.plan
        if plan and len(plan['samples']) > 2000:
            # Long programs: the panel only draws the TCP trace, every sample was checked.
            step = math.ceil(len(plan['samples'])/2000); plan = dict(plan, samples=plan['samples'][::step]+plan['samples'][-1:])
        if plan and 'tree' in plan: plan = {k: v for k, v in plan.items() if k != 'tree'}  # executor data, not for the panel
        return dict(plan=plan, running=self.running, problem=self.problem, exec_block=self.exec_block,
                    exec_next_block=self.exec_next_block, exec_next_name=self.exec_next_name, exec_name=self.exec_name, exec_decisions=self.exec_decisions,
                    step_mode=self.step_mode, step_waiting=self.step_waiting, elapsed=self.elapsed, error=self.error,
                    valid=self.plan is not None and not self.error and not self.plan.get('executed'),
                    visual_active=self.visual_active, grip=self.grip, stage=self.stage,
                    executing=self.executing, exec_stage=self.exec_stage, exec_error=self.exec_error, exec_done=self.exec_done,
                    exec_measured=self.exec_measured[-200:])
