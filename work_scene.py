# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Base-relative work frames and Cartesian target metadata. No motion authority.

Translations are metres; fixed-axis roll/pitch/yaw are radians, composed as
Rz(yaw) Ry(pitch) Rx(roll), using the same transform convention as the URDF.
The first increment supports one level of work frames under the robot base.
"""
import copy
import math
import re
from robot_model import origin, multiply, number


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError('Identificatore della scena non valido.')
    return value


def label(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80 or any(ord(c) < 32 for c in value):
        raise ValueError('Nome della scena richiesto, massimo 80 caratteri.')
    return value.strip()


def pose(value):
    if not isinstance(value, dict):
        raise ValueError('Posa della scena non valida.')
    result = {}
    for key, bound in (('xyz', 10.), ('rpy', 2 * math.pi)):
        values = value.get(key)
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError('Servono tre coordinate e tre angoli per la posa.')
        result[key] = [number(v, -bound, bound) for v in values]
    return result


def validate_scene(work_frames, targets):
    if not isinstance(work_frames, list) or len(work_frames) > 32:
        raise ValueError('Massimo 32 riferimenti di lavoro.')
    if not isinstance(targets, list) or len(targets) > 256:
        raise ValueError('Massimo 256 target cartesiani.')
    checked_frames, checked_targets = [], []
    ids, names = {'base'}, set()
    for raw in work_frames:
        if not isinstance(raw, dict):
            raise ValueError('Riferimento di lavoro non valido.')
        key, name = identifier(raw.get('id')), label(raw.get('name'))
        if key in ids or name.casefold() in names or raw.get('parent') != 'base':
            raise ValueError('Riferimento duplicato o non relativo alla base robot.')
        ids.add(key); names.add(name.casefold())
        checked_frames.append(dict(id=key, name=name, parent='base', **pose(raw)))
    frame_ids = ids.copy()
    names = set()
    for raw in targets:
        if not isinstance(raw, dict):
            raise ValueError('Target cartesiano non valido.')
        key, name = identifier(raw.get('id')), label(raw.get('name'))
        frame_id = identifier(raw.get('frame_id'))
        if key in ids or name.casefold() in names or frame_id not in frame_ids:
            raise ValueError('Target duplicato o riferimento del target non presente.')
        ids.add(key); names.add(name.casefold())
        checked_targets.append(dict(id=key, name=name, frame_id=frame_id, **pose(raw)))
    return checked_frames, checked_targets


def scene_state(work_frames, targets):
    """Derive matrices, never trust persisted matrices or cached base positions."""
    base = dict(id='base', name='Base robot', parent='', xyz=[0., 0., 0.], rpy=[0., 0., 0.])
    entries = [base, *copy.deepcopy(work_frames)]
    matrices = {entry['id']: origin(entry['xyz'], entry['rpy']) for entry in entries}
    for entry in entries:
        entry['matrix'] = [v for row in matrices[entry['id']] for v in row]
    resolved = []
    for target in targets:
        matrix = multiply(matrices[target['frame_id']], origin(target['xyz'], target['rpy']))
        resolved.append(dict(**copy.deepcopy(target), matrix=[v for row in matrix for v in row],
                             xyz_base=[matrix[i][3] for i in range(3)]))
    return entries, resolved
