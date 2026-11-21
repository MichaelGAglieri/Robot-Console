# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Bounded, read-only MoveJ plans. No serial, threads or execution capability.

The caller supplies the existing simultaneous profile and geometry evaluator.
Joint coordinates are commanded degrees; positions returned by geometry are m.
"""
import math
import uuid


def coordinates(value):
    if not isinstance(value, list) or len(value) != 6 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 360 for v in value):
        raise ValueError('Servono sei angoli assoluti validi da −360° a +360°.')
    return [round(v, 2) for v in value]


def fraction_time(s, speed, acceleration, duration):
    peak = min(speed, math.sqrt(acceleration)); ramp = peak / acceleration
    distance = .5 * acceleration * ramp * ramp
    if s <= distance: return math.sqrt(2 * s / acceleration)
    if s >= 1 - distance: return duration - math.sqrt(2 * (1 - s) / acceleration)
    return ramp + (s - distance) / peak


class PlanError(ValueError):
    """A planning failure tied to one stage (index into the instructions) and its joint angles."""

    def __init__(self, message, stage, angles=None, detail=None):
        super().__init__(message); self.stage = stage; self.angles = angles; self.detail = detail or message


def build_plan(start, instructions, profile, evaluate, context, grip='non comandata', *,
               max_instructions=200, max_moves=64, max_samples=4096):
    """Stages and 1° samples for the instructions. `profile(delta, starts[, scale])` is the
    controller's group profile; an instruction with `speed` (0.1–1) scales the joint speeds."""
    start = coordinates(start)
    if not instructions or len(instructions) > max_instructions:
        raise ValueError('Anteprima MoveJ: servono da 1 a %d istruzioni.' % max_instructions)
    initial_grip = grip
    stages, samples = [], []; now = 0.; current = start[:]; moves = 0

    def sample(q, stamp, stage):
        if len(samples) >= max_samples: raise PlanError('Anteprima oltre %d campioni: riduci il programma.' % max_samples, stage, q)
        tcp, collisions = evaluate(q, grip)
        if collisions:
            raise PlanError('Interferenza MoveJ al tratto %d (%.2f s): %s' % (stage + 1, stamp, ', '.join(collisions[:3])), stage, q,
                            'interferenza a %.2f s: %s' % (stamp, ', '.join(collisions[:3])))
        samples.append(dict(time=stamp, q=q[:], tcp=tcp))

    sample(current, 0., 0)
    for instruction in instructions:
        kind = instruction['kind']; name = str(instruction.get('name', kind))[:100]
        stage = dict(kind=kind, name=name, block_index=instruction.get('block_index', -1), start_time=now, starts=current[:])
        if instruction.get('call_path'): stage['call_path'] = instruction['call_path']
        try:
            if kind == 'movej':
                moves += 1
                if moves > max_moves: raise ValueError('Massimo %d tratti MoveJ per anteprima.' % max_moves)
                target = coordinates(instruction['target']); delta = [round(b-a, 2) for a, b in zip(current, target)]
                scale = instruction.get('speed', 1.); stage['speed'] = scale
                if any(delta):
                    d, target, axes, requested, effective, duration, speed, acceleration = (
                        profile(delta, current) if scale == 1. else profile(delta, current, scale))
                    stage.update(targets=target, deltas=d, axes=axes, requested=requested, effective=effective,
                                 peaks=[abs(v)*min(speed, math.sqrt(acceleration)) for v in d],
                                 duration=duration, path_speed=speed, path_acceleration=acceleration)
                    count = max(1, math.ceil(max(abs(v) for v in d)))
                    for i in range(1, count+1):
                        fraction = i/count
                        q = [a + v*fraction for a, v in zip(current, d)]
                        sample(q, now+fraction_time(fraction, speed, acceleration, duration), len(stages))
                    current = target[:]
                else:
                    stage.update(targets=current[:], deltas=delta, axes=[], requested=[], effective=[0.]*6,
                                 peaks=[0.]*6, duration=0., path_speed=0., path_acceleration=0.)
            elif kind in ('wait', 'grip', 'note'):
                duration = instruction.get('seconds', 0.)
                if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 <= duration <= 60:
                    raise ValueError('Pausa MoveJ non valida.')
                if kind == 'grip' and instruction.get('command') not in ('apri', 'chiudi'):
                    raise ValueError('Comando pinza MoveJ non valido.')
                stage.update(duration=duration, targets=current[:], command=instruction.get('command', ''))
                if kind == 'grip':
                    grip = instruction['command']; sample(current, now+duration, len(stages))
            elif kind == 'output':
                stage.update(duration=0., targets=current[:], output=instruction['output'], value=instruction['value'], timeout=instruction['timeout'])
            elif kind == 'sensor':
                # Waiting time is unknown: counted as zero in the estimate, bounded by the timeout.
                stage.update(duration=0., targets=current[:], sensor=instruction['sensor'],
                             expected=instruction['expected'], timeout=instruction['timeout'])
            else:
                raise ValueError('L’anteprima MoveJ non simula attese sensore o istruzioni sconosciute.')
        except PlanError: raise
        except ValueError as error: raise PlanError(str(error), len(stages), current[:]) from error
        now += stage['duration']
        if now > 3600: raise PlanError('Anteprima oltre un’ora: riduci il programma.', len(stages), current[:])
        stage['end_time'] = now; stages.append(stage)
    return dict(id=uuid.uuid4().hex, context=context, starts=start, targets=current, stages=stages,
                samples=samples, duration=now, initial_grip=initial_grip, sample_count=len(samples),
                max_joint_step_deg=1., preview_only=True)


def position_at(plan, elapsed, progress):
    elapsed = max(0., min(plan['duration'], elapsed)); current = plan['starts'][:]; grip = plan['initial_grip']
    for index, stage in enumerate(plan['stages']):
        if stage['kind'] == 'grip' and elapsed >= stage['start_time']: grip = stage['command']
        if elapsed >= stage['end_time']:
            current = stage['targets'][:]; continue
        if stage['kind'] == 'movej' and stage['duration'] > 0:
            fraction = progress(1., stage['path_speed'], elapsed-stage['start_time'], stage['path_acceleration'])
            current = [a+d*fraction for a, d in zip(stage['starts'], stage['deltas'])]
        return current, grip, index
    return current, grip, len(plan['stages'])-1
