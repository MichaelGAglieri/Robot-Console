# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Controller process shared by the macOS (Swift) and cross-platform (Qt) front ends.
One JSON request per stdin line, one JSON state reply per stdout line. EOF = STOP and exit."""
import sys,json,os
sys.dont_write_bytecode=True
from pathlib import Path
here=Path(__file__).resolve().parent
for path in (here,here.parent):
 if (path/'server.py').is_file() and str(path) not in sys.path:sys.path.insert(0,str(path))
if os.name=='nt':
 # JSON is UTF-8 on every platform; Windows pipes default to the ANSI code page.
 sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
from platform_support import data_folder,InstanceLock
folder=data_folder()
folder.mkdir(parents=True,exist_ok=True)
os.environ['DOC_REGIA_DATA']=str(folder)
# One native controller per user, including when opened from different copies.
lock=InstanceLock(folder)
if not lock.acquire():
 print(json.dumps({'error':'Robot Console è già aperta.'}),flush=True);sys.exit(1)
import server
from assistant_local import Journal,Assistant
from ollama_local import OllamaLocal
from ros_link import ROSLink
from firmware_tools import FirmwareTools
from studio import Studio
from firmware_workspace import FirmwareWorkspace
from tool_manager import ToolManager
from local_api import LocalAPI
from jarvis_channel import JarvisChannel
journal=Journal(folder)
server.c.journal=journal
ollama=OllamaLocal(folder)
assistant=Assistant(server.c,journal,ollama)
ros=ROSLink(folder,journal)
firmware=FirmwareTools(folder,server.c,journal)
studio=Studio(folder,server.c,journal)
assistant.studio=studio
workspace=FirmwareWorkspace(folder,server.c)
firmware.workspace=workspace
extra={}
tools=ToolManager(folder,journal)
api=LocalAPI(server.c,studio)
jarvis=JarvisChannel(server.c,studio,folder,journal)
try:jarvis.start()
except (OSError,ValueError) as error:journal.add("error","jarvis",str(error))
last_limits={}
try:
 stored=json.loads((folder/'limiti.json').read_text())
 for mode,values in stored.items():
  if mode in ('demo','robot') and isinstance(values,list) and len(values) in (5,6) and all(isinstance(pair,list) and len(pair)==2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in pair) and -360<=pair[0]<=0<=pair[1]<=360 for pair in values):last_limits[mode]=values+[[0.,0.]]*(6-len(values))
except (OSError,ValueError,TypeError,AttributeError):pass
journal.add('session','app','Sessione avviata; nessuna connessione hardware automatica.')
def reply():
 state=server.c.state()
 if ros.process:ros.snapshot(state,studio.ros_snapshot())
 return dict(jarvis_quit=jarvis.quit_requested,jarvis_connection=jarvis.take_connection_selection(),ros_health=ros.state(),tools=tools.state(),local_api=api.state(),firmware_workspace=workspace.state(),**extra,studio=studio.state(),state=state,chat=journal.recent(30,True),diary=journal.recent(30),assistant_busy=assistant.busy,ros_status=ros.status,ros_event=ros.last_event,ollama=ollama.state(),firmware=firmware.state(),last_limits=last_limits)

try:
 for line in sys.stdin:
  try:
   request=json.loads(line)
   jarvis.update_ui(request.get("jarvis_ui"))
   assistant.language='en' if request.get('language')=='en' else 'it'
   op=request.get('op');extra={}
   if op=='studio_home_preview':extra={'home_preview':studio.preview_home(request.get('offsets'),request.get('model_hash'))}
   elif op=='multi_preview':extra={'multi_plan':server.c.preview_group(request.get('deltas'))}
   elif op=='voice_prepare':extra={'voice_command':server.c.prepare_voice(request.get('text'),request.get('language','it'))}
   elif op=='firmware_read':extra={'firmware_file':request['name'],'firmware_text':workspace.file(request['name']).read_text()}
   elif op=='firmware_save':workspace.save_file(request['name'],request['text'])
   elif op=='firmware_generate':workspace.generate(request['profile'])
   elif op=='firmware_upgrade_axes':workspace.upgrade_axis_control()
   elif op=='firmware_restore':workspace.restore()
   elif op=='firmware_export':workspace.export(request['path'])
   elif op.startswith('studio_'):studio.action(request)
   elif op=='chat':assistant.ask(request.get('text',''),request.get('llm',False))
   elif op=='ollama_start':ollama.start()
   elif op=='ollama_refresh':ollama.refresh_async()
   elif op=='ollama_stop':
    if assistant.busy:raise ValueError('Attendi la risposta in corso prima di fermare l’IA.')
    ollama.stop()
   elif op=='ollama_select':ollama.select(request.get('model',''))
   elif op=='firmware':firmware.start(request.get('operation',''),request.get('port',''),request.get('confirmed',False))
   elif op=='firmware_cancel':firmware.stop()
   elif op=='ros_connect':ros.start(request.get('project',''),request.get('domain',42))
   elif op=='ros_disconnect':ros.stop()
   elif op=='tool_start':tools.start(request['name'],request.get('project',''),request.get('domain',42),studio.model['root'])
   elif op=='tool_stop':tools.stop(request['name'])
   elif op=='tool_check':tools.project=request.get('project','')
   elif op=='api_start':api.start()
   elif op=='api_stop':api.stop()
   elif op=='api_permissions':
    if not api.server:raise ValueError('Avvia prima l’API locale.')
    api.commands.configure(request.get('enabled'),request.get('demo_execution'))
   elif op=='api_approve':api.commands.approve(request.get('id'),request.get('confirmed') is True)
   else:
    if op!='heartbeat':journal.add('request',server.c.mode,json.dumps(request,ensure_ascii=False))
    if op in ('play','home','pose_start'):studio.follow=True;studio.movej.running=False;studio.movej.visual_active=False
    server.c.action(request)
    if op=='limits':
     last_limits[server.c.mode]=[pair[:] for pair in server.c.limits]
     tmp=folder/'limiti.tmp';tmp.write_text(json.dumps(last_limits));tmp.replace(folder/'limiti.json')
   print(json.dumps(reply()),flush=True)
  except Exception as e:
   journal.add('error','app',str(e))
   print(json.dumps(dict(reply(),error=str(e))),flush=True)
finally:
 jarvis.close()
 api.stop()
 tools.close()
 studio.close()
 firmware.close()
 server.c.halt('App chiusa: STOP')
 ros.stop(wait=True)
 ollama.close()
