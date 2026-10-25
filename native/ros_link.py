# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import os,json,subprocess,threading,time
from pathlib import Path
class ROSLink:
 def __init__(self,folder,journal):
  self.folder=Path(folder);self.journal=journal;self.process=None;self.status='Disconnesso';self.last_event=''
 def start(self,project):
  if self.process and self.process.poll() is None:return
  root=Path(project).expanduser().resolve()
  if not (root/'pixi.toml').is_file() or not (root/'architetture/laboratorio').is_dir():raise ValueError('Seleziona il checkout DOC-Robotics con pixi.toml e architetture/laboratorio.')
  pixi='/opt/homebrew/bin/pixi'
  if not Path(pixi).is_file():raise ValueError('Pixi non disponibile.')
  env={**os.environ,'ROS_DOMAIN_ID':os.environ.get('ROS_DOMAIN_ID','42'),'PYTHONUNBUFFERED':'1'}
  # No launch of lab controller, microphone or hardware bridge.
  self.process=subprocess.Popen([pixi,'run','--manifest-path',str(root/'pixi.toml'),'python',str(Path(__file__).with_name('ros_observer.py')),str(self.folder/'ros_state.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  self.status='Avvio osservatore ROS 2…'
  p=self.process
  threading.Thread(target=self.read,args=(p,),daemon=True).start()
  threading.Thread(target=self.errors,args=(p,),daemon=True).start()
 def read(self,p):
  for line in p.stdout:
   try:
    e=json.loads(line);self.last_event=e['text'];self.status='Connesso · dominio '+os.environ.get('ROS_DOMAIN_ID','42')
    self.journal.add('ros',e['topic'],e['text'])
   except (ValueError,KeyError):pass
  if self.process is p:self.status='Osservatore terminato'
 def errors(self,p):
  for line in p.stderr:
   if line.strip():self.journal.add('ros_log','ROS 2',line.strip())
 def snapshot(self,state):
  tmp=self.folder/'ros_state.tmp'
  tmp.write_text(json.dumps(dict(time=time.time(),source='Robot Console',**{k:state[k] for k in ('mode','connected','home','pos','busy','speed','cycle')})))
  tmp.replace(self.folder/'ros_state.json')
 def stop(self):
  p=self.process;self.process=None
  if p and p.poll() is None:
   p.terminate()
   try:p.wait(timeout=2)
   except subprocess.TimeoutExpired:p.kill()
  self.status='Disconnesso'
