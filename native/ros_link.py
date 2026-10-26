# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import json,os,shutil,subprocess,threading,time
from pathlib import Path
class ROSLink:
 def __init__(self,folder,journal):
  self.folder=Path(folder);self.journal=journal;self.process=None;self.status='Disconnesso';self.last_event='';self.domain=42;self.project='';self.health={};self.started=0
 def start(self,project,domain=42):
  if self.process and self.process.poll() is None:return
  root=Path(project).expanduser().resolve()
  if not (root/'pixi.toml').is_file():raise ValueError('Seleziona un progetto ROS/Pixi con pixi.toml.')
  if type(domain)!=int or not 0<=domain<=232:raise ValueError('Dominio ROS ammesso: 0–232.')
  pixi=shutil.which('pixi') or '/opt/homebrew/bin/pixi'
  if not Path(pixi).is_file():raise ValueError('Pixi non disponibile.')
  if not (root/'.pixi/envs/default/bin/python').exists():raise ValueError('Ambiente non preparato: esegui pixi install nel progetto. Nessuna installazione automatica.')
  self.domain=domain;self.project=str(root);self.health={};self.started=time.time()
  env={**os.environ,'ROS_DOMAIN_ID':str(domain),'PYTHONUNBUFFERED':'1','ROS_AUTOMATIC_DISCOVERY_RANGE':'LOCALHOST'}
  self.process=subprocess.Popen([pixi,'run','--frozen','--no-install','--manifest-path',str(root/'pixi.toml'),'python',str(Path(__file__).with_name('ros_observer.py')),str(self.folder/'ros_state.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  self.status='Avvio osservatore ROS 2…';p=self.process
  threading.Thread(target=self.read,args=(p,),daemon=True).start();threading.Thread(target=self.errors,args=(p,),daemon=True).start()
 def state(self):
  running=bool(self.process and self.process.poll() is None);now=time.time();health=self.health.copy();age=now-health.get('time',self.started) if running else -1
  topics=[dict(name=k,age=now-v) for k,v in health.get('topics',{}).items() if k.startswith('/laboratorio/')]
  recent=any(t['age']<5 for t in topics)
  status=('Laboratorio rilevato' if recent else 'Osservatore attivo · nessun dato laboratorio recente') if running and age<4 else ('Osservatore senza heartbeat' if running else self.status)
  return dict(running=running,status=status,domain=self.domain,project=self.project,age=age,nodes=health.get('nodes',[]),topics=topics,error=health.get('error',''),visualization_topic='/robot_console/joint_states',frame_prefix='robot_console/')
 def read(self,p):
  for line in p.stdout:
   try:
    event=json.loads(line)
    if 'health' in event:self.health=event['health'];continue
    self.last_event=event['text'];self.journal.add('ros',event['topic'],event['text'])
   except (ValueError,KeyError):pass
  if self.process is p:self.status='Osservatore terminato'
 def errors(self,p):
  for line in p.stderr:
   if line.strip():self.journal.add('ros_log','ROS 2',line.strip())
 def snapshot(self,state,visualization=None):
  tmp=self.folder/'ros_state.tmp';tmp.write_text(json.dumps(dict(time=time.time(),console=state,visualization=visualization)));tmp.replace(self.folder/'ros_state.json')
 def stop(self,wait=False):
  p=self.process;self.process=None
  if p and p.poll() is None:
   p.terminate()
   def finish():
    try:p.wait(timeout=2)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=2)
   if wait:finish()
   else:threading.Thread(target=finish,daemon=True).start()
  self.status='Disconnesso'
