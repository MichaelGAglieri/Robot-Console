# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Explicit, authenticated loopback API for telemetry and named sensor inputs.
No endpoint can open USB, upload firmware, HOME or execute motion.
"""
import json,secrets,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
class LocalAPI:
 def __init__(self,controller,studio):self.controller=controller;self.studio=studio;self.server=None;self.token='';self.port=0
 def state(self):return dict(running=self.server is not None,url='http://127.0.0.1:'+str(self.port) if self.server else '',token=self.token if self.server else '',scope='telemetry + named sensor input; no motion')
 def start(self):
  if self.server:return
  self.token=secrets.token_urlsafe(32);owner=self
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def respond(self,status,data):
    raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def authorized(self):return secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.token)
   def do_GET(self):
    if not self.authorized():self.respond(403,{'error':'Unauthorized'});return
    if self.path=='/v1/state':self.respond(200,dict(controller=owner.controller.state(),studio=owner.studio.state()))
    elif self.path=='/v1/health':self.respond(200,{'ok':True,'scope':'no motion'})
    else:self.respond(404,{'error':'Not found'})
   def do_POST(self):
    if not self.authorized():self.respond(403,{'error':'Unauthorized'});return
    try:
     length=int(self.headers.get('Content-Length','0'))
     if not 0<length<=4096:raise ValueError('Request too large')
     data=json.loads(self.rfile.read(length))
     if self.path!='/v1/sensors':self.respond(404,{'error':'No motion endpoint'});return
     with owner.studio.lock:owner.studio.sensor_value(data['name'],data['value'],'adattatore API locale')
     self.respond(200,{'ok':True})
    except (ValueError,KeyError,TypeError) as error:self.respond(400,{'error':str(error)})
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True;self.port=self.server.server_address[1]
  server=self.server;threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True).start()
 def stop(self):
  server=self.server;self.server=None
  if server:server.shutdown();server.server_close()
  self.token='';self.port=0
