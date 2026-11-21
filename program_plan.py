# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Offline programs as a plan of verified branches. Pure planning, no controller commands.

An interpreter walks the blocks with its own state: commanded angles, gripper,
variables and loop counters. Motion blocks start from the angles the previous block
leaves (MoveJ to a Cartesian target solves IK seeded with them, MoveL becomes the
waypoints of movel.plan_line). Variables, loop counts and target offsets are known
while planning; only `if` conditions that read sensors are decided while running.
At such a condition the interpreter closes the current segment and plans both
outcomes. Segments that start from the same state are planned once, so branches that
come back together are merged. Every segment goes through movej_preview.build_plan
(1° samples against limits and collisions), so whichever branch the sensors choose,
the executor (movej_run.run_tree) only runs stages that were planned and checked.
The 3D preview, durations and validation follow one path chosen per condition.
"""
import math
import program_functions as functions
from ik5 import Chain, inverse_kinematics, unreachable_reason, column, ORIENTATION_WARN
from movel import plan_line
from movej_preview import build_plan, coordinates, PlanError
from program_lang import parse, names, evaluate, structure
from work_scene import scene_state

MOTION = ('movej', 'movel')
OFFLINE = ('movej', 'movel', 'loop', 'if', 'set', 'output', 'function', 'call', 'return')
GRIP_SECONDS = 1.5  # Controller.servo waits 30 × 50 ms
SEGMENT_LIMITS = dict(max_instructions=2000, max_moves=800, max_samples=40000)
MAX_SEGMENTS = 128
MAX_SAMPLES = 120000
MAX_STEPS = 20000
MAX_LOOP = 1000
REASONS = dict(reach='fuori portata', limits='limiti dei giunti', locked='giunti esclusi', workspace='nessuna soluzione')


def is_motion_program(blocks):
    """Offline program: planned and run as a whole (MoveJ/MoveL, loops, conditions, variables)."""
    return any(b['kind'] in OFFLINE and b.get('enabled', True) for b in blocks)


class ProgramError(ValueError):
    """A block that cannot be planned; `block` indexes Studio.blocks."""

    def __init__(self, message, block, where, detail):
        super().__init__(message); self.block = block; self.where = where; self.detail = detail


class State:
    """Interpreter state at a block: everything that decides what follows."""
    __slots__ = ('pc', 'angles', 'grip', 'variables', 'loops', 'repeats', 'via', 'calls')

    def __init__(self, pc, angles, grip, variables, loops=(), repeats=(), via=(), calls=()):
        self.pc = pc; self.angles = angles; self.grip = grip; self.variables = variables
        self.loops = loops; self.repeats = repeats; self.via = via; self.calls = calls

    def copy(self, **changes):
        values = {k: getattr(self, k) for k in self.__slots__}; values.update(changes)
        values['variables'] = dict(values['variables']); values['angles'] = list(values['angles'])
        return State(**values)

    def key(self):
        return (self.pc, tuple(self.angles), self.grip, tuple(sorted(self.variables.items())), self.loops, self.repeats, self.calls)


class ProgramPlanner:
    def __init__(self, movej):
        self.m = movej; self.s = movej.s; self.c = self.s.controller
        self.cartesian = False; self.lines = []; self.blocks = self.s.blocks
        self.match = structure(self.blocks); self.functions = functions.definitions(self.blocks, self.match)

    # Geometry of single instructions --------------------------------------------------

    def chain(self):
        """Mapped, enabled joints with URDF and controller limits, as MoveL uses them."""
        s = self.s; enabled = s.effective_enabled()
        usable = {j['name']: enabled[j['name']] and s.mapping[j['name']] >= 0 for j in s.independent()}
        chain = Chain(s.model, s.tip, s.tool, s.calibration, usable)
        for name in chain.variables:
            lo, hi = chain.limits[name]; clo, chi = self.c.limits[s.mapping[name]]
            chain.limits[name] = (max(lo, math.radians(clo)), min(hi, math.radians(chi)))
        return chain

    def model_q(self, angles):
        q = dict(self.m.seed)
        for joint in self.s.independent():
            axis = self.s.mapping[joint['name']]
            if axis >= 0: q[joint['name']] = math.radians(angles[axis])
        return q

    def angles(self, chain, q, start):
        result = start[:]
        for name in chain.variables: result[self.s.mapping[name]] = round(math.degrees(q[name]), 2)
        return result

    def offset(self, block, variables):
        """Target offset in mm; an entry of `offset_expr` (e.g. «strato*20») replaces the number."""
        values = list(block.get('offset', [0, 0, 0])); expressions = block.get('offset_expr') or ['', '', '']
        for k, text in enumerate(expressions):
            if text:
                value = self.known(text, variables)
                if type(value) not in (int, float) or not -500 <= value <= 500: raise ValueError('scostamento %s fuori da ±500 mm' % text)
                values[k] = value
        return values

    def scene_target(self, block, variables):
        _, targets = scene_state(self.s.work_frames, self.s.cartesian_targets)
        found = next((t for t in targets if t['id'] == block.get('target')), None)
        if found is None: raise ValueError('target non presente nella scena')
        m = [found['matrix'][i*4:i*4+4] for i in range(4)]
        # The offset is in the target's work frame: on a table frame, Z +60 means 60 mm above.
        frame = self.s.cartesian.frame(found['frame_id']); offset = [v/1000 for v in self.offset(block, variables)]
        point = [m[i][3]+sum(frame[i][k]*offset[k] for k in range(3)) for i in range(3)]
        return point, column(m, 2), found['name']

    def point(self, block, variables):
        if block['to'] == 'target': return self.scene_target(block, variables)
        frame = self.s.cartesian.frame(block['frame']); local = [v/1000 for v in block['xyz']]
        return [sum(frame[i][k]*local[k] for k in range(3))+frame[i][3] for i in range(3)], None, 'punto'

    def movej_target(self, block, current, variables):
        to = block['to']
        if to == 'home': return [0.]*6
        if to == 'joints': return coordinates(block['angles'])
        if to == 'pose':
            sequence = self.c.sequence
            block=dict(block,index=self.s.pose_index(block))
            if not 0 <= block['index'] < len(sequence): raise ValueError('posa non presente')
            self.m.pose_indices.add(block['index']); return coordinates(sequence[block['index']]['pos'])
        # Cartesian target: IK seeded with the angles left by the previous block.
        self.cartesian = True
        point, axis, name = self.scene_target(block, variables)
        if block.get('orientation', 'axis') == 'position': axis = None
        chain = self.chain(); q = self.model_q(current)
        found, closest = inverse_kinematics(chain, q, point, axis)
        if not found:
            reason, _, _ = unreachable_reason(chain, q, point, closest)
            raise ValueError('%s irraggiungibile: %s' % (name, REASONS[reason]))
        best = found[0]
        if axis is not None and (best['axis_error'] or 0) > ORIENTATION_WARN:
            raise ValueError('%s: asse del target non realizzabile con questi assi (scarto %.1f°); scegli «solo posizione»'
                             % (name, math.degrees(best['axis_error'])))
        return self.angles(chain, best['positions'], current)

    def movel(self, block, index, current, variables):
        self.cartesian = True
        point, _, _ = self.point(block, variables); chain = self.chain()
        result = plan_line(chain, self.model_q(current), point, block.get('orientation', 'keep') == 'keep', block.get('tolerance', .5)/1000)
        line = dict(block_index=index, length_mm=result['length']*1000, segments=result['segments'],
                    max_deviation_mm=result['max_deviation']*1000, end_error_mm=result['end_error']*1000,
                    axis_error_deg=None if result['axis_error'] is None else math.degrees(result['axis_error']))
        return [self.angles(chain, q, current) for q in result['waypoints'][1:]], line

    # Interpreter ----------------------------------------------------------------------

    def known(self, text, variables):
        """Value of an expression fixed at planning time: numbers and variables, never sensors."""
        tree = parse(text); used = names(tree)
        sensors = used & set(self.s.sensors)
        if sensors: raise ValueError('i sensori (%s) si leggono solo nelle condizioni «Se» e nelle attese' % ', '.join(sorted(sensors)))
        missing = used-set(variables)
        if missing: raise ValueError('variabile non definita: %s' % ', '.join(sorted(missing)))
        return evaluate(tree, variables)

    def label(self, index):
        return 'Blocco %d · %s' % (index+1, self.blocks[index]['name'])

    def where(self, state, index):
        """Readable location, with the sensor outcomes that lead to this branch."""
        label = self.label(index)
        if state.calls: label = functions.location(functions.trace(state.calls))+' / '+label
        if not state.via: return label
        return '%s (ramo: %s)' % (label, ', '.join('Se al blocco %d %s' % (b+1, 'vero' if o else 'falso') for b, o in state.via))

    def segment(self, state):
        """Instructions from `state` until the program ends or a condition reads sensors."""
        st = state.copy(); out = []; lines = []; blocks = self.blocks; steps = 0
        while st.pc < len(blocks):
            steps += 1; index = st.pc; block = blocks[index]; kind = block['kind']
            if steps > MAX_STEPS: raise ProgramError('%s: oltre %d passi di interpretazione.' % (self.label(index), MAX_STEPS), index, self.where(st, index), 'programma troppo lungo')
            try:
                if not block['enabled'] and kind not in ('else', 'end'):
                    # A disabled loop or condition skips its whole body.
                    st.pc = self.match[index]['end']+1 if kind in ('loop', 'if', 'function') else index+1; continue
                if kind == 'function':
                    # Definitions are never executed by falling through the main program.
                    st.pc = self.match[index]['end']+1
                elif kind == 'call':
                    functions.enter(st, block, index, self.functions, self.known, self.s.sensors)
                elif kind == 'return':
                    value = self.known(block['value'], st.variables) if block['value'] else None
                    functions.leave(st, value)
                elif kind == 'loop':
                    count = self.known(block['times'], st.variables)
                    if count != int(count) or not 0 <= count <= MAX_LOOP: raise ValueError('numero di ripetizioni intero da 0 a %d' % MAX_LOOP)
                    if count == 0: st.pc = self.match[index]['end']+1; continue
                    if block.get('variable'):
                        if block['variable'] in self.s.sensors: raise ValueError('%s è il nome di un sensore: scegli un altro nome' % block['variable'])
                        st.variables[block['variable']] = 0
                    st.loops = st.loops+((index, int(count)-1),); st.pc = index+1
                elif kind == 'end':
                    owner = self.match[index]['owner']
                    if blocks[owner]['kind'] == 'function':
                        functions.leave(st); continue
                    if blocks[owner]['kind'] == 'loop' and st.loops[-1][1] > 0:
                        st.loops = st.loops[:-1]+((owner, st.loops[-1][1]-1),); st.pc = owner+1
                        if blocks[owner].get('variable'): st.variables[blocks[owner]['variable']] += 1
                    else:
                        if blocks[owner]['kind'] == 'loop': st.loops = st.loops[:-1]
                        st.pc = index+1
                elif kind == 'else': st.pc = self.match[index]['end']+1  # end of the true branch
                elif kind == 'if':
                    tree = parse(block['condition']); used = names(tree)
                    unknown = used-set(st.variables)-set(self.s.sensors)
                    if unknown: raise ValueError('nome sconosciuto: %s (variabile non ancora definita o sensore non definito)' % ', '.join(sorted(unknown)))
                    skip = self.match[index].get('else', self.match[index]['end'])+1
                    if not used & set(self.s.sensors):
                        st.pc = index+1 if evaluate(tree, st.variables) else skip; continue
                    known = {n: st.variables[n] for n in used if n in st.variables}
                    end = dict(block=index, condition=block['condition'], variables=known,
                               sensors=sorted(used & set(self.s.sensors)),
                               states=(st.copy(pc=index+1, via=st.via+((index, True),)), st.copy(pc=skip, via=st.via+((index, False),))))
                    return out, end, lines, st
                elif kind == 'set':
                    if block['variable'] in self.s.sensors: raise ValueError('%s è il nome di un sensore: scegli un altro nome' % block['variable'])
                    st.variables[block['variable']] = self.known(block['value'], st.variables); st.pc = index+1
                elif kind == 'repeat':
                    # Earlier increment: repeat blocks start..index-1, `count` times in all.
                    counters = dict(st.repeats); left = counters.get(index, block['count']-1)
                    if left > 0: counters[index] = left-1; st.pc = block['start']
                    else: counters.pop(index, None); st.pc = index+1
                    st.repeats = tuple(sorted(counters.items()))
                else:
                    self.instruction(st, index, block, out, lines); st.pc = index+1
            except ProgramError: raise
            except ValueError as error:
                where = self.where(st, index)
                raise ProgramError('%s: %s' % (where, error), index, where, str(error)) from error
        return out, None, lines, st

    def instruction(self, st, index, block, out, lines):
        kind = block['kind']; label = self.label(index); tag = dict(block_index=index)
        if st.calls:
            tag['call_path'] = functions.trace(st.calls); label = functions.location(tag['call_path'])+' / '+label
        if kind == 'movej':
            target = self.movej_target(block, st.angles, st.variables)
            out.append(dict(tag, kind='movej', name=label, target=target, speed=block.get('speed', 100)/100)); st.angles = target
        elif kind == 'movel':
            waypoints, line = self.movel(block, index, st.angles, st.variables); lines.append(line)
            for k, target in enumerate(waypoints):
                out.append(dict(tag, kind='movej', name='%s · tratto %d/%d' % (label, k+1, len(waypoints)),
                                target=target, speed=block.get('speed', 100)/100))
            st.angles = waypoints[-1]
        elif kind == 'pose':
            for step in self.m.pose_instructions(self.s.pose_index(block), index, start=st.angles):
                step.update(tag); step['name'] = label; out.append(step)
                if step['kind'] == 'movej': st.angles = step['target']
                if step['kind'] == 'grip': st.grip = step['command']
        elif kind == 'grip':
            out.append(dict(tag, kind='grip', name=label, command=block['command'], seconds=GRIP_SECONDS)); st.grip = block['command']
        elif kind == 'wait':
            left = block['seconds']
            while True:
                chunk = min(60., left); out.append(dict(tag, kind='wait', name=label, seconds=chunk)); left -= chunk
                if left <= 1e-9: break
        elif kind == 'note': out.append(dict(tag, kind='note', name=functions.location(tag['call_path'])+' / '+block['name'] if st.calls else block['name'], seconds=0.))
        elif kind == 'output':
            if block['output'] not in self.s.outputs: raise ValueError('uscita non definita: '+block['output'])
            out.append(dict(tag, kind='output', name=label, output=block['output'], value=block['output_value'], timeout=block['timeout']))
        elif kind == 'sensor':
            if block['sensor'] not in self.s.sensors: raise ValueError('sensore non definito: %s' % block['sensor'])
            out.append(dict(tag, kind='sensor', name=label, sensor=block['sensor'], expected=block['expected'], timeout=block['timeout']))

    # Branch tree ----------------------------------------------------------------------

    def build(self, start, grip, profile, evaluate_q, context, scenario):
        """Plan every branch; return the preview path as an ordinary plan plus the tree."""
        root = State(0, coordinates(start), grip, {}); index = {}; segments = []; queue = [root]; total = 0
        while queue:
            st = queue.pop(0); key = st.key()
            if key in index: continue
            if len(segments) >= MAX_SEGMENTS:
                raise ProgramError('Programma: oltre %d rami da verificare; riduci le condizioni dentro i cicli.' % MAX_SEGMENTS,
                                   st.pc if st.pc < len(self.blocks) else -1, 'programma', 'troppi rami')
            out, end, lines, last = self.segment(st)
            index[key] = len(segments)
            stages, samples = [], []
            if out:
                try:
                    plan = build_plan(st.angles, out, profile, evaluate_q, context, st.grip, **SEGMENT_LIMITS)
                except PlanError as error:
                    step = out[min(error.stage, len(out)-1)]; block = step.get('block_index', -1)
                    where = self.where(st.copy(calls=()), block).replace(self.label(block), step['name'], 1) if block >= 0 else 'programma'
                    raise ProgramError('%s: %s' % (where, error.detail), block, where, error.detail) from error
                stages, samples = plan['stages'], plan['samples']
                if plan['targets'] != last.angles: raise ProgramError('Programma: angoli finali del ramo incoerenti.', -1, 'programma', 'incoerenza interna')
            total += len(samples)
            if total > MAX_SAMPLES: raise ProgramError('Programma oltre %d campioni verificati: riduci ripetizioni o rami.' % MAX_SAMPLES, -1, 'programma', 'troppi campioni')
            segments.append(dict(id=len(segments), stages=stages, samples=samples, end=end, lines=lines,
                                 start=st.angles, grip=st.grip, via=[list(v) for v in st.via]))
            if end: queue.extend(end['states'])
        for segment in segments:
            if segment['end']:
                end = segment['end']; true, false = end.pop('states')
                end['next'] = [index[true.key()], index[false.key()]]
        return self.preview(segments, scenario)

    def outcome(self, end, scenario):
        """Branch shown in the preview: chosen by the operator, else current sensor values (missing = 0)."""
        chosen = scenario.get(str(end['block']))
        if isinstance(chosen, bool): return chosen
        env = dict(end['variables'])
        for name in end['sensors']:
            value = self.s.sensors[name]['value']; env[name] = 0 if value is None else value
        return bool(evaluate(parse(end['condition']), env))

    def preview(self, segments, scenario):
        stages, samples, lines, decisions = [], [], [], {}; now = 0.; current = segments[0]; path = []
        while True:
            path.append(current['id'])
            for stage in current['stages']:
                stage = dict(stage, start_time=stage['start_time']+now, end_time=stage['end_time']+now, segment=current['id'])
                stages.append(stage)
            samples.extend(dict(x, time=x['time']+now) for x in current['samples'])
            now += sum(s['duration'] for s in current['stages']); lines.extend(current['lines'])
            end = current['end']
            if not end: break
            result = self.outcome(end, scenario)
            entry = decisions.setdefault(end['block'], dict(block_index=end['block'], condition=end['condition'], preview=result, occurrences=0))
            entry['occurrences'] += 1
            current = segments[end['next'][0 if result else 1]]
        if not stages: raise ValueError('Nessuna istruzione abilitata nel programma.')
        checked = sum(len(s['samples']) for s in segments)
        tree = [dict(id=s['id'], stages=s['stages'], end=s['end'], start=s['start']) for s in segments]
        return dict(stages=stages, samples=samples, duration=now, path=path, lines=lines, tree=tree,
                    decisions=sorted(decisions.values(), key=lambda d: d['block_index']),
                    branches=len(segments), checked_samples=checked, targets=stages[-1]['targets'])

    def summary(self, plan, built):
        """Duration of every block on the preview path, MoveL lines and branch information."""
        blocks = {}
        for stage in plan['stages']:
            entry = blocks.setdefault(stage['block_index'], dict(index=stage['block_index'], start_time=stage['start_time'], duration=0., stages=0))
            entry['duration'] += stage['duration']; entry['stages'] += 1
        return dict(blocks=sorted(blocks.values(), key=lambda b: b['start_time']), lines=built['lines'], cartesian=self.cartesian,
                    decisions=built['decisions'], branches=built['branches'], checked_samples=built['checked_samples'])
