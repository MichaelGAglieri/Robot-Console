# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Whole-program validation before execution. Simulation only, no controller calls.

Sequences connect active targets directly from the current position. HOME is
included only when explicitly requested. Each single-joint or simultaneous unit
is sampled at most every 1 degree per joint and checked against applied limits,
calibrated URDF limits and collision geometry.
"""
import math

AXES = 6  # controller channels, as in server.AXES

STEP_DEG = 1.


def units_between(trail, path):
    """Units unwound backwards, then units travelled forwards (follow_path semantics)."""
    from server import path_units
    previous, following = path_units(trail), path_units(path); common = 0
    while common < min(len(previous), len(following)) and previous[common] == following[common]: common += 1
    return [(u, True) for u in reversed(previous[common:])], [(u, False) for u in following[common:]]


class ProgramCheck:
    def __init__(self, studio, limit=200, collision_warnings=False):
        self.s = studio; self.c = studio.controller; self.issues = []; self.samples = 0; self.limit = limit
        self.seen = set(); self.notes = []; self.collision_warnings=collision_warnings
        # Limits never applied (all 0/0) would flag every sample: say it once and skip them.
        self.limits_set = any(lo != hi for lo, hi in self.c.limits)
        if not self.limits_set: self.notes.append('Limiti del controllore non applicati: controllati solo i limiti URDF e le collisioni.')

    def positions(self, angles, grip):
        s = self.s; result = s.preview.copy()
        for joint in s.independent():
            axis = s.mapping[joint['name']]
            if axis >= 0: result[joint['name']] = math.radians(angles[axis])
        result['__gripper'] = 1. if grip == 'apri' else 0.
        return result

    def report(self, where, detail, angles):
        key = (where, detail.split(' (')[0].split(':')[0])  # one message per leg and kind of problem
        if key in self.seen: return
        self.seen.add(key)
        if len(self.issues) < self.limit:
            self.issues.append(dict(where=where, detail=detail, angles=[round(v, 2) for v in angles]))

    def check_point(self, angles, grip, where):
        self.samples += 1; s = self.s
        for axis, (lo, hi) in enumerate(self.c.limits if self.limits_set else []):
            if not lo-.005 <= angles[axis] <= hi+.005:
                self.report(where, 'J%d fuori dai limiti applicati (%.2f°)' % (axis+1, angles[axis]), angles); return False
        positions = self.positions(angles, grip)
        for joint in s.independent():
            cal = s.calibration[joint['name']]; value = positions[joint['name']]*cal['sign']+cal['offset']
            if not joint['lower']-1e-6 <= value <= joint['upper']+1e-6:
                self.report(where, joint['name']+' fuori dai limiti URDF calibrati', angles); return False
        hits = s.collision_report(positions)
        if hits and self.collision_warnings:
            note='Interferenza modello (solo avviso): '+', '.join(hits[:3])
            if note not in self.notes and len(self.notes)<self.limit:self.notes.append(note)
        elif hits:
            self.report(where, 'interferenza: '+', '.join(hits[:3]), angles); return False
        return True

    def run_unit(self, angles, unit, reverse, grip, where):
        deltas = [0.]*AXES
        for step in unit: deltas[step['axis']] += -step['delta'] if reverse else step['delta']
        count = max(1, math.ceil(max(abs(d) for d in deltas)/STEP_DEG))
        start = angles[:]
        for k in range(1, count+1):
            point = [a+d*k/count for a, d in zip(start, deltas)]
            if not self.check_point(point, grip, where): break
        final=[a+d for a,d in zip(start,deltas)]
        self.check_point(final,grip,where)
        return final

    def travel(self, angles, trail, path, grip, where):
        backwards, forwards = units_between(trail, path)
        for unit, reverse in backwards+forwards:
            angles = self.run_unit(angles, unit, reverse, grip, where)
        return angles, [step.copy() for step in path]

    def sequence(self, operations, label, cycles=1, return_home=True, motion=None):
        """Replay pose and gripper operations in order, then HOME; a second cycle checks steady state."""
        from server import sequence_units
        angles = self.c.pos[:]; grip = self.c.grip
        if not self.check_point(angles, grip, 'posizione attuale'): return
        for cycle in range(cycles):
            prefix = '' if cycle == 0 else 'ciclo %d · ' % (cycle+1)
            for kind, index, item in operations:
                if kind == 'grip':
                    grip = item['command']
                    self.check_point(angles, grip, prefix+'pinza in '+label(index))
                    continue
                name = prefix+'%s · %s' % (label(index), item['name'])
                for unit,_ in sequence_units(angles,item['pos'],motion):angles=self.run_unit(angles,unit,False,grip,'verso '+name)
                if item.get('grip') in ('apri', 'chiudi'):
                    grip = item['grip']; self.check_point(angles, grip, 'pinza in '+name)
            if return_home:
                for unit,_ in sequence_units(angles,[0.]*AXES,motion):angles=self.run_unit(angles,unit,False,grip,prefix+'ritorno diretto a HOME')


def plan_report(studio):
    """MoveJ/MoveL programs are validated by planning them: the same plan the preview shows
    and the execution runs, sampled every 1° per joint against limits and collisions."""
    m = studio.movej; workcell = dict(studio.workcell)
    scenario = (m.plan or {}).get('scenario') or {}  # keep the branches chosen for the preview
    try: m.prepare(dict(source='program', scenario=scenario))
    except ValueError as error:
        problem = m.problem or dict(where='programma', detail=str(error), angles=list(studio.controller.pos))
        issue = dict(where=problem['where'], detail=problem['detail'], angles=[round(v, 2) for v in problem['angles']])
        return dict(source='program', ok=False, issues=[issue], samples=0, poses=0, cycles=1, workcell=workcell,
                    notes=['Programma MoveJ/MoveL: la pianificazione si ferma al primo blocco non realizzabile.'])
    plan = m.plan; kinds = {b['index']: studio.blocks[b['index']]['kind'] for b in plan['program']['blocks']}
    return dict(source='program', ok=True, issues=[], samples=plan['program']['checked_samples'], cycles=1, workcell=workcell,
                poses=sum(kind in ('movej', 'movel', 'pose') for kind in kinds.values()),
                notes=['Programma MoveJ/MoveL: validato con il piano dell’anteprima e dell’esecuzione, durata stimata %.1f s.' % plan['duration']]
                + (['Condizioni sui sensori: %d rami verificati, %d campioni in tutto.' % (plan['program']['branches'], plan['program']['checked_samples'])]
                   if plan['program']['branches'] > 1 else []))


def validate(studio, source, *, repeat=False, return_home=False, index=None, collision_warnings=False, motion=None):
    """Check direct targets and gripper state in execution order. Never commands the controller."""
    from program_plan import is_motion_program
    if source == 'program' and is_motion_program(studio.blocks): return plan_report(studio)
    c = studio.controller; check = ProgramCheck(studio,collision_warnings=collision_warnings and source in ('sequence','home','pose')); notes = []; operations = []
    if source == 'program':
        for index, block in studio.expanded_program():
            if block['kind'] == 'pose':
                try:pose = c.sequence[studio.pose_index(block)]
                except ValueError as error:check.report('blocco %d' % (index+1),str(error),c.pos);continue
                if pose.get('enabled', True): operations.append(('pose', index, pose))
            elif block['kind'] == 'grip': operations.append(('grip', index, block))
            elif block['kind'] == 'sensor': notes.append('Attese sensore: il robot resta fermo, nessun movimento da controllare.')
        label = lambda i: 'blocco %d' % (i+1)
    elif source == 'home':
        check.sequence([('pose',0,dict(name='HOME',pos=[0.]*AXES))],lambda i:'HOME',return_home=False,motion=motion)
        return dict(source=source,ok=not check.issues,issues=check.issues,samples=check.samples,poses=1,cycles=1,notes=check.notes,workcell=dict(studio.workcell))
    elif source == 'pose':
        if type(index)!=int or not 0<=index<len(c.sequence):raise ValueError('Posa non presente.')
        operations=[('pose',index,c.sequence[index])];label=lambda i:'posa %d'%(i+1)
    elif source == 'sequence':
        motion=c.require_sequence_motion()
        operations = [('pose', i, p) for i, p in enumerate(c.sequence) if p.get('enabled', True)]
        label = lambda i: 'posa %d' % (i+1)
    else: raise ValueError('Validazione: sorgente non valida.')
    if not operations: raise ValueError('Validazione: nessuna posa o azione pinza abilitata da controllare.')
    cycles = 2 if source == 'sequence' and repeat else 1
    check.sequence(operations, label, cycles, return_home=return_home,motion=motion)
    return dict(source=source, ok=not check.issues, issues=check.issues, samples=check.samples,
                poses=sum(kind == 'pose' for kind, _, _ in operations), cycles=cycles,
                notes=sorted(set(notes+check.notes)), workcell=dict(studio.workcell))
