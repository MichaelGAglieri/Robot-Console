# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Runtime leases for external I/O. No GPIO, USB or firmware access."""
import copy, math, secrets, threading, time, uuid
from robot_model import number

FRESH_SECONDS = 1.0
HEARTBEAT_SECONDS = 1.0

def digital(value):
    if type(value) not in (bool, int) or value not in (0, 1):
        raise ValueError('Valore uscita digitale: usa 0 oppure 1.')
    return bool(value)

class AdapterHub:
    def __init__(self, studio):
        self.s = studio; self.lock = threading.RLock(); self.adapters = {}; self.requests = {}; self.values = {}

    @staticmethod
    def definitions(raw):
        if not isinstance(raw, dict) or len(raw) > 64: raise ValueError('Massimo 64 uscite digitali.')
        if any(not isinstance(n, str) or not n.strip() or len(n) > 60 or v != 'digital' for n, v in raw.items()):
            raise ValueError('Definizione uscita digitale non valida.')
        return dict(raw)

    def define(self, name):
        proposed = dict(self.s.outputs); proposed[name] = 'digital'
        self.s.outputs = self.definitions(proposed)

    def register(self, data):
        name = data.get('name'); simulated = data.get('simulated', True)
        if not isinstance(name, str) or not name.strip() or len(name) > 60 or type(simulated) is not bool:
            raise ValueError('Nome e origine dell’adattatore non validi.')
        inputs, outputs = data.get('inputs', []), data.get('outputs', [])
        for names, defined in ((inputs, self.s.sensors), (outputs, self.s.outputs)):
            if not isinstance(names, list) or len(names) > 64 or any(not isinstance(n, str) or n not in defined for n in names) or len(set(names)) != len(names):
                raise ValueError('Definisci nell’app tutti gli ingressi e le uscite dell’adattatore.')
        with self.lock:
            # Live I/O has one owner; reconnecting requires expiry or an explicit disconnect.
            for adapter in self.adapters.values():
                if self.alive(adapter) and (set(inputs) & set(adapter['inputs']) or set(outputs) & set(adapter['outputs'])):
                    raise ValueError('Ingresso o uscita già assegnato a un adattatore attivo.')
            if len(self.adapters) >= 64:
                self.adapters = {k: a for k, a in self.adapters.items() if self.alive(a)}
                if len(self.adapters) >= 64: raise ValueError('Massimo 64 adattatori attivi.')
            key = uuid.uuid4().hex; token = secrets.token_urlsafe(24)
            self.adapters[key] = dict(id=key, name=name, token=token, simulated=simulated,
                                      inputs=inputs[:], outputs=outputs[:], heartbeat=time.monotonic(), connected=True)
            return dict(id=key, adapter_token=token, heartbeat_seconds=HEARTBEAT_SECONDS, freshness_seconds=FRESH_SECONDS)

    def alive(self, adapter):
        return adapter['connected'] and time.monotonic()-adapter['heartbeat'] < HEARTBEAT_SECONDS

    def authorized(self, key, token, live=True):
        adapter = self.adapters.get(key)
        if not adapter or not isinstance(token, str) or not secrets.compare_digest(adapter['token'], token):
            raise ValueError('Sessione adattatore non valida.')
        if live and not self.alive(adapter): raise ValueError('Heartbeat adattatore scaduto: registra una nuova sessione.')
        return adapter

    def heartbeat(self, key, token):
        with self.lock:
            a = self.authorized(key, token); a['heartbeat'] = time.monotonic()

    def disconnect(self, key, token):
        with self.lock: self.authorized(key, token, live=False)['connected'] = False

    def publish(self, data):
        with self.s.lock, self.lock:
            name = data['name']
            if data.get('adapter_id'):
                a = self.authorized(data['adapter_id'], data.get('adapter_token'))
                if name not in a['inputs']: raise ValueError('Ingresso non assegnato a questo adattatore.')
                self.s.sensor_value(name, data['value'], 'adattatore API locale')
                self.s.sensors[name].update(adapter_id=a['id'], simulated=a['simulated'])
            else:
                # Compatibility endpoint: unregistered samples can never claim measurement.
                self.s.sensor_value(name, data['value'], 'adattatore API locale')
                self.s.sensors[name].pop('adapter_id', None); self.s.sensors[name]['simulated'] = True

    def read_sensor(self, name):
        with self.s.lock, self.lock:
            sensor = self.s.sensors.get(name)
            if sensor is None: raise ValueError('sensore %s non definito' % name)
            if sensor['value'] is None: raise ValueError('%s senza dato' % name)
            key = sensor.get('adapter_id')
            if key and (key not in self.adapters or not self.alive(self.adapters[key])):
                raise ValueError('%s: adattatore non disponibile' % name)
            simulated = sensor.get('simulated', sensor['source'] in ('simulato', 'non collegato'))
            if self.s.controller.mode == 'robot':
                if simulated: raise ValueError('%s: un dato simulato non vale sul robot reale' % name)
                if time.time()-sensor['stamp'] >= FRESH_SECONDS:
                    raise ValueError('%s: dato non aggiornato nell’ultimo secondo' % name)
            # Adapter samples must remain fresh in both modes; GUI simulation is persistent in Anteprima.
            if key and time.time()-sensor['stamp'] >= FRESH_SECONDS: raise ValueError('%s: dato adattatore scaduto' % name)
            return sensor['value']

    def pending(self, key, token):
        with self.lock:
            self.authorized(key, token); self.prune()
            return [self.public(r) for r in self.requests.values() if r['adapter_id'] == key and r['status'] == 'pending']

    def public(self, request):
        return {k: v for k, v in request.items() if k not in ('deadline', 'generation')}

    def prune(self):
        now = time.monotonic()
        for r in self.requests.values():
            if r['status'] == 'pending':
                a = self.adapters.get(r['adapter_id'])
                if r['generation'] != self.s.controller.generation: r['status'] = 'cancelled'
                elif now >= r['deadline']: r['status'] = 'timeout'
                elif not a or not self.alive(a): r['status'] = 'disconnected'
        if len(self.requests) > 200:
            self.requests = dict(list(self.requests.items())[-200:])

    def ack(self, data):
        with self.lock:
            a = self.authorized(data['adapter_id'], data.get('adapter_token')); self.prune()
            r = self.requests.get(data.get('request_id'))
            if not r or r['status'] != 'pending' or r['adapter_id'] != a['id']:
                raise ValueError('Richiesta uscita scaduta, annullata o non assegnata.')
            if data.get('success') is not True or digital(data.get('value')) != r['value']:
                r['status'] = 'failed'; raise ValueError('Conferma uscita non corrispondente alla richiesta.')
            r['status'] = 'confirmed'
            self.values[r['name']] = dict(value=r['value'], simulated=False, source=a['name'], stamp=time.time())

    def write_output(self, stage, gen):
        c = self.s.controller; name = stage['output']; value = digital(stage['value'])
        c.wait_ready(gen)
        with self.lock:
            if name not in self.s.outputs: raise ValueError('Uscita non definita: '+name)
            if c.mode == 'demo':
                self.values[name] = dict(value=value, simulated=True, source='simulato', stamp=time.time())
                c.log('Uscita simulata %s = %d.' % (name, value)); return
            adapters = [a for a in self.adapters.values() if name in a['outputs'] and self.alive(a) and not a['simulated']]
            if len(adapters) != 1: raise ValueError('Uscita senza adattatore misurato attivo: '+name)
            key = uuid.uuid4().hex
            r = dict(id=key, name=name, value=value, status='pending', adapter_id=adapters[0]['id'],
                     generation=gen, deadline=time.monotonic()+stage['timeout'], timeout=stage['timeout'])
            self.requests[key] = r
        try:
            while True:
                c.wait_ready(gen)
                with self.lock:
                    self.prune(); status = r['status']
                    if status == 'confirmed':
                        if not self.alive(adapters[0]): raise ValueError('Adattatore uscita non disponibile: '+name)
                        return
                    if status != 'pending': raise ValueError('Uscita %s: %s.' % (name, status))
                time.sleep(.02)
        finally:
            with self.lock:
                if r['status'] == 'pending': r['status'] = 'cancelled'

    def state(self):
        with self.lock:
            self.prune()
            return dict(outputs=[dict(name=name, kind=kind, **self.values.get(name, dict(value=None, simulated=True, source='non collegato', stamp=0.))) for name, kind in self.s.outputs.items()],
                        adapters=[dict(id=a['id'], name=a['name'], simulated=a['simulated'], alive=self.alive(a), age=time.monotonic()-a['heartbeat']) for a in self.adapters.values()],
                        requests=[self.public(r) for r in list(self.requests.values())[-20:]])

    def close(self):
        with self.lock:
            for a in self.adapters.values(): a['connected'] = False
            for r in self.requests.values():
                if r['status'] == 'pending': r['status'] = 'cancelled'
