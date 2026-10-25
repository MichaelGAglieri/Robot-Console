# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import sys,json,os,fcntl
sys.dont_write_bytecode=True
from pathlib import Path
folder=Path(os.environ.get('DOC_REGIA_DATA',str(Path.home()/'Library/Application Support/DOC Regia')))
folder.mkdir(parents=True,exist_ok=True)
os.environ['DOC_REGIA_DATA']=str(folder)
# One native controller per user, including when opened from different copies.
lock=open(folder/'controller.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except OSError:
 print(json.dumps({'error':'Robot Console è già aperta.'}),flush=True);sys.exit(1)
import server
from assistant_local import Journal,Assistant
from ollama_local import OllamaLocal
from ros_link import ROSLink
from firmware_tools import FirmwareTools
journal=Journal(folder)
server.c.journal=journal
ollama=OllamaLocal(folder)
assistant=Assistant(server.c,journal,ollama)
ros=ROSLink(folder,journal)
firmware=FirmwareTools(folder,server.c,journal)
last_limits={}
try:
 stored=json.loads((folder/'limiti.json').read_text())
 for mode,values in stored.items():
  if mode in ('demo','robot') and isinstance(values,list) and len(values)==5 and all(isinstance(pair,list) and len(pair)==2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in pair) and -360<=pair[0]<=0<=pair[1]<=360 for pair in values):last_limits[mode]=values
except (OSError,ValueError,TypeError,AttributeError):pass
journal.add('session','app','Sessione avviata; nessuna connessione hardware automatica.')
def reply():
 state=server.c.state()
 if ros.process:ros.snapshot(state)
 return dict(state=state,chat=journal.recent(30,True),diary=journal.recent(30),assistant_busy=assistant.busy,ros_status=ros.status,ros_event=ros.last_event,ollama=ollama.state(),firmware=firmware.state(),last_limits=last_limits)

try:
 for line in sys.stdin:
  try:
   request=json.loads(line)
   op=request.get('op')
   if op=='chat':assistant.ask(request.get('text',''),request.get('llm',False))
   elif op=='ollama_start':ollama.start()
   elif op=='ollama_refresh':ollama.refresh_async()
   elif op=='ollama_stop':
    if assistant.busy:raise ValueError('Attendi la risposta in corso prima di fermare l’IA.')
    ollama.stop()
   elif op=='ollama_select':ollama.select(request.get('model',''))
   elif op=='firmware':firmware.start(request.get('operation',''),request.get('port',''),request.get('confirmed',False))
   elif op=='firmware_cancel':firmware.stop()
   elif op=='ros_connect':ros.start(request.get('project',''))
   elif op=='ros_disconnect':ros.stop()
   else:
    if op!='heartbeat':journal.add('request',server.c.mode,json.dumps(request,ensure_ascii=False))
    server.c.action(request)
    if op=='limits':
     last_limits[server.c.mode]=[pair[:] for pair in server.c.limits]
     tmp=folder/'limiti.tmp';tmp.write_text(json.dumps(last_limits));tmp.replace(folder/'limiti.json')
   print(json.dumps(reply()),flush=True)
  except Exception as e:
   journal.add('error','app',str(e))
   print(json.dumps(dict(reply(),error=str(e))),flush=True)
finally:
 firmware.close()
 server.c.halt('App chiusa: STOP')
 ros.stop()
 ollama.close()
