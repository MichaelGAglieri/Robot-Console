# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Authenticated loopback API. Only the native app can grant execution permissions/approval.
No route can connect USB, upload firmware, establish HOME or edit limits.
"""
import json, secrets, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit
from program_api import ProgramAccess

class LocalAPI:
 def __init__(self, controller, studio):
  self.controller=controller;self.studio=studio;self.server=None;self.token='';self.port=0;self.commands=ProgramAccess(studio)
 def state(self):
  return dict(running=self.server is not None,url='http://127.0.0.1:'+str(self.port) if self.server else '',token=self.token if self.server else '',scope='stato, I/O e programmi con permessi espliciti',**self.commands.state())
 def dispatch(self,method,path,data,headers):
  s=self.studio
  if method=='GET':
   if path=='/v1/state':return 200,dict(controller=self.controller.state(),studio=s.state(),access=self.commands.state())
   if path=='/v1/health':return 200,dict(ok=True,version=2,**self.commands.state())
   if path=='/v1/plan':return 200,self.commands.snapshot_plan()
   if path.startswith('/v1/runs/') and len(path.split('/'))==4:return 200,self.commands.run(path.split('/')[-1])
   if path=='/v1/io':return 200,s.io.state()
   if path.startswith('/v1/adapters/') and path.endswith('/requests') and len(path.split('/'))==5:
    return 200,dict(requests=s.io.pending(path.split('/')[3],headers.get('X-Adapter-Token','')))
  if method=='POST':
   if path=='/v1/program/plan':return 200,self.commands.plan(data)
   if path=='/v1/program/execute':return 202,self.commands.execute(data)
   if path=='/v1/program/heartbeat':self.commands.heartbeat(data['id']);return 200,dict(ok=True)
   if path in ('/v1/program/step','/v1/program/continue'):
    with s.lock,self.commands.lock:
     self.commands.require_enabled()
     if data.get('id')!=self.commands.active:raise ValueError('Esecuzione API non attiva.')
     s.action(dict(op='studio_program_step' if path.endswith('/step') else 'studio_program_continue'))
    return 200,dict(ok=True)
   if path=='/v1/stop':self.commands.stop();return 200,dict(ok=True)
   if path=='/v1/sensors':s.io.publish(data);return 200,dict(ok=True)
   if path=='/v1/adapters':return 201,s.io.register(data)
   if path=='/v1/io/ack':s.io.ack(data);return 200,dict(ok=True)
   if path.startswith('/v1/adapters/') and len(path.split('/'))==5:
    parts=path.split('/');key=parts[3]
    if parts[4]=='heartbeat':s.io.heartbeat(key,data.get('adapter_token'));return 200,dict(ok=True)
    if parts[4]=='disconnect':s.io.disconnect(key,data.get('adapter_token'));return 200,dict(ok=True)
  return 404,dict(error='Endpoint non disponibile.')
 def start(self):
  if self.server:return
  self.commands=ProgramAccess(self.studio);self.token=secrets.token_urlsafe(32);owner=self
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def setup(self):super().setup();self.connection.settimeout(5)
   def respond(self,status,data):
    raw=json.dumps(data,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers()
    try:self.wfile.write(raw)
    except (BrokenPipeError,ConnectionResetError):pass
   def handle_request(self,method):
    if not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.token):self.respond(403,dict(error='Autorizzazione API non valida.'));return
    if self.headers.get('Origin'):self.respond(403,dict(error='Richieste del browser non consentite.'));return
    host=self.headers.get('Host','')
    if host not in ('127.0.0.1:'+str(owner.port),'localhost:'+str(owner.port)):self.respond(403,dict(error='Host locale non valido.'));return
    try:
     data={}
     if method=='POST':
      length=int(self.headers.get('Content-Length','0'))
      if not 0<length<=262144:raise ValueError('Richiesta API vuota o troppo grande.')
      raw=self.rfile.read(length)
      if len(raw)!=length:raise ValueError('Richiesta API incompleta.')
      data=json.loads(raw,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Numero JSON non valido.')))
      if not isinstance(data,dict):raise ValueError('La richiesta API deve essere un oggetto JSON.')
     status,result=owner.dispatch(method,self.path,data,self.headers);self.respond(status,result)
    except (ValueError,KeyError,TypeError,AttributeError,RecursionError) as error:
     self.respond(400,dict(error=str(error),problem=owner.studio.movej.problem))
    except (TimeoutError,OSError):self.respond(408,dict(error='Timeout della richiesta API.'))
   def do_GET(self):self.handle_request('GET')
   def do_POST(self):self.handle_request('POST')
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True;self.port=self.server.server_address[1];self.commands.start()
  server=self.server;threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True).start()
 def stop(self):
  server=self.server;self.server=None;self.commands.close();self.studio.io.close()
  if server:server.shutdown();server.server_close()
  self.token='';self.port=0
