#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Schematic DOC model shipped with Robot Console (GPL, no third-party geometry).

Every display mesh of the DOC URDF is replaced by simple primitives (capsules, discs and
boxes) whose sizes were measured once on the locally generated EB-15 model. Only the
numbers in models/doc5/schematic.json are kept: same joint frames, same mesh names and
colours, similar collision envelope. The detailed model is generated locally with
eb15_model.py.

  python3 scripts/schematic_model.py            build models/doc5/meshes from the JSON
  python3 scripts/schematic_model.py --measure SOURCES...   re-measure (needs numpy and the
                                                 original EB-15/EBG-30 zip files or folders)
"""
import json, math, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL = ROOT / 'models/doc5'
SPEC = MODEL / 'schematic.json'
HEADER = b'Robot Console schematic DOC model - GPL-3.0-only'.ljust(80, b' ')
SEGMENTS = 28


def sub(a, b): return [x - y for x, y in zip(a, b)]
def add(a, b, s=1.): return [x + y * s for x, y in zip(a, b)]
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def norm(a):
    length = math.sqrt(dot(a, a)) or 1.
    return [x / length for x in a]


def frame(axis):
    axis = norm(axis)
    helper = [1., 0., 0.] if abs(axis[0]) < .9 else [0., 1., 0.]
    u = norm(cross(axis, helper))
    return u, cross(axis, u), axis


def capsule(a, b, r):
    """Closed triangle mesh: cylinder between a and b with hemispherical caps."""
    axis = sub(b, a)
    if dot(axis, axis) < 1e-12: axis = [0., 0., 1.]
    u, v, w = frame(axis)
    rings = []
    half = SEGMENTS // 4
    for i in range(half + 1):  # cap at a, from the pole to the equator
        phi = math.pi / 2 * (1 - i / half)
        rings.append((a, -math.sin(phi), math.cos(phi)))
    for i in range(half + 1):  # cap at b
        phi = math.pi / 2 * i / half
        rings.append((b, math.sin(phi), math.cos(phi)))
    points = []
    for centre, along, radial in rings:
        row = []
        for k in range(SEGMENTS):
            t = 2 * math.pi * k / SEGMENTS
            offset = add(add([0., 0., 0.], u, r * radial * math.cos(t)), v, r * radial * math.sin(t))
            row.append(add(add(centre, w, r * along), offset))
        points.append(row)
    return _grid(points)


def disc(centre, axis, radius, height):
    u, v, w = frame(axis)
    bottom, top = add(centre, w, -height / 2), add(centre, w, height / 2)
    ring = lambda c: [add(add(c, u, radius * math.cos(2 * math.pi * k / SEGMENTS)), v, radius * math.sin(2 * math.pi * k / SEGMENTS)) for k in range(SEGMENTS)]
    rows = [[bottom] * SEGMENTS, ring(bottom), ring(top), [top] * SEGMENTS]
    return _grid(rows)


def box(centre, axes, half):
    tris = []
    corners = lambda sx, sy, sz: add(add(add(centre, axes[0], sx * half[0]), axes[1], sy * half[1]), axes[2], sz * half[2])
    faces = [((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)), ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)),
             ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)),
             ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), ((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1))]
    for face in faces:
        p = [corners(*c) for c in face]
        tris += [(p[0], p[1], p[2]), (p[0], p[2], p[3])]
    return _outward(tris, centre)


def _grid(rows):
    tris = []
    for i in range(len(rows) - 1):
        for k in range(SEGMENTS):
            a, b = rows[i][k], rows[i][(k + 1) % SEGMENTS]
            c, d = rows[i + 1][k], rows[i + 1][(k + 1) % SEGMENTS]
            tris += [(a, b, d), (a, d, c)]
    centre = [sum(p[i] for row in rows for p in row) / sum(len(r) for r in rows) for i in range(3)]
    return _outward([t for t in tris if _area(t) > 1e-14], centre)


def _area(t):
    c = cross(sub(t[1], t[0]), sub(t[2], t[0]))
    return math.sqrt(dot(c, c)) / 2


def _outward(tris, centre):
    out = []
    for t in tris:
        n = cross(sub(t[1], t[0]), sub(t[2], t[0]))
        mid = [sum(p[i] for p in t) / 3 for i in range(3)]
        out.append(t if dot(n, sub(mid, centre)) >= 0 else (t[0], t[2], t[1]))
    return out


def stl(tris):
    raw = bytearray(HEADER + struct.pack('<I', len(tris)))
    for t in tris:
        n = norm(cross(sub(t[1], t[0]), sub(t[2], t[0])))
        raw += struct.pack('<12fH', *n, *t[0], *t[1], *t[2], 0)
    return bytes(raw)


def build():
    spec = json.loads(SPEC.read_text())
    (MODEL / 'meshes').mkdir(exist_ok=True)
    for old in (MODEL / 'meshes').glob('*.stl'):
        old.unlink()
    for name, shapes in spec['meshes'].items():
        tris = []
        for s in shapes:
            if s['kind'] == 'capsule': tris += capsule(s['a'], s['b'], s['r'])
            elif s['kind'] == 'disc': tris += disc(s['centre'], s['axis'], s['r'], s['h'])
            else: tris += box(s['centre'], s['axes'], s['half'])
        (MODEL / 'meshes' / name).write_bytes(stl(tris))
    import hashlib
    provenance = json.loads((MODEL / 'provenance.json').read_text())
    provenance['meshes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((MODEL / 'meshes').glob('*.stl'))}
    (MODEL / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return len(spec['meshes'])


def measure(sources):
    """Fit one primitive per original part (smallest volume of box, cylinder, capsules)."""
    import numpy as np
    import eb15_model
    from collision import fit_capsule, fit_capsules
    data = eb15_model.assembly()
    found = eb15_model.find_sources(sources)
    origin = {'base_link': np.zeros(3)}
    for i in range(1, 6):
        origin['link_%d' % i] = np.array(data['joints']['J%d' % i]['origin'], float)
    for k in (1, 2, 3):
        origin['lab_finger_%d' % k] = origin['link_5']
    r6 = lambda v: [round(float(x), 5) for x in v]
    result = {}
    for part in data['parts']:
        link = eb15_model.LINK_OF[part['link']]
        name = '%s_%s.stl' % (link, data['color_names'][part['color']])
        raw = eb15_model._load(np, found[part['file']]).reshape(-1, 3)
        points = (raw @ np.array(part['R']).T + np.array(part['t']) - origin[link]) / 1000.0
        points = np.unique(np.round(points, 5), axis=0)
        _, vectors = np.linalg.eigh(np.cov((points - points.mean(0)).T))
        axes = vectors[:, ::-1].T
        proj = points @ axes.T
        low, high = np.percentile(proj, .5, axis=0), np.percentile(proj, 99.5, axis=0)
        extent = high - low
        mid = axes.T @ ((low + high) / 2)
        options = [(float(np.prod(extent)), dict(kind='box', centre=r6(mid), axes=[r6(a) for a in axes], half=r6(extent / 2)))]
        for k in range(3):
            i, j = [x for x in range(3) if x != k]
            radial = np.hypot(proj[:, i] - (low[i] + high[i]) / 2, proj[:, j] - (low[j] + high[j]) / 2)
            radius = float(np.percentile(radial, 99))
            options.append((math.pi * radius ** 2 * extent[k], dict(kind='disc', centre=r6(mid), axis=r6(axes[k]), r=round(radius, 5), h=round(float(extent[k]), 5))))
        step = max(1, len(points) // 4000)
        sample = points[::step].tolist()
        single = fit_capsule(sample)
        for capsules, penalty in (([single] if single else [], 1.0), (fit_capsules(sample), 1.35)):
            if capsules:
                # Several short capsules look like beads: they win only when clearly tighter.
                volume = sum(math.pi * c['r'] ** 2 * math.dist(c['a'], c['b']) + 4 / 3 * math.pi * c['r'] ** 3 for c in capsules)
                options.append((volume * (penalty if len(capsules) > 1 else 1.0),
                                [dict(kind='capsule', a=r6(c['a']), b=r6(c['b']), r=round(c['r'], 5)) for c in capsules]))
        best = min(options, key=lambda o: o[0])[1]
        result.setdefault(name, []).extend(best if isinstance(best, list) else [best])
    SPEC.write_text(json.dumps(dict(description='One primitive per DOC part (metres, link frames), measured once on the '
                                    'original EB-15/EBG-30 parts; numbers only, GPL-3.0-only. Rebuild with scripts/schematic_model.py.',
                                    meshes=dict(sorted(result.items()))), indent=1) + '\n')
    return len(data['parts'])


if __name__ == '__main__':
    if sys.argv[1:2] == ['--measure']:
        print('measured', measure(sys.argv[2:]), 'parts')
    print('built', build(), 'schematic meshes in', MODEL / 'meshes')
