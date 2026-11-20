# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Simplified collision geometry for any imported arm. Pure geometry, no I/O but mesh reads.

Every link with visual geometry gets up to four capsules: its vertices are sliced
along their principal axis and each slice gets a capsule whose radius is the 95th
percentile of the distance from that axis (the margin covers the rest). Slices keep
joint housings from inflating a whole link. Links without geometry keep the previous conservative check: the
segment between joint origins with a 25 mm radius. Checks: link against link (pairs
that are adjacent, rigidly joined or already touching in the reference pose are
skipped), link against the workcell boxes and, optionally, against the table plane
z = 0. Sampling and capsule fitting are approximations and are reported as such.
"""
import math
import struct
from pathlib import Path
from robot_model import frames, origin, multiply

FALLBACK_RADIUS = .025
REST_GAP = .015
POINT_LIMIT = 3000
_points = {}


def dot(a, b): return sum(x*y for x, y in zip(a, b))
def sub(a, b): return [x-y for x, y in zip(a, b)]
def add(a, b, s=1.): return [x+y*s for x, y in zip(a, b)]


def mesh_points(path):
    """Vertices of an STL (binary or ASCII) or OBJ file, subsampled; [] when unreadable."""
    if path in _points: return _points[path]
    points = []
    try:
        data = Path(path).read_bytes()
        if path.lower().endswith('.obj'):
            for line in data.decode(errors='replace').splitlines():
                if line.startswith('v '):
                    points.append([float(v) for v in line.split()[1:4]])
        elif len(data) >= 84 and 84+50*struct.unpack('<I', data[80:84])[0] == len(data):
            count = struct.unpack('<I', data[80:84])[0]
            for i in range(count):
                values = struct.unpack('<9f', data[84+50*i+12:84+50*i+48])
                points.extend([list(values[0:3]), list(values[3:6]), list(values[6:9])])
        else:
            for line in data.decode(errors='replace').splitlines():
                parts = line.split()
                if parts[:1] == ['vertex']: points.append([float(v) for v in parts[1:4]])
    except (OSError, ValueError, struct.error):
        points = []
    if len(points) > POINT_LIMIT: points = points[::math.ceil(len(points)/POINT_LIMIT)]
    _points[path] = points
    return points


def visual_points(visual):
    kind, size = visual['kind'], visual['size']
    if kind == 'mesh': local = [[p[i]*size[i] for i in range(3)] for p in mesh_points(visual.get('mesh') or '')]
    elif kind == 'box': local = [[sx*size[0]/2, sy*size[1]/2, sz*size[2]/2] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    elif kind == 'cylinder':
        r, h = size[0], size[1]
        local = [[r*math.cos(a*math.pi/8), r*math.sin(a*math.pi/8), z*h/2] for a in range(16) for z in (-1, 1)]
    elif kind == 'sphere': local = [[s*size[0] if i == k else 0. for i in range(3)] for k in range(3) for s in (-1, 1)]
    else: local = []
    t = origin(visual['xyz'], visual['rpy'])
    return [[sum(t[i][k]*p[k] for k in range(3))+t[i][3] for i in range(3)] for p in local]


def fit_capsule(points):
    if len(points) < 4: return None
    n = len(points); c = [sum(p[i] for p in points)/n for i in range(3)]
    cov = [[sum((p[i]-c[i])*(p[j]-c[j]) for p in points)/n for j in range(3)] for i in range(3)]
    axis = [1., .7, .3]
    for _ in range(40):
        axis = [dot(row, axis) for row in cov]; length = math.sqrt(dot(axis, axis))
        if length < 1e-15: axis = [0., 0., 1.]; break
        axis = [v/length for v in axis]
    t = [dot(sub(p, c), axis) for p in points]
    radial = sorted(math.sqrt(max(0., dot(sub(p, c), sub(p, c))-ti*ti)) for p, ti in zip(points, t))
    radius = radial[min(len(radial)-1, int(.95*len(radial)))]
    low, high = min(t)+radius, max(t)-radius
    if low > high: low = high = (min(t)+max(t))/2
    return dict(a=add(c, axis, low), b=add(c, axis, high), r=max(radius, .002))


def principal_axis(points):
    n = len(points); c = [sum(p[i] for p in points)/n for i in range(3)]
    cov = [[sum((p[i]-c[i])*(p[j]-c[j]) for p in points)/n for j in range(3)] for i in range(3)]
    axis = [1., .7, .3]
    for _ in range(40):
        axis = [dot(row, axis) for row in cov]; length = math.sqrt(dot(axis, axis))
        if length < 1e-15: return c, [0., 0., 1.]
        axis = [v/length for v in axis]
    return c, axis


def fit_capsules(points, slices=4):
    """One capsule per slice along the principal axis; long thin links get more slices."""
    whole = fit_capsule(points)
    if not whole: return []
    c, axis = principal_axis(points); t = [dot(sub(p, c), axis) for p in points]
    span = max(t)-min(t); count = max(1, min(slices, round(span/max(2*whole['r'], 1e-6)+.5)))
    if count == 1: return [whole]
    result = []
    for k in range(count):
        low, high = min(t)+span*k/count, min(t)+span*(k+1)/count
        part = [p for p, ti in zip(points, t) if low-1e-9 <= ti <= high+1e-9]
        if len(part) < 4: continue
        pc = [sum(p[i] for p in part)/len(part) for i in range(3)]
        radial = sorted(math.sqrt(max(0., dot(sub(p, pc), sub(p, pc))-dot(sub(p, pc), axis)**2)) for p in part)
        r = max(radial[min(len(radial)-1, int(.95*len(radial)))], .002)
        tc = dot(sub(pc, c), axis); a, b = max(low+r, tc-(high-low)/2), min(high-r, tc+(high-low)/2)
        if a > b: a = b = (low+high)/2
        off = sub(pc, add(c, axis, tc))
        result.append(dict(a=add(add(c, axis, a), off), b=add(add(c, axis, b), off), r=r))
    return result or [whole]


def segment_distance(p1, q1, p2, q2):
    """Closest distance between two segments (Ericson, Real-Time Collision Detection)."""
    d1, d2, r = sub(q1, p1), sub(q2, p2), sub(p1, p2)
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    if a < 1e-15 and e < 1e-15: return math.sqrt(dot(r, r))
    if a < 1e-15: s, t = 0., min(1., max(0., f/e))
    else:
        c = dot(d1, r)
        if e < 1e-15: t, s = 0., min(1., max(0., -c/a))
        else:
            b = dot(d1, d2); denom = a*e-b*b
            s = min(1., max(0., (b*f-c*e)/denom)) if denom > 1e-15 else 0.
            t = (b*s+f)/e
            if t < 0: t, s = 0., min(1., max(0., -c/a))
            elif t > 1: t, s = 1., min(1., max(0., (b-c)/a))
    w = sub(add(p1, d1, s), add(p2, d2, t)); return math.sqrt(dot(w, w))


def box_distance(a, b, box, radius):
    """Distance from a segment to an axis-aligned box, sampled finer than the capsule radius."""
    lo = [box['center'][i]-box['size'][i]/2 for i in range(3)]; hi = [box['center'][i]+box['size'][i]/2 for i in range(3)]
    length = math.sqrt(dot(sub(b, a), sub(b, a))); count = max(1, math.ceil(length/max(.002, radius/2)))
    best = float('inf')
    for k in range(count+1):
        p = add(a, sub(b, a), k/count)
        q = [max(lo[i], min(hi[i], p[i])) for i in range(3)]
        best = min(best, math.sqrt(dot(sub(p, q), sub(p, q))))
    return best


class Geometry:
    """Collision bodies of one model, with the pairs that are never checked."""

    def __init__(self, model):
        self.model = model; parent_of = {}; self.bodies = []
        groups = {link['name']: link['name'] for link in model['links']}
        def find(x):
            while groups[x] != x: x = groups[x]
            return x
        for joint in model['joints']:
            parent_of[joint['child']] = joint['parent']
            if joint['kind'] == 'fixed': groups[find(joint['child'])] = find(joint['parent'])
        for link in model['links']:
            points = [p for visual in link['visuals'] for p in visual_points(visual)]
            for capsule in fit_capsules(points):
                self.bodies.append(dict(name=link['name'], link=link['name'], **capsule))
        fitted = {b['link'] for b in self.bodies}
        for joint in model['joints']:
            if joint['child'] in fitted: continue
            # Previous behaviour for links without geometry: joint segment, 25 mm.
            self.bodies.append(dict(name=joint['child'], link=joint['parent'], a=[0., 0., 0.], b=list(joint['xyz']), r=FALLBACK_RADIUS))
        self.group = {b['name']: find(b['link']) for b in self.bodies}
        self.root_group = find(model['root'])
        adjacent = set()
        for joint in model['joints']:
            adjacent.add(frozenset((find(joint['parent']), find(joint['child']))))
        # Gripper fingers belong to one mechanism: never checked against each other.
        fingers = {j['child'] for j in model['joints'] if j['name'] in (model.get('gripper') or {}).get('joints', [])}
        self.pairs = []
        reference = self.world({}, None); close = set()
        for i in range(len(self.bodies)):
            for j in range(i+1, len(self.bodies)):
                if self.clearance(reference[i], reference[j]) <= REST_GAP:
                    close.add(frozenset((self.group[self.bodies[i]['name']], self.group[self.bodies[j]['name']])))
        for i in range(len(self.bodies)):
            for j in range(i+1, len(self.bodies)):
                a, b = self.bodies[i], self.bodies[j]; ga, gb = self.group[a['name']], self.group[b['name']]
                if ga == gb or frozenset((ga, gb)) in adjacent or (a['link'] in fingers and b['link'] in fingers): continue
                # Links within REST_GAP of each other in the reference pose are close by design
                # (joint housings around an axis); their interaction is left to the joint limits.
                if frozenset((ga, gb)) in close: continue
                self.pairs.append((i, j))
        self.floor_checked = {i for i, body in enumerate(reference)
                              if self.group[self.bodies[i]['name']] != self.root_group and min(body[0][2], body[1][2])-body[2] > REST_GAP}

    def world(self, positions, calibration):
        f = frames(self.model, positions, calibration); result = []
        for b in self.bodies:
            m = f[b['link']]
            point = lambda p: [sum(m[i][k]*p[k] for k in range(3))+m[i][3] for i in range(3)]
            result.append((point(b['a']), point(b['b']), b['r']))
        return result

    @staticmethod
    def clearance(x, y): return segment_distance(x[0], x[1], y[0], y[1])-x[2]-y[2]

    def check(self, positions, calibration=None, obstacles=(), floor=False, margin=.01):
        """Interferences as dicts: kind self/obstacle/floor, the two names and the clearance (m)."""
        world = self.world(positions, calibration); found = []
        for i, j in self.pairs:
            gap = self.clearance(world[i], world[j])
            if gap < margin: found.append(dict(kind='self', a=self.bodies[i]['name'], b=self.bodies[j]['name'], clearance=gap))
        for i, (a, b, r) in enumerate(world):
            for box in obstacles:
                gap = box_distance(a, b, box, r)-r
                if gap < margin: found.append(dict(kind='obstacle', a=self.bodies[i]['name'], b=box['name'], clearance=gap))
            if floor and i in self.floor_checked:
                gap = min(a[2], b[2])-r
                if gap < margin: found.append(dict(kind='floor', a=self.bodies[i]['name'], b='piano di lavoro', clearance=gap))
        worst = {}
        for hit in found:
            key = (hit['kind'], hit['a'], hit['b'])
            if key not in worst or hit['clearance'] < worst[key]['clearance']: worst[key] = hit
        return list(worst.values())
