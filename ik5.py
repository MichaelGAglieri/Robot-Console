# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Prioritized inverse kinematics and Cartesian jog for the Studio preview.

Pure geometry on a parsed URDF: no serial port, controller or motion authority.
Joint values are the controller-side radians used by Studio (URDF angle =
q*sign+offset). Poses are metres in the robot base frame.

Priorities: 1) TCP position, 2) tool axis (local +Z, out of the flange),
3) rotation about that axis (local +X). A five-axis arm such as the DOC cannot
hold every tool direction: the residual is measured and reported, never hidden.
"""
import math
from robot_model import origin, multiply, rotation

POSITION_TOL = 1e-4                 # 0.1 mm: acceptance
PRECISION = 1e-6                    # 1 µm: iteration target, so repeated jog steps do not drift
AXIS_TOL = math.radians(.05)
ROLL_TOL = math.radians(.1)
ORIENTATION_WARN = math.radians(.5)  # residual worth telling the operator
SINGULAR = .02                      # m/rad: 1° moves the TCP < 0.35 mm in some direction
JOG_JUMP = math.radians(15)


def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def norm(a): return math.sqrt(dot(a, a))
def column(m, k): return [m[i][k] for i in range(3)]
def apply(m, v): return [dot(m[i][:3], v) for i in range(3)]


def clamp(vector, limit):
    length = norm(vector)
    return [v*limit/length for v in vector] if length > limit else list(vector)


def inverse(a):
    """Gauss-Jordan inverse of a small square matrix; None when singular."""
    n = len(a); m = [row[:]+[float(i == k) for k in range(n)] for i, row in enumerate(a)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda k: abs(m[k][i]))
        if abs(m[pivot][i]) < 1e-15: return None
        m[i], m[pivot] = m[pivot], m[i]; d = m[i][i]; m[i] = [v/d for v in m[i]]
        for k in range(n):
            if k != i and m[k][i]:
                f = m[k][i]; m[k] = [v-f*w for v, w in zip(m[k], m[i])]
    return [row[n:] for row in m]


def damped_pinv(a, damping):
    """A^T (A A^T + λ²I)^-1 for an m×n matrix with m ≤ 3."""
    rows = len(a)
    gram = [[dot(a[i], a[k])+(damping*damping if i == k else 0) for k in range(rows)] for i in range(rows)]
    inv = inverse(gram) or [[0.]*rows for _ in range(rows)]
    return [[sum(a[r][j]*inv[r][c] for r in range(rows)) for c in range(rows)] for j in range(len(a[0]))]


def smallest_singular(a):
    """Smallest singular value of a 3×n matrix (Jacobi on the 3×3 Gram matrix)."""
    g = [[dot(a[i], a[k]) for k in range(3)] for i in range(3)]
    for _ in range(30):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda ij: abs(g[ij[0]][ij[1]]))
        if abs(g[p][q]) < 1e-18: break
        theta = .5*math.atan2(2*g[p][q], g[q][q]-g[p][p]); c, s = math.cos(theta), math.sin(theta)
        r = [[float(i == k) for k in range(3)] for i in range(3)]; r[p][p] = c; r[q][q] = c; r[p][q] = s; r[q][p] = -s
        g = [[sum(r[k][i]*g[k][l]*r[l][j] for k in range(3) for l in range(3)) for j in range(3)] for i in range(3)]
    return math.sqrt(max(0., min(g[i][i] for i in range(3))))


def wrap(angle): return (angle+math.pi) % (2*math.pi)-math.pi


class Chain:
    """Joints between the base and the tool link, with the variables that drive them."""

    def __init__(self, model, tip, tool, calibration, enabled):
        by_child = {j['child']: j for j in model['joints']}
        self.by_name = {j['name']: j for j in model['joints']}
        path, link = [], tip
        while link != model['root']:
            if link not in by_child: raise ValueError('Link utensile non collegato alla base.')
            path.append(by_child[link]); link = by_child[link]['parent']
        self.path = path[::-1]; self.tool = list(tool); self.calibration = calibration
        gripper = model.get('gripper') or {}
        self.gripper = set(gripper.get('joints', [])); self.travel = gripper.get('travel', 0)
        self.drivers = {}
        for joint in self.path:
            if joint['kind'] == 'fixed': continue
            name, factor = joint['name'], 1.
            while name not in self.gripper and self.by_name[name]['mimic']:
                factor *= self.by_name[name]['multiplier']; name = self.by_name[name]['mimic']
            if name in self.gripper: continue
            self.drivers[joint['name']] = (name, factor*calibration.get(name, {}).get('sign', 1))
        order = [j['name'] for j in model['joints'] if j['kind'] != 'fixed' and not j['mimic']]
        used = {name for name, _ in self.drivers.values()}
        self.variables = [n for n in order if n in used and enabled.get(n, True)]
        self.locked = [n for n in order if n in used and not enabled.get(n, True)]
        self.limits = {}
        for name in self.variables:
            j = self.by_name[name]; c = calibration.get(name, {}); sign, offset = c.get('sign', 1), c.get('offset', 0)
            self.limits[name] = tuple(sorted(((j['lower']-offset)/sign, (j['upper']-offset)/sign)))

    def value(self, name, q):
        j = self.by_name[name]
        if name in self.gripper: return float(q.get('__gripper', 0))*self.travel
        if j['mimic']: return self.value(j['mimic'], q)*j['multiplier']+j['mimic_offset']
        c = self.calibration.get(name, {})
        return float(q.get(name, 0))*c.get('sign', 1)+c.get('offset', 0)

    def urdf(self, name, q):
        c = self.calibration.get(name, {}); return float(q.get(name, 0))*c.get('sign', 1)+c.get('offset', 0)

    def controller(self, name, angle):
        c = self.calibration.get(name, {}); return (angle-c.get('offset', 0))/c.get('sign', 1)

    def forward(self, q):
        """Tool pose and, per variable, the position/rotation Jacobian columns."""
        t = [[float(i == k) for k in range(4)] for i in range(4)]; moving = []
        for joint in self.path:
            t = multiply(t, origin(joint['xyz'], joint['rpy']))
            if joint['kind'] == 'fixed': continue
            v = self.value(joint['name'], q)
            axis = apply(t, joint['axis']); point = column(t, 3)
            moving.append((joint['name'], joint['kind'], axis, point))
            if joint['kind'] == 'prismatic': t = multiply(t, origin([a*v for a in joint['axis']]))
            else: t = multiply(t, rotation(joint['axis'], v))
        t = multiply(t, origin(self.tool))
        tcp = column(t, 3); linear = {n: [0.]*3 for n in self.variables}; angular = {n: [0.]*3 for n in self.variables}
        for name, kind, axis, point in moving:
            if name not in self.drivers: continue
            driver, factor = self.drivers[name]
            if driver not in linear: continue
            if kind == 'prismatic': lin, ang = axis, [0.]*3
            else: lin, ang = cross(axis, [a-b for a, b in zip(tcp, point)]), axis
            linear[driver] = [x+factor*y for x, y in zip(linear[driver], lin)]
            angular[driver] = [x+factor*y for x, y in zip(angular[driver], ang)]
        jp = [[linear[n][i] for n in self.variables] for i in range(3)]
        jw = [[angular[n][i] for n in self.variables] for i in range(3)]
        return t, jp, jw

    def reach(self, q):
        """Upper bound of the distance between the second moving joint and the TCP."""
        t, _, _ = self.forward(q); points = []
        m = [[float(i == k) for k in range(4)] for i in range(4)]
        for joint in self.path:
            m = multiply(m, origin(joint['xyz'], joint['rpy']))
            if joint['kind'] != 'fixed':
                points.append(column(m, 3)); v = self.value(joint['name'], q)
                m = multiply(m, origin([a*v for a in joint['axis']]) if joint['kind'] == 'prismatic' else rotation(joint['axis'], v))
        if len(points) < 2: return None, None
        points = points[1:]+[column(t, 3)]
        return points[0], sum(norm([a-b for a, b in zip(points[i+1], points[i])]) for i in range(len(points)-1))


def orientation_errors(t, axis, roll):
    z, x = column(t, 2), column(t, 0); axis_error = roll_error = None
    if axis is not None: axis_error = math.acos(max(-1., min(1., dot(z, axis))))
    if roll is not None:
        projected = [r-dot(roll, z)*c for r, c in zip(roll, z)]
        roll_error = abs(math.atan2(dot(cross(x, projected), z), dot(x, projected))) if norm(projected) > 1e-9 else 0.
    return axis_error, roll_error


def solve(chain, q0, target, axis=None, roll=None, iterations=250):
    """Damped task-priority iterations from one seed, clamped to the joint limits."""
    q = dict(q0); names = chain.variables; n = len(names); stalled = 0; best = None
    for iteration in range(iterations):
        t, jp, jw = chain.forward(q)
        p, z, x = column(t, 3), column(t, 2), column(t, 0)
        error = [a-b for a, b in zip(target, p)]
        axis_error, roll_error = orientation_errors(t, axis, roll)
        # Position errors below tolerance count as equal, so orientation can improve.
        score = (norm(error) if norm(error) >= PRECISION else 0., axis_error or 0, roll_error or 0)
        if best is None or score < best[0]: best = (score, dict(q))
        if norm(error) < PRECISION and (axis_error is None or axis_error < AXIS_TOL) and (roll_error is None or roll_error < ROLL_TOL): break
        if not n: break
        levels = [(jp, clamp(error, .03), .002)]
        if axis is not None:
            e = cross(z, axis)
            if dot(z, axis) < 0 and norm(e) < 1e-6: e = column(t, 1)
            e = clamp([v*axis_error/max(norm(e), 1e-12) for v in e], .25)
            projector = [[float(i == k)-z[i]*z[k] for k in range(3)] for i in range(3)]
            levels.append(([[dot(projector[i], [jw[r][c] for r in range(3)]) for c in range(n)] for i in range(3)], e, .01))
        if roll is not None:
            projected = [r-dot(roll, z)*c for r, c in zip(roll, z)]
            if norm(projected) > 1e-9:
                angle = math.atan2(dot(cross(x, projected), z), dot(x, projected))
                levels.append(([[dot(z, [jw[r][c] for r in range(3)]) for c in range(n)]], [max(-.25, min(.25, angle))], .01))
        step = [0.]*n; null = [[float(i == k) for k in range(n)] for i in range(n)]
        for a, e, damping in levels:
            projected = [[sum(row[k]*null[k][c] for k in range(n)) for c in range(n)] for row in a]
            residual = [ei-dot(row, step) for ei, row in zip(e, a)]
            pinv = damped_pinv(projected, damping)
            step = [s+dot(pinv[c], residual) for c, s in enumerate(step)]
            # Damping smooths the step; the projector must stay exact or lower tasks leak into higher ones.
            exact = damped_pinv(projected, 1e-7)
            null = [[null[i][k]-sum(exact[i][r]*projected[r][k] for r in range(len(a))) for k in range(n)] for i in range(n)]
        largest = max(abs(s) for s in step)
        if largest > .2: step = [s*.2/largest for s in step]
        moved = 0.
        for name, s in zip(names, step):
            lo, hi = chain.limits[name]; new = max(lo, min(hi, q.get(name, 0.)+s))
            moved = max(moved, abs(new-q.get(name, 0.))); q[name] = new
        stalled = stalled+1 if moved < 1e-8 else 0
        if stalled > 5: break
    q = best[1]; t, jp, _ = chain.forward(q)
    if (axis is not None or roll is not None) and norm([a-b for a, b in zip(target, column(t, 3))]) >= POSITION_TOL:
        # An unrealizable orientation must never cost position: polish position only.
        polished = solve(chain, q, target, iterations=80)
        if polished['position_error'] < POSITION_TOL: q = polished['positions']; t, jp, _ = chain.forward(q)
    axis_error, roll_error = orientation_errors(t, axis, roll)
    at_limit = [name for name in names if min(abs(q[name]-chain.limits[name][0]), abs(q[name]-chain.limits[name][1])) < 1e-4]
    return dict(positions=q, position_error=norm([a-b for a, b in zip(target, column(t, 3))]), axis_error=axis_error,
                roll_error=roll_error, at_limit=at_limit, sigma=smallest_singular(jp), iterations=iteration+1, pose=t)


def describe(chain, q):
    """Branch labels: reach direction relative to the base joint, sign of the third variable."""
    labels = {}
    names = chain.variables
    if len(names) >= 3:
        labels['elbow'] = '+' if chain.urdf(names[2], q) >= 0 else '−'
    first = next((j for j in chain.path if j['kind'] != 'fixed'), None)
    if first and first['kind'] != 'prismatic':
        t = [[float(i == k) for k in range(4)] for i in range(4)]
        for joint in chain.path:
            t = multiply(t, origin(joint['xyz'], joint['rpy']))
            if joint is first: t = multiply(t, rotation(joint['axis'], chain.value(joint['name'], q))); break
        if abs(dot(apply(t, first['axis']), [0, 0, 1])) > .99:
            pose, _, _ = chain.forward(q); start, _ = chain.reach(q)
            offset = [a-b for a, b in zip(column(pose, 3), start or column(t, 3))]
            labels['reach'] = 'front' if dot(offset[:2], column(t, 0)[:2]) >= 0 else 'back'
    return labels


def seeds(chain, q, target):
    """Current pose first (continuity), then base aimed at/away from the target with mixed elbows."""
    result = [dict(q)]; names = chain.variables
    if len(names) < 2: return result
    first = chain.by_name[names[0]]
    azimuths = [None]
    if first['kind'] != 'prismatic' and abs(dot(first['axis'], [0, 0, 1])) > .99:
        phi = math.atan2(target[1], target[0])*(1 if first['axis'][2] > 0 else -1); azimuths = [phi, wrap(phi+math.pi)]
    for azimuth in azimuths:
        for a, b in ((.7, 1.2), (.7, -1.2), (-.7, 1.2), (-.7, -1.2)):
            seed = dict(q); urdf = {names[1]: a}
            if len(names) > 2: urdf[names[2]] = b
            if azimuth is not None: urdf[names[0]] = azimuth
            for name, angle in urdf.items():
                lo, hi = chain.limits[name]; seed[name] = max(lo, min(hi, chain.controller(name, angle)))
            result.append(seed)
    return result


def change(chain, a, b):
    return max((abs(a.get(n, 0.)-b.get(n, 0.)) for n in chain.variables), default=0.)


def inverse_kinematics(chain, q, target, axis=None, roll=None):
    """All distinct solutions that reach the position, closest to the current pose first."""
    found = []; closest = None
    for seed in seeds(chain, q, target):
        result = solve(chain, seed, target, axis, roll)
        if closest is None or result['position_error'] < closest['position_error']: closest = result
        if result['position_error'] >= POSITION_TOL: continue
        if any(change(chain, result['positions'], other['positions']) < math.radians(1) for other in found): continue
        found.append(result)
    if found:
        # Prefer the best realizable orientation, then continuity with the current pose.
        found.sort(key=lambda r: (round((r['axis_error'] or 0)/ORIENTATION_WARN), round((r['roll_error'] or 0)/ORIENTATION_WARN), change(chain, q, r['positions'])))
    if found:
        # Alternatives must hold the orientation as well as the best one, not just the point.
        axis0, roll0 = found[0]['axis_error'] or 0, found[0]['roll_error'] or 0
        found = [r for r in found if (r['axis_error'] or 0) <= axis0+ORIENTATION_WARN and (r['roll_error'] or 0) <= roll0+ORIENTATION_WARN]
    for result in found:
        result['change'] = change(chain, q, result['positions']); result['labels'] = describe(chain, result['positions'])
    return found, closest


def unreachable_reason(chain, q, target, closest):
    start, reach = chain.reach(q)
    distance = norm([a-b for a, b in zip(target, start)]) if start else None
    if chain.locked and not chain.variables: return 'locked', distance, reach
    if reach is not None and distance > reach+POSITION_TOL: return 'reach', distance, reach
    if closest and closest['at_limit']: return 'limits', distance, reach
    if chain.locked: return 'locked', distance, reach
    return 'workspace', distance, reach


def rotate(vector):
    """Rodrigues rotation matrix (3×3) for a rotation vector."""
    theta = norm(vector)
    if theta < 1e-12: return [[float(i == k) for k in range(3)] for i in range(3)]
    m = rotation([v/theta for v in vector], theta); return [row[:3] for row in m[:3]]


def jog(chain, q, frame, translation, turn, keep_axis=True):
    """One Cartesian step from the current pose; seed is the current pose only (continuity).

    frame: 4×4 base←frame matrix, or None for the tool frame. translation in metres,
    turn as a rotation vector in radians, both expressed in that frame. Rotations
    pivot about the TCP.
    """
    t, _, _ = chain.forward(q)
    basis = [row[:3] for row in (t if frame is None else frame)[:3]]
    delta = apply(basis, translation); omega = apply(basis, turn)
    target = [a+b for a, b in zip(column(t, 3), delta)]
    turning = norm(omega) > 1e-9
    if turning or keep_axis:
        r = rotate(omega)
        axis = [dot(r[i], column(t, 2)) for i in range(3)]; roll = [dot(r[i], column(t, 0)) for i in range(3)]
    else: axis = roll = None
    result = solve(chain, q, target, axis, roll, iterations=150)
    result['change'] = change(chain, q, result['positions'])
    result['limit_jump'] = max(JOG_JUMP, 2*norm(omega))
    result['turning'] = turning
    return result
