# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Explicit optional tools; only processes started by this app can be stopped."""
import json,os,shutil,subprocess,threading,time
from pathlib import Path
class ToolManager:
 def __init__(self,folder,journal):
  self.folder=Path(folder)/'tools';self.folder.mkdir(parents=True,exist_ok=True);self.journal=journal;self.processes={};self.error='';self.project=''
 def available(self,name,project):
  root=Path(project).expanduser()
  binary={'rviz':'rviz2','gazebo':'gz','bag':'ros2','webots':'/Applications/Webots.app/Contents/MacOS/webots'}.get(name,'')
  return bool(binary and (Path(binary).is_file() if binary.startswith('/') else (root/'.pixi/envs/default/bin'/binary).is_file()))
 def state(self):return dict(project=self.project,error=self.error,tools=[dict(name=name,available=self.available(name,self.project),running=name in self.processes and self.processes[name].poll() is None) for name in ('rviz','gazebo','webots','bag')])
 def start(self,name,project,domain=42,root_frame='base'):
  self.project=str(Path(project).expanduser().resolve());root=Path(self.project)
  if name in self.processes and self.processes[name].poll() is None:return
  if not self.available(name,project):raise ValueError('Strumento '+name+' non trovato nel progetto selezionato.')
  if type(domain)!=int or not 0<=domain<=232:raise ValueError('Dominio ROS non valido.')
  pixi=shutil.which('pixi') or '/opt/homebrew/bin/pixi';prefix=[pixi,'run','--frozen','--no-install','--manifest-path',str(root/'pixi.toml')]
  env={**os.environ,'ROS_DOMAIN_ID':str(domain),'ROS_AUTOMATIC_DISCOVERY_RANGE':'LOCALHOST'}
  if name=='rviz':
   config=self.folder/'robot-console.rviz';config.write_text('Panels: []\nVisualization Manager:\n  Class: ""\n  Global Options:\n    Fixed Frame: '+json.dumps('robot_console/'+root_frame)+'\n  Displays:\n    - Class: rviz_default_plugins/Grid\n      Name: Grid\n      Enabled: true\n    - Class: rviz_default_plugins/TF\n      Name: Frames\n      Enabled: true\n    - Class: rviz_default_plugins/RobotModel\n      Name: Robot Console\n      Enabled: true\n      Description Source: Topic\n      Description Topic:\n        Value: /robot_console/robot_description\n      TF Prefix: robot_console\n')
   args=prefix+['rviz2','-d',str(config)]
  elif name=='gazebo':args=prefix+['gz','sim','-v','2','shapes.sdf']
  elif name=='webots':
   world=root/'webots_sim/worlds/laboratorio.wbt'
   if not world.is_file():raise ValueError('Mondo laboratorio non trovato nel progetto.')
   args=['/Applications/Webots.app/Contents/MacOS/webots','--mode=pause',str(world)]
  else:
   output=self.folder/('rosbag-'+time.strftime('%Y%m%d-%H%M%S'))
   args=prefix+['ros2','bag','record','-o',str(output),'/robot_console/joint_states','/robot_console/robot_description','/tf','/doc_regia/stato','/laboratorio/stato','/laboratorio/esito']
  log=(self.folder/(name+'.log')).open('a')
  try:self.processes[name]=subprocess.Popen(args,env=env,stdout=log,stderr=subprocess.STDOUT,cwd=root)
  finally:log.close()
  self.error='';self.journal.add('tool',name,'Avviato esplicitamente dalla console; log in '+str(self.folder/(name+'.log')))
 def stop(self,name,wait=False):
  p=self.processes.get(name)
  if p and p.poll() is None:
   # SIGINT lets rosbag finalize its index and keeps recorded files usable.
   import signal;p.send_signal(signal.SIGINT)
   def finish():
    try:p.wait(timeout=4)
    except subprocess.TimeoutExpired:
     p.terminate()
     try:p.wait(timeout=2)
     except subprocess.TimeoutExpired:p.kill()
   if wait:finish()
   else:threading.Thread(target=finish,daemon=True).start()
 def close(self):
  for name in list(self.processes):self.stop(name,wait=True)
