# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Shared MoveJ execution: runs exactly a previewed plan through the existing controller.

Each joint stage is one simultaneous group (`move_group`: limits, enabled axes,
speed budget, MULTI ACK/DONE, timeout and STOP generation). Gripper stages use
`servo`, waits honour pause and STOP. Completed groups are recorded on the trail,
so HOME returns along them. Any interruption leaves the commanded position at the
last completed stage; there is no automatic resume.
"""
import time

POSITION_MATCH = .005  # degrees, the controller's own rounding is 0.01°


def stage_start_matches(controller, stage):
    return all(abs(a-b) <= POSITION_MATCH for a, b in zip(controller.pos, stage['starts']))


def run_stage(c, stage, number, gen, read_sensor=None, write_output=None):
    """One planned stage; `number` (1-based) names it in errors."""
    if stage['kind'] == 'movej':
        if not stage['axes']: return
        scale = stage.get('speed', 1.)
        with c.lock:
            if gen != c.generation: raise ValueError('Interrotto')
            if not stage_start_matches(c, stage):
                raise ValueError('Posizione comandata diversa dal piano MoveJ al tratto %d: nessun impulso inviato.' % number)
            # The controller recomputes the group: it must be the previewed one, speeds included.
            profile = c.group_plan(list(stage['deltas']), scale=scale)
            if profile[3] != stage['requested'] or abs(profile[5]-stage['duration']) > 1e-9:
                raise ValueError('Velocità diverse dal piano MoveJ al tratto %d: nessun impulso inviato.' % number)
        c.move_group(list(stage['deltas']), gen, scale=scale)
        with c.lock:
            if any(abs(a-b) > POSITION_MATCH for a, b in zip(c.pos, stage['targets'])):
                raise ValueError('Tratto MoveJ %d terminato fuori dal piano: STOP.' % number)
    elif stage['kind'] == 'grip':
        c.servo(stage['command'], gen)
    elif stage['kind'] == 'wait':
        end = time.monotonic()+stage['duration']
        while time.monotonic() < end:
            c.wait_ready(gen); time.sleep(.03)
    elif stage['kind'] == 'note':
        c.log(stage['name'])
    elif stage['kind'] == 'output' and write_output:
        write_output(stage, gen)
    elif stage['kind'] == 'sensor' and read_sensor:
        # Wait until the input reports the expected value; a timeout stops the program.
        end = time.monotonic()+stage['timeout']
        while True:
            c.wait_ready(gen)
            try:
                if read_sensor(stage['sensor']) == stage['expected']: return
            except ValueError:
                pass  # no usable value yet: keep waiting until the timeout
            if time.monotonic() > end: raise ValueError('Timeout sensore: '+stage['sensor'])
            time.sleep(.03)
    else:
        raise ValueError('Istruzione MoveJ non eseguibile: '+stage['kind'])


def run_plan(controller, plan, gen, progress, gate=None):
    """Worker for Controller.spawn. `progress(index)` reports the active stage; `gate(index,
    stage)`, when given, may hold the worker before a stage (step-by-step programs)."""
    c = controller
    for index, stage in enumerate(plan['stages']):
        c.wait_ready(gen)
        if gate: gate(index, stage)
        progress(index)
        run_stage(c, stage, index+1, gen)
    c.wait_ready(gen); progress(len(plan['stages']))


def run_tree(controller, tree, gen, progress, gate, read_sensor, decide, write_output=None):
    """Worker for offline programs: run planned segments; at the end of a segment `decide(end)`
    reads the sensors and picks one of the two planned continuations. `progress(stage)` and
    `gate(stage)` receive stage dicts, which carry their block index."""
    c = controller; segment = tree[0]; number = 0
    while True:
        for stage in segment['stages']:
            number += 1; c.wait_ready(gen)
            gate(stage); progress(stage)
            run_stage(c, stage, number, gen, read_sensor, write_output)
        end = segment['end']
        if not end: break
        c.wait_ready(gen)
        segment = tree[end['next'][0 if decide(end) else 1]]
    c.wait_ready(gen); progress(None)
