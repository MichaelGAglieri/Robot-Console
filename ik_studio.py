# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Studio adapter for five-axis IK and Cartesian jog. Preview only: it changes
the virtual model pose and never calls controller action/spawn/write."""
import hashlib
import json
import math
from ik5 import (Chain, inverse_kinematics, unreachable_reason, jog, column, norm,
                 ORIENTATION_WARN, POSITION_TOL, SINGULAR)
from robot_model import origin, multiply, number
from work_scene import scene_state


def mm(value): return '%.1f' % (value*1000)
def deg(value): return '%.1f' % math.degrees(value)


class CartesianPreview:
    def __init__(self, studio):
        self.s = studio; self.report = None; self.solutions = []; self.context = ''

    def chain(self):
        s = self.s
        return Chain(s.model, s.tip, s.tool, s.calibration, s.effective_enabled())

    def key(self):
        s = self.s
        values = [s.model['source_hash'], s.calibration, s.tool, s.tip, s.effective_enabled()]
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def frame(self, key):
        """4×4 base←frame matrix; None for the tool frame."""
        if key == 'tool': return None
        entries, _ = scene_state(self.s.work_frames, [])
        for entry in entries:
            if entry['id'] == key: return origin(entry['xyz'], entry['rpy'])
        raise ValueError('Riferimento non presente: ricarica la scena.')

    def readout(self, positions):
        """TCP position and tool axis in the base and in every work frame."""
        try: pose, jp, _ = self.chain().forward(positions)
        except (ValueError, KeyError): return None
        from ik5 import smallest_singular
        entries, _ = scene_state(self.s.work_frames, [])
        frames = []
        for entry in entries:
            f = origin(entry['xyz'], entry['rpy']); r = [row[:3] for row in f[:3]]
            delta = [pose[i][3]-f[i][3] for i in range(3)]
            local = [sum(r[k][i]*delta[k] for k in range(3)) for i in range(3)]
            axis = [sum(r[k][i]*pose[k][2] for k in range(3)) for i in range(3)]
            frames.append(dict(id=entry['id'], name=entry['name'], xyz=[v*1000 for v in local], axis=axis))
        sigma = smallest_singular(jp)
        return dict(frames=frames, sigma=sigma, singular=sigma < SINGULAR)

    def apply(self, positions):
        s = self.s
        if s.follow: s.preview = s.current_positions()
        for joint in s.independent():
            if joint['name'] in positions: s.preview[joint['name']] = positions[joint['name']]
        s.preview.pop('__gripper', None); s.follow = False

    def summary(self, chain, result):
        return dict(labels=result.get('labels', {}), change_deg=math.degrees(result.get('change', 0)),
                    position_error_mm=result['position_error']*1000,
                    axis_error_deg=None if result['axis_error'] is None else math.degrees(result['axis_error']),
                    roll_error_deg=None if result['roll_error'] is None else math.degrees(result['roll_error']),
                    joints=[dict(name=n, deg=math.degrees(result['positions'][n])) for n in chain.variables],
                    at_limit=result['at_limit'], singular=result['sigma'] < SINGULAR)

    def solve(self, kind, target, axis=None, roll=None, label=''):
        chain = self.chain(); q = self.s.current_positions()
        found, closest = inverse_kinematics(chain, q, target, axis, roll)
        self.context = self.key(); self.solutions = [r['positions'] for r in found[:6]]
        report = dict(kind=kind, label=label, ok=bool(found), applied=bool(found), chosen=0, reason='',
                      solutions=[self.summary(chain, r) for r in found[:6]], collisions=[], singular=False,
                      target_mm=[v*1000 for v in target], locked=chain.locked)
        if found:
            best = found[0]; self.apply(best['positions'])
            report['collisions'] = self.s.collision_report(self.s.current_positions())
            report['singular'] = best['sigma'] < SINGULAR
            residual = max(best['axis_error'] or 0, best['roll_error'] or 0)
            if residual > ORIENTATION_WARN:
                message = 'IK: posizione raggiunta; orientamento non realizzabile con questi assi · scarto %s° · soluzioni: %d.' % (deg(residual), len(found))
            elif axis is not None:
                message = 'IK: posizione e orientamento raggiunti · soluzioni: %d · scelta la più vicina (variazione massima %s°).' % (len(found), deg(best['change']))
            else:
                message = 'IK: posizione raggiunta · soluzioni: %d · scelta la più vicina (variazione massima %s°).' % (len(found), deg(best['change']))
        else:
            reason, distance, reach = unreachable_reason(chain, q, target, closest); report['reason'] = reason
            if reason == 'reach':
                message = 'IK: punto fuori portata · distanza %s mm, portata massima stimata %s mm. Anteprima invariata.' % (mm(distance), mm(reach))
            elif reason == 'limits':
                message = 'IK: punto non raggiungibile entro i limiti dei giunti (%s). Anteprima invariata.' % ', '.join(closest['at_limit'])
            elif reason == 'locked':
                message = 'IK: i giunti esclusi impediscono la soluzione (%s). Anteprima invariata.' % ', '.join(chain.locked)
            else:
                message = 'IK: nessuna soluzione trovata · distanza minima %s mm. Anteprima invariata.' % mm(closest['position_error'])
        report['message'] = message; self.report = report; self.s.status = message

    def point(self, request):
        frame_key = request.get('frame', 'base')
        if frame_key == 'tool': raise ValueError('Per l’IK scegli la base o un riferimento di lavoro.')
        frame = self.frame(frame_key); local = request.get('target')
        if not isinstance(local, list) or len(local) != 3: raise ValueError('Il target cartesiano richiede X, Y e Z.')
        local = [number(v, -10, 10) for v in local]
        target = [sum(frame[i][k]*local[k] for k in range(3))+frame[i][3] for i in range(3)]
        mode = request.get('orientation', 'free'); axis = roll = None
        if mode == 'down': axis = [-frame[i][2] for i in range(3)]
        elif mode == 'keep':
            pose, _, _ = self.chain().forward(self.s.current_positions()); axis = column(pose, 2); roll = column(pose, 0)
        elif mode != 'free': raise ValueError('Orientamento IK non valido.')
        self.solve('point', target, axis, roll)

    def target(self, request):
        key = request.get('id'); mode = request.get('orientation', 'axis')
        if mode not in ('position', 'axis', 'full'): raise ValueError('Orientamento IK non valido.')
        _, targets = scene_state(self.s.work_frames, self.s.cartesian_targets)
        found = next((t for t in targets if t['id'] == key), None)
        if found is None: raise ValueError('Target non presente.')
        m = [found['matrix'][i*4:i*4+4] for i in range(4)]
        axis = column(m, 2) if mode != 'position' else None; roll = column(m, 0) if mode == 'full' else None
        self.s.selected_target = key
        self.solve('target', column(m, 3), axis, roll, found['name'])

    def choose(self, index):
        if type(index) != int or not self.report or not 0 <= index < len(self.solutions): raise ValueError('Soluzione IK non presente.')
        if self.key() != self.context: raise ValueError('Modello o calibrazione cambiati: ricalcola l’IK.')
        self.apply(self.solutions[index]); self.report['chosen'] = index
        self.report['collisions'] = self.s.collision_report(self.s.current_positions())
        self.s.status = 'IK: soluzione %d applicata all’anteprima.' % (index+1)

    def jog(self, request):
        translation = request.get('translation', [0, 0, 0]); turn = request.get('rotation', [0, 0, 0])
        if not isinstance(translation, list) or not isinstance(turn, list) or len(translation) != 3 or len(turn) != 3:
            raise ValueError('Passo cartesiano non valido.')
        translation = [number(v, -50, 50)/1000 for v in translation]; turn = [math.radians(number(v, -30, 30)) for v in turn]
        if norm(translation) < 1e-9 and norm(turn) < 1e-9: raise ValueError('Passo cartesiano nullo.')
        keep = request.get('keep_axis', True) is True
        chain = self.chain(); q = self.s.current_positions()
        result = jog(chain, q, self.frame(request.get('frame', 'base')), translation, turn, keep)
        residual = max(result['axis_error'] or 0, result['roll_error'] or 0)
        report = dict(kind='jog', label='', ok=False, applied=False, chosen=0, reason='', solutions=[], collisions=[],
                      singular=result['sigma'] < SINGULAR, target_mm=[], locked=chain.locked)
        if result['position_error'] >= POSITION_TOL:
            report['reason'] = 'reach'
            message = 'Jog rifiutato: punto fuori portata o oltre i limiti dei giunti. Anteprima invariata.'
        elif result['change'] > result['limit_jump']:
            report['reason'] = 'jump'
            message = 'Jog rifiutato: il passo richiederebbe %s° su un giunto (singolarità o cambio di configurazione). Riduci il passo.' % deg(result['change'])
        elif result['turning'] and residual > ORIENTATION_WARN:
            report['reason'] = 'orientation'
            message = 'Jog rifiutato: rotazione non realizzabile con questi assi in questa posa · scarto %s°.' % deg(residual)
        else:
            self.apply(result['positions']); report.update(ok=True, applied=True)
            report['collisions'] = self.s.collision_report(self.s.current_positions())
            if residual > ORIENTATION_WARN:
                message = 'Jog: passo applicato; direzione utensile non mantenibile con questi assi · scarto %s°.' % deg(residual)
            else:
                message = 'Jog: passo applicato all’anteprima · variazione massima %s°.' % deg(result['change'])
        report['message'] = message; self.report = report; self.solutions = []; self.s.status = message

    def state(self, positions):
        return dict(readout=self.readout(positions), report=self.report)
