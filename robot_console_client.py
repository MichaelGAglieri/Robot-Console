# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Standard-library client. It cannot connect hardware or approve a real execution."""
import json, threading, time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError

class APIError(RuntimeError):
    def __init__(self, message, status=None, problem=None):
        super().__init__(message); self.status=status; self.problem=problem

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

class RobotConsole:
    def __init__(self, url, token, timeout=10):
        parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or not parsed.port or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise ValueError('Usa l’indirizzo HTTP locale mostrato nell’app.')
        if not isinstance(token,str) or not token:raise ValueError('Token API richiesto.')
        self.url=url.rstrip('/');self.token=token;self.timeout=timeout
        self.opener=build_opener(ProxyHandler({}),NoRedirect())

    def request(self, path, data=None, headers=None):
        if not path.startswith('/v1/') or '://' in path or '?' in path:raise ValueError('Percorso API non valido.')
        raw=None if data is None else json.dumps(data,allow_nan=False).encode()
        req=Request(self.url+path,data=raw,headers={**(headers or {}),'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with self.opener.open(req,timeout=self.timeout) as response:return json.load(response)
        except HTTPError as error:
            with error:
                try:body=json.load(error)
                except (ValueError,OSError):body={}
            raise APIError(body.get('error','Errore API locale.'),error.code,body.get('problem')) from error

    def state(self):return self.request('/v1/state')
    def health(self):return self.request('/v1/health')
    def plan(self, blocks, scenario=None):return self.request('/v1/program/plan',dict(blocks=blocks,scenario=scenario or {}))
    def current_plan(self):return self.request('/v1/plan')
    def execute(self, plan, name='Programma Python', step=False):
        return self.request('/v1/program/execute',dict(id=plan['id'],fingerprint=plan['fingerprint'],name=name,step=step))
    def run(self, run):return self.request('/v1/runs/'+(run['id'] if isinstance(run,dict) else run))
    def heartbeat(self, run):return self.request('/v1/program/heartbeat',dict(id=run['id'] if isinstance(run,dict) else run))
    def stop(self):return self.request('/v1/stop',{})
    def step(self, run):return self.request('/v1/program/step',dict(id=run['id']))
    def continue_program(self, run):return self.request('/v1/program/continue',dict(id=run['id']))
    def sensor(self, name, value):return self.request('/v1/sensors',dict(name=name,value=value))
    def io(self):return self.request('/v1/io')
    def wait(self, run, timeout=600, poll_interval=.2, progress=None):
        """Keep this script's lease alive, including while awaiting the operator.
        Timeout/KeyboardInterrupt requests STOP. No automatic retry or resume of execution.
        """
        end=time.monotonic()+timeout
        try:
            while True:
                state=self.run(run)
                if progress:progress(state)
                if state['status']=='completed':return state
                if state['status'] in ('stopped','failed','rejected','expired'):raise APIError(state['error'] or state['status'])
                if time.monotonic()>=end:
                    self.stop();raise TimeoutError('Timeout dello script: STOP richiesto.')
                try:self.heartbeat(run)
                except APIError:
                    state=self.run(run)
                    if state['status']=='completed':return state
                    raise
                time.sleep(max(.02,min(.5,poll_interval)))
        except KeyboardInterrupt:
            self.stop();raise

class Adapter:
    """An adapter declares whether its I/O is simulated. Real output ACKs must follow actual I/O."""
    def __init__(self, client, name, inputs=(), outputs=(), simulated=True):
        self.client=client
        session=client.request('/v1/adapters',dict(name=name,inputs=list(inputs),outputs=list(outputs),simulated=simulated))
        self.id=session['id'];self.token=session['adapter_token'];self.closed=threading.Event();self.error=None
        def keepalive():
            while not self.closed.wait(.2):
                try:client.request('/v1/adapters/'+self.id+'/heartbeat',dict(adapter_token=self.token))
                except Exception as error:self.error=error;break
        self.worker=threading.Thread(target=keepalive,daemon=True);self.worker.start()
    def publish(self, name, value):
        if self.error:raise self.error
        return self.client.request('/v1/sensors',dict(name=name,value=value,adapter_id=self.id,adapter_token=self.token))
    def requests(self):
        if self.error:raise self.error
        return self.client.request('/v1/adapters/'+self.id+'/requests',headers={'X-Adapter-Token':self.token})['requests']
    def acknowledge(self, request, actual_value, success=True):
        return self.client.request('/v1/io/ack',dict(adapter_id=self.id,adapter_token=self.token,request_id=request['id'],value=actual_value,success=success))
    def close(self):
        self.closed.set();self.worker.join(timeout=2)
        try:self.client.request('/v1/adapters/'+self.id+'/disconnect',dict(adapter_token=self.token))
        except (APIError,OSError):pass
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
