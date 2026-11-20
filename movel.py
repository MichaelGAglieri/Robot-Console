# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""MoveL planning: a straight TCP line turned into the fewest joint-space segments.

Pure geometry, no serial or controller access. The line is sampled every
millimetre and solved with continuous IK (each point seeded by the previous one).
Consecutive samples are then merged greedily while the joint-linear motion that the
backend really executes (one simultaneous group per segment, angles rounded to
0.01°) keeps the TCP within the requested distance from the line. The result is a
list of waypoints for an ordinary MoveJ plan, plus measured deviations.
"""
import math
from ik5 import solve, change, column, norm, unreachable_reason, POSITION_TOL, SINGULAR

STEP = .001                     # 1 mm between IK samples
MAX_LENGTH = 2.                 # metres
JUMP_PER_STEP = math.radians(6)  # larger joint jumps for 1 mm mean a singularity or branch change


def quantize(chain, q):
    """Controller angles are commanded in hundredths of a degree."""
    result = dict(q)
    for name in chain.variables:
        result[name] = math.radians(round(math.degrees(q[name]), 2))
    return result


def distance_to_segment(point, a, b):
    ab = [y-x for x, y in zip(a, b)]; length = sum(v*v for v in ab)
    t = 0. if length < 1e-18 else max(0., min(1., sum((p-x)*v for p, x, v in zip(point, a, ab))/length))
    return norm([p-(x+t*v) for p, x, v in zip(point, a, ab)])


def segment_samples(chain, qa, qb):
    """Joint-linear interpolation between two waypoints, at most 0.25° per joint."""
    largest = max((abs(qb[n]-qa[n]) for n in chain.variables), default=0.)
    count = max(4, math.ceil(math.degrees(largest)/.25))
    for i in range(count+1):
        f = i/count; q = dict(qa)
        for n in chain.variables: q[n] = qa[n]+(qb[n]-qa[n])*f
        yield q


def deviation(chain, qa, qb, a, b):
    worst = 0.
    for q in segment_samples(chain, qa, qb):
        pose, _, _ = chain.forward(q); worst = max(worst, distance_to_segment(column(pose, 3), a, b))
    return worst


def plan_line(chain, q0, target, keep_orientation=True, tolerance=.0005, max_segments=64):
    """Waypoints (controller q, radians) from q0 to the straight line end `target` (base, m)."""
    if not chain.variables: raise ValueError('MoveL: nessun giunto disponibile per il calcolo.')
    start_pose, _, _ = chain.forward(q0); start = column(start_pose, 3)
    length = norm([b-a for a, b in zip(start, target)])
    if length < .0005: raise ValueError('MoveL: il punto di arrivo coincide con la posizione attuale.')
    if length > MAX_LENGTH: raise ValueError('MoveL: retta oltre 2 m.')
    axis = column(start_pose, 2) if keep_orientation else None
    roll = column(start_pose, 0) if keep_orientation else None
    steps = max(2, math.ceil(length/STEP)); fine = [dict(q0)]; worst_axis = worst_roll = 0.; sigma = 1.
    for k in range(1, steps+1):
        point = [a+(b-a)*k/steps for a, b in zip(start, target)]
        result = solve(chain, fine[-1], point, axis, roll, iterations=80)
        travelled = length*k/steps
        if result['position_error'] >= POSITION_TOL:
            reason, _, reach = unreachable_reason(chain, fine[-1], point, result)
            words = dict(reach='fuori portata', limits='limiti dei giunti', locked='giunti esclusi', workspace='nessuna soluzione continua')
            detail = ' (%s)' % ', '.join(result['at_limit']) if reason == 'limits' and result['at_limit'] else ''
            raise ValueError('MoveL: tratto irraggiungibile a %.1f mm dall’inizio: %s%s.' % (travelled*1000, words[reason], detail))
        jump = change(chain, fine[-1], result['positions'])
        if jump > JUMP_PER_STEP:
            raise ValueError('MoveL: a %.1f mm dall’inizio un giunto dovrebbe ruotare di %.1f° per 1 mm (singolarità o cambio di configurazione).' % (travelled*1000, math.degrees(jump)))
        worst_axis = max(worst_axis, result['axis_error'] or 0.); worst_roll = max(worst_roll, result['roll_error'] or 0.)
        sigma = min(sigma, result['sigma']); fine.append(result['positions'])
    # Greedy merge: double the reach, then bisect, keeping the executed path within tolerance.
    waypoints = [quantize(chain, fine[0])]; index = 0; worst = 0.
    while index < steps:
        def ok(j):
            return deviation(chain, waypoints[-1], quantize(chain, fine[j]), start, target) <= tolerance
        if not ok(index+1):
            raise ValueError('MoveL: tolleranza %.3f mm non rispettabile a %.1f mm dall’inizio con angoli arrotondati a 0,01°; aumenta la tolleranza o modifica il percorso.'
                             % (tolerance*1000, length*(index+1)/steps*1000))
        good, probe = index+1, 1
        while index+probe*2 <= steps and ok(index+probe*2): good = index+probe*2; probe *= 2
        low, high = good, min(steps, index+probe*2)
        while high-low > 1:
            middle = (low+high)//2
            if ok(middle): low = middle
            else: high = middle
        good = low
        worst = max(worst, deviation(chain, waypoints[-1], quantize(chain, fine[good]), start, target))
        waypoints.append(quantize(chain, fine[good])); index = good
        if len(waypoints)-1 > max_segments:
            raise ValueError('MoveL: servono più di %d tratti con questa tolleranza; aumentala o accorcia la retta.' % max_segments)
    end_pose, _, _ = chain.forward(waypoints[-1])
    end_error = norm([a-b for a, b in zip(column(end_pose, 3), target)])
    return dict(waypoints=waypoints, length=length, segments=len(waypoints)-1, max_deviation=worst,
                end_error=end_error, axis_error=worst_axis if keep_orientation else None,
                roll_error=worst_roll if keep_orientation else None, singular=sigma < SINGULAR,
                tolerance=tolerance, start=start, target=list(target))
