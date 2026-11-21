# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Session-only API permissions and operator approval, above the shared Studio executor."""
import copy, hashlib, json, threading, time, uuid

RUN_LEASE_SECONDS = 3.0
APPROVAL_SECONDS = 60.0
TERMINAL = ('completed', 'stopped', 'failed', 'rejected', 'expired')

class ProgramAccess:
    def __init__(self, studio):
        self.s = studio; self.lock = threading.RLock(); self.enabled = False; self.allow_demo = False
        self.runs = {}; self.execution_plans = {}; self.pending = None; self.active = None; self.stop_event = threading.Event(); self.thread = None

    def start(self):
        self.stop_event.clear()
        def monitor():
            while not self.stop_event.wait(.1): self.poll()
        self.thread = threading.Thread(target=monitor, daemon=True); self.thread.start()

    def configure(self, enabled, allow_demo):
        if type(enabled) is not bool or type(allow_demo) is not bool: raise ValueError('Permessi API non validi.')
        with self.s.lock, self.lock:
            self.enabled = enabled; self.allow_demo = enabled and allow_demo
            revoke = not enabled or (not self.allow_demo and self.s.controller.mode == 'demo')
            if revoke:
                if self.pending: self.runs[self.pending]['status'] = 'rejected'; self.pending = None
                active = self.active
            else: active = None
        if active: self.stop('Permesso API revocato: STOP.')

    def require_enabled(self):
        if not self.enabled: raise ValueError('API programmi disattivata: abilitala nell’app.')

    @staticmethod
    def fingerprint(plan):
        values = {k: plan.get(k) for k in ('context', 'starts', 'stages', 'tree', 'source')}
        return hashlib.sha256(json.dumps(values, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def snapshot_plan(self):
        with self.s.lock:
            m = self.s.movej; plan = m.plan
            if not plan or plan.get('source') != 'program': raise ValueError('Nessun piano di programma disponibile.')
            # Full execution stages and all verified continuations, not just the selected preview path.
            result = copy.deepcopy(m.state()['plan']); result['tree'] = copy.deepcopy(plan.get('tree', []))
            result['fingerprint'] = self.fingerprint(plan)
            def bounds(index, memo):
                if index in memo: return memo[index]
                segment = plan['tree'][index]; lo = sum(s['duration'] for s in segment['stages'])
                hi = lo+sum(s.get('timeout', 0) for s in segment['stages'] if s['kind'] in ('sensor', 'output'))
                if segment['end']:
                    paths = [bounds(k, memo) for k in segment['end']['next']]
                    lo += min(p[0] for p in paths); hi += max(p[1] for p in paths)
                memo[index] = (lo, hi); return memo[index]
            if plan.get('tree'): result['duration_min'], result['duration_max'] = bounds(0, {})
            result['valid'] = m.state()['valid']; return result

    def plan(self, data):
        self.poll()
        with self.s.lock, self.lock:
            self.require_enabled(); self.s.movej.ready()
            if self.pending: raise ValueError('Una richiesta API attende conferma: rifiutala o annullala prima.')
            blocks = self.s.validate_blocks(data.get('blocks'))
            self.s.action(dict(op='studio_blocks', blocks=blocks))
            self.s.action(dict(op='studio_program_plan', scenario=data.get('scenario', {})))
            return self.snapshot_plan()

    def execute(self, data):
        self.poll()
        with self.s.lock, self.lock:
            self.require_enabled(); self.s.movej.validate(data.get('id'))
            plan = self.s.movej.plan
            if plan.get('source') != 'program' or not plan.get('program'): raise ValueError('Pianifica prima il programma con l’API o il pannello.')
            if data.get('fingerprint') != self.fingerprint(plan): raise ValueError('Impronta del piano non corrispondente.')
            if self.pending or self.active: raise ValueError('Una richiesta API è già in corso.')
            mode = self.s.controller.mode
            if mode == 'demo' and not self.allow_demo: raise ValueError('Esecuzione da script in Anteprima non abilitata nell’app.')
            key = uuid.uuid4().hex
            run = dict(id=key, plan_id=plan['id'], fingerprint=data['fingerprint'], mode=mode,
                       name=str(data.get('name', 'Programma Python'))[:80], duration=plan['duration'],
                       branches=plan['program'].get('branches', 1), generation=self.s.controller.generation,
                       status='awaiting_operator' if mode == 'robot' else 'starting', error='',
                       expires=time.monotonic()+APPROVAL_SECONDS, heartbeat=time.monotonic(),
                       step=data.get('step') is True)
            self.runs[key] = run
            while len(self.runs) > 30:
                oldest = next((k for k, r in self.runs.items() if r['status'] in TERMINAL), None)
                if oldest is None: break
                self.runs.pop(oldest); self.execution_plans.pop(oldest, None)
            if mode == 'robot': self.pending = key
            else:
                try: self._execute(run)
                except Exception as error:
                    run.update(status='failed', error=str(error)); raise
            return self.public(run)

    def _execute(self, run):
        self.require_enabled(); m = self.s.movej
        if run['mode'] != self.s.controller.mode or run['generation'] != self.s.controller.generation:
            raise ValueError('Stato del robot cambiato: richiesta API annullata.')
        m.validate(run['plan_id'])
        if self.fingerprint(m.plan) != run['fingerprint']: raise ValueError('Piano modificato dopo la richiesta API.')
        if time.monotonic()-run['heartbeat'] >= RUN_LEASE_SECONDS: raise ValueError('Script non più connesso: richiesta annullata.')
        self.execution_plans[run['id']] = m.plan
        self.s.action(dict(op='studio_program_execute', id=run['plan_id'], confirmed=True, step=run['step']))
        run['status'] = 'running'; self.active = run['id']; self.pending = None

    def approve(self, key, approved):
        # Called ONLY by the native bridge; no HTTP route exposes approval.
        with self.s.lock, self.lock:
            if key != self.pending or key not in self.runs: raise ValueError('Richiesta API non più in attesa.')
            run = self.runs[key]
            if not approved: run['status'] = 'rejected'; self.pending = None; return
            try:
                if time.monotonic() >= run['expires']: raise ValueError('Conferma API scaduta: invia una nuova richiesta.')
                self._execute(run)
            except Exception as error:
                run.update(status='failed', error=str(error)); self.pending = None; raise

    def heartbeat(self, key):
        with self.lock:
            run = self.runs.get(key)
            if not run or run['status'] in TERMINAL: raise ValueError('Esecuzione API non più attiva.')
            if time.monotonic()-run['heartbeat'] >= RUN_LEASE_SECONDS:
                raise ValueError('Heartbeat script scaduto; nessuna ripresa automatica.')
            run['heartbeat'] = time.monotonic()

    def public(self, run):
        return {k: v for k, v in run.items() if k not in ('expires', 'heartbeat', 'generation')}

    def poll(self):
        stop_reason = None
        with self.lock:
            now = time.monotonic()
            if self.pending:
                r = self.runs[self.pending]
                if now >= r['expires'] or now-r['heartbeat'] >= RUN_LEASE_SECONDS:
                    r.update(status='expired', error='Richiesta API scaduta o script assente.'); self.pending = None
            if self.active:
                r = self.runs[self.active]; m = self.s.movej
                receipt = self.execution_plans.get(r['id'], {}).get('execution_result')
                if receipt:
                    r['status'] = 'completed' if receipt['done'] else ('stopped' if r['generation'] != self.s.controller.generation else 'failed'); r['error'] = receipt['error']
                    r['measured_seconds'] = sum(s['actual'] for s in receipt['measured']); r['progress'] = dict(measured=receipt['measured'], decisions=receipt['decisions']); self.execution_plans.pop(r['id'], None); self.active = None
                elif r['generation'] != self.s.controller.generation:
                    r.update(status='stopped', error=m.exec_error or 'STOP o stato cambiato.'); self.execution_plans.pop(r['id'], None); self.active = None
                elif now-r['heartbeat'] >= RUN_LEASE_SECONDS:
                    r.update(status='stopped', error='Heartbeat script scaduto: STOP.'); self.execution_plans.pop(r['id'], None); self.active = None; stop_reason = r['error']
        if stop_reason: self.s.action(dict(op='studio_cancel'))

    def run(self, key):
        self.poll()
        with self.lock:
            if key not in self.runs: raise ValueError('Esecuzione API non presente.')
            result = self.public(self.runs[key]); m = self.s.movej
            if key == self.active or self.runs[key]['plan_id'] == (m.plan or {}).get('id'):
                result['progress'] = dict(block=m.exec_block, stage=m.exec_stage, name=m.exec_name,
                                          step_waiting=m.step_waiting, measured=copy.deepcopy(m.exec_measured), decisions=copy.deepcopy(m.exec_decisions))
            return result

    def stop(self, reason='STOP richiesto dallo script.'):
        with self.lock:
            for key in (self.pending, self.active):
                if key:
                    self.runs[key].update(status='stopped', error=reason); self.execution_plans.pop(key, None)
            self.pending = self.active = None
        self.s.action(dict(op='studio_cancel'))

    def state(self):
        self.poll()
        with self.lock:
            return dict(motion_enabled=self.enabled, demo_execution=self.allow_demo,
                        pending=self.public(self.runs[self.pending]) if self.pending else None,
                        active=self.public(self.runs[self.active]) if self.active else None,
                        script_heartbeat_seconds=RUN_LEASE_SECONDS, approval_seconds=APPROVAL_SECONDS)

    def close(self):
        self.stop_event.set()
        with self.lock:
            need_stop = bool(self.active); self.enabled = self.allow_demo = False
            if self.pending: self.runs[self.pending]['status'] = 'rejected'; self.pending = None
        if need_stop: self.stop('API chiusa: STOP.')
        if self.thread and self.thread is not threading.current_thread(): self.thread.join(timeout=2)
