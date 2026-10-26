# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Arm projects, preview planning, program blocks and timestamped telemetry.
All execution requests pass through the existing controller. Model import never
opens serial or changes firmware. No automatic recovery or model downloads.
"""
import copy, csv, hashlib, io, json, math, os, shutil, tempfile, threading, time, uuid, zipfile
from pathlib import Path
from robot_model import default_urdf, parse_urdf, frames, tcp, position_ik, number

class Studio:
 def __init__(self,folder,controller,journal=None,builtin=True):
  self.folder=Path(folder)/'studio';self.folder.mkdir(parents=True,exist_ok=True)
  self.controller=controller;self.journal=journal;self.lock=threading.RLock()
  self.model=parse_urdf(default_urdf(6));self.model.update(approximate=True,schematic=True);self.raw=default_urdf(6).decode()
  self.project_name='DOC · progetto iniziale';self.preview={};self.enabled={};self.mapping={};self.calibration={};self.tool=[0,0,.10];self.tip=self.model['tip'];self.verified=False
  self.obstacles=[];self.blocks=[];self.sensors={};self.recording=False;self.samples=[];self.last_sample=0;self.selected='';self.follow=True;self.status='Modello schematico: dimensioni e HOME da calibrare.'
  self.program_running=False;self.program_index=-1;self.program_error='';self.cancel=threading.Event();self.program_thread=None
  self.reset_joints(default=True)
  if builtin and (Path(__file__).parent/'models/doc5/doc5.urdf').is_file():self.load_reference()
  try:
   if (self.folder/'project.json').exists():self.load_data(json.loads((self.folder/'project.json').read_text()))
  except (OSError,ValueError,KeyError,TypeError) as e:self.status='Progetto salvato non leggibile; modello iniziale attivo: '+str(e)
  if builtin and self.raw.encode() in (default_urdf(5),default_urdf(6)) and (Path(__file__).parent/'models/doc5/doc5.urdf').is_file():self.load_reference()
 def load_reference(self):
  source=Path(__file__).parent/'models/doc5/doc5.urdf';raw=source.read_bytes();directory=self.folder/'models'/('doc5-'+hashlib.sha256(raw).hexdigest()[:16]);directory.mkdir(parents=True,exist_ok=True)
  self.model=parse_urdf(raw,source.parent,directory);self.model.update(approximate=True,schematic=False);self.raw=raw.decode();self.reset_joints(True);self.tip=self.model['tip'];self.tool=[0,0,0];self.follow=True;self.verified=False
  for joint,offset in zip(self.independent(),self.model.get('nominal_home',[])):self.calibration[joint['name']]['offset']=offset
  self.status='Modello di visualizzazione Webots/presentazione, non CAD calibrato del DOC fisico.'
 def independent(self):return [j for j in self.model['joints'] if j['kind']!='fixed' and not j['mimic']]
 def effective_enabled(self):return {name:(self.controller.axes_enabled[self.mapping[name]] if self.mapping[name]>=0 else enabled) for name,enabled in self.enabled.items()}
 def reset_joints(self,default=False):
  self.preview={j['name']:max(j['lower'],min(j['upper'],0)) for j in self.independent()}
  self.enabled={j['name']:True for j in self.independent()};self.mapping={j['name']:i if default and i<6 else -1 for i,j in enumerate(self.independent())}
  self.calibration={j['name']:dict(sign=1,offset=0) for j in self.independent()};self.selected=self.independent()[0]['name']
 def idle_configuration(self):
  c=self.controller
  if c.connected or c.busy or c.playing or c.firmware_busy or self.program_running:raise ValueError('Scollega il controllo prima di cambiare modello, mapping o calibrazione.')
 def save(self):
  tmp=self.folder/'project.tmp';tmp.write_text(json.dumps(self.data(),ensure_ascii=False,indent=2));tmp.replace(self.folder/'project.json')
 def data(self):
  return dict(schema=1,name=self.project_name,model=self.model,urdf=self.raw,preview=self.preview,enabled=self.effective_enabled(),mapping=self.mapping,calibration=self.calibration,tool=self.tool,tip=self.tip,verified=self.verified,obstacles=self.obstacles,blocks=self.blocks,sensors={k:{**v,'value':None,'stamp':0} for k,v in self.sensors.items()})
 def load_data(self,data):
  fields=('model','raw','project_name','preview','enabled','mapping','calibration','tool','tip','verified','obstacles','blocks','sensors','follow','selected','status')
  previous={key:copy.deepcopy(getattr(self,key)) for key in fields}
  try:self._load_data(data)
  except Exception:
   for key,value in previous.items():setattr(self,key,value)
   raise
 def _load_data(self,data):
  if data.get('schema')!=1:raise ValueError('Versione progetto non supportata.')
  # Reparse URDF rather than trusting matrices or geometry from an imported JSON.
  checked=parse_urdf(data['urdf'].encode());old=data.get('model',{})
  checked['approximate']=bool(old.get('approximate',False))
  checked['schematic']=bool(old.get('schematic',False))
  old_visuals={link['name']:link.get('visuals',[]) for link in old.get('links',[])}
  for link in checked['links']:
   for index,visual in enumerate(link['visuals']):
    previous=old_visuals.get(link['name'],[])
    if index<len(previous):
     mesh=Path(previous[index].get('mesh',''))
     if mesh.is_file() and mesh.resolve().is_relative_to(self.folder.resolve()):visual['mesh']=str(mesh.resolve())
  self.model=checked;self.raw=data['urdf'];self.project_name=str(data.get('name',checked['name']))[:100];self.reset_joints()
  for joint in self.independent():
   name=joint['name'];self.preview[name]=number(data.get('preview',{}).get(name,0))
   self.enabled[name]=data.get('enabled',{}).get(name,True) is True
   axis=data.get('mapping',{}).get(name,-1)
   if type(axis)!=int or not -1<=axis<6:raise ValueError('Mapping hardware non valido.')
   self.mapping[name]=axis;c=data.get('calibration',{}).get(name,{})
   self.calibration[name]=dict(sign=number(c.get('sign',1),-1,1),offset=number(c.get('offset',0),-20,20))
   if self.calibration[name]['sign'] not in (-1,1):raise ValueError('Segno di calibrazione non valido.')
   calibrated=self.preview[name]*self.calibration[name]['sign']+self.calibration[name]['offset']
   if not joint['lower']-1e-6<=calibrated<=joint['upper']+1e-6:raise ValueError('Posizione salvata fuori dai limiti calibrati.')
  self.tool=[number(v,-2,2) for v in data.get('tool',[0,0,0])]
  if len(self.tool)!=3:raise ValueError('TCP non valido.')
  self.tip=data.get('tip',checked['tip'])
  if self.tip not in {l['name'] for l in checked['links']}:raise ValueError('Link TCP non valido.')
  # Imported projects never authorize physical motion by themselves.
  self.verified=False;self.obstacles=self.validate_obstacles(data.get('obstacles',[]))
  self.blocks=self.validate_blocks(data.get('blocks',[]));self.sensors={}
  for name,definition in data.get('sensors',{}).items():self.define_sensor(name,definition.get('kind','digital'))
  self.follow=False;self.status='Progetto caricato; verifica mapping, HOME e calibrazione prima dell’uso fisico.'
 def current_positions(self,state=None):
  state=state or self.controller.state();result=self.preview.copy();result['__gripper']=1. if state.get('grip')=='apri' else 0.
  if self.follow:
   values=state.get('preview_pos',state['pos'])
   for name,axis in self.mapping.items():
    if axis>=0:result[name]=math.radians(values[axis]) if next(j for j in self.independent() if j['name']==name)['kind']!='prismatic' else values[axis]/1000
  return result
 def collision_report(self,positions):
  f=frames(self.model,positions,self.calibration);hits=[]
  # Conservative link-origin segments against expanded axis-aligned workcell boxes.
  for j in self.model['joints']:
   a=[f[j['parent']][i][3] for i in range(3)];b=[f[j['child']][i][3] for i in range(3)]
   for box in self.obstacles:
    lo=[box['center'][i]-box['size'][i]/2-.025 for i in range(3)];hi=[box['center'][i]+box['size'][i]/2+.025 for i in range(3)]
    t0,t1=0.,1.
    for i in range(3):
     delta=b[i]-a[i]
     if abs(delta)<1e-12:
      if not lo[i]<=a[i]<=hi[i]:t0,t1=1,0;break
     else:
      x,y=sorted(((lo[i]-a[i])/delta,(hi[i]-a[i])/delta));t0=max(t0,x);t1=min(t1,y)
    if t0<=t1:hits.append(j['child']+' / '+box['name'])
  return hits
 def state(self):
  with self.lock:
   state=self.controller.state();positions=self.current_positions(state);f=frames(self.model,positions,self.calibration)
   live_positions=self.preview.copy()
   for joint in self.independent():
    axis=self.mapping[joint['name']]
    if axis>=0:live_positions[joint['name']]=math.radians(state.get('preview_pos',state['pos'])[axis]) if joint['kind']!='prismatic' else state.get('preview_pos',state['pos'])[axis]/1000
   live_frames=frames(self.model,live_positions,self.calibration)
   now=time.time()
   if self.recording and now-self.last_sample>=.20:
    self.samples.append(dict(time=now,mode=state['mode'],positions=positions.copy(),commanded=state['pos'],busy=state['busy'],grip=state['grip'],sensors=copy.deepcopy(self.sensors)))
    self.samples=self.samples[-18000:];self.last_sample=now
   return dict(name=self.project_name,model=self.model,positions=positions,enabled=self.effective_enabled(),mapping=self.mapping,calibration=self.calibration,tool=self.tool,tip=self.tip,verified=self.verified,selected=self.selected,follow=self.follow,status=self.status,
    live_frames=[dict(name=name,matrix=[v for row in matrix for v in row]) for name,matrix in live_frames.items()],frames=[dict(name=name,matrix=[v for row in matrix for v in row]) for name,matrix in f.items()],tcp=tcp(self.model,positions,self.calibration,self.tip,self.tool),collisions=self.collision_report(positions),obstacles=self.obstacles,blocks=self.blocks,sensors=[dict(name=k,**v,age=now-v['stamp'] if v['stamp'] else -1) for k,v in self.sensors.items()],recording=self.recording,sample_count=len(self.samples),program_running=self.program_running,program_index=self.program_index,program_error=self.program_error,
    telemetry=[dict(time=s['time'],values=s['commanded']) for s in self.samples[-180:]],capabilities=dict(physical_axes=self.controller.configured_axes,physical_prismatic=False,position_source='virtuale' if state['mode']=='demo' else 'stimata; senza encoder',calibrated=self.verified))
 def import_urdf(self,path):
  self.idle_configuration();source=Path(path).expanduser().resolve()
  if source.suffix.lower()!='.urdf':raise ValueError('Seleziona un file .urdf già espanso.')
  directory=self.folder/'models'/uuid.uuid4().hex;directory.mkdir(parents=True)
  try:
   raw=source.read_bytes();model=parse_urdf(raw,source.parent,directory)
   (directory/'source.urdf').write_bytes(raw)
  except Exception:shutil.rmtree(directory);raise
  text=raw.decode('utf-8');self.model=model;self.raw=text;self.tip=model['tip'];self.tool=[0,0,0];self.verified=False;self.follow=False;self.reset_joints();self.obstacles=[]
  self.status='URDF importato. Associa esplicitamente i giunti ai canali J1–J6; nessuna impostazione firmware modificata.';self.save()
 @staticmethod
 def validate_obstacles(boxes):
  if not isinstance(boxes,list) or len(boxes)>40:raise ValueError('Massimo 40 ostacoli.')
  result=[]
  for box in boxes:
   center=[number(v,-10,10) for v in box['center']];size=[number(v,.001,10) for v in box['size']]
   if len(center)!=3 or len(size)!=3:raise ValueError('Dimensioni ostacolo non valide.')
   result.append(dict(name=str(box.get('name','Ostacolo'))[:60],center=center,size=size))
  return result
 def target_path(self,positions):
  c=self.controller
  if c.mode=='robot' and not self.verified:raise ValueError('Conferma prima la corrispondenza fisica di modello, mapping e calibrazione.')
  if self.collision_report(positions):raise ValueError('Interferenza geometrica rilevata nell’anteprima.')
  targets=c.pos[:];mapped=set()
  for j in self.independent():
   name=j['name'];axis=self.mapping[name];q=number(positions[name]);cal=self.calibration[name]
   if not j['lower']-1e-6<=q*cal['sign']+cal['offset']<=j['upper']+1e-6:raise ValueError('Target fuori dai limiti URDF calibrati.')
   if not self.effective_enabled()[name]:
    if axis>=0 and abs(q-math.radians(c.pos[axis]))>1e-6:raise ValueError('Target diverso dalla posizione del giunto escluso '+name)
    continue
   if axis<0:
    if abs(q)>1e-6:raise ValueError('Il giunto '+name+' non è associato a un motore.')
    continue
   if axis in mapped:raise ValueError('Più giunti associati allo stesso motore.')
   if j['kind']=='prismatic':raise ValueError('Il firmware attuale comanda assi rotativi: giunti prismatici disponibili solo in anteprima.')
   mapped.add(axis);targets[axis]=round(math.degrees(q),2)
  path=[]
  for axis,target in enumerate(targets):
   delta=round(target-c.pos[axis],2)
   if abs(delta)>.001:
    c.validate(axis,delta);path.append(dict(axis=axis,delta=delta))
  # Check intermediate sequential segments, not only the final target.
  start=positions.copy();by_axis={a:n for n,a in self.mapping.items() if a>=0}
  for name,axis in self.mapping.items():
   if axis>=0:start[name]=math.radians(c.pos[axis])
  if self.collision_report(start):raise ValueError('Interferenza alla posizione iniziale del modello.')
  for step in path:
   name=by_axis[step['axis']];initial=start[name];final=positions[name]
   for index in range(1,21):
    trial=start.copy();trial[name]=initial+(final-initial)*index/20
    if self.collision_report(trial):raise ValueError('Interferenza lungo il percorso sequenziale: modifica il target o gli ostacoli.')
   start[name]=final
  return path
 def execute_preview(self):
  c=self.controller
  with c.lock:
   c.check()
   if c.busy or c.playing or self.program_running:raise ValueError('Controllore occupato.')
   positions=self.preview.copy();path=self.target_path(positions)
   def run(g):
    for step in path:c.move(step['axis'],step['delta'],g)
   c.spawn(run)
  self.follow=True
 def define_sensor(self,name,kind):
  if not isinstance(name,str) or not name or len(name)>60 or kind not in ('digital','distance','force','encoder','temperature'):raise ValueError('Definizione sensore non valida.')
  if name not in self.sensors and len(self.sensors)>=64:raise ValueError('Massimo 64 sensori.')
  self.sensors[name]=dict(kind=kind,value=None,stamp=0.,source='non collegato')
 def sensor_value(self,name,value,source='simulato'):
  if name not in self.sensors:raise ValueError('Definisci prima il sensore.')
  if type(value) not in (bool,int,float) or (type(value)!=bool and not math.isfinite(value)):raise ValueError('Valore sensore non valido.')
  self.sensors[name].update(value=value,stamp=time.time(),source=source)
 @staticmethod
 def validate_blocks(blocks):
  if not isinstance(blocks,list) or len(blocks)>200:raise ValueError('Massimo 200 blocchi.')
  result=[]
  for raw in blocks:
   b=copy.deepcopy(raw);kind=b.get('kind')
   if kind not in ('pose','grip','wait','sensor','repeat','note'):raise ValueError('Tipo di blocco non supportato.')
   b['name']=str(b.get('name',kind))[:80];b['enabled']=b.get('enabled',True) is True
   if kind=='pose':
    b['index']=int(number(b.get('index',0),0,10000))
   if kind=='grip' and b.get('command') not in ('apri','chiudi'):raise ValueError('Comando pinza non valido.')
   if kind=='wait':b['seconds']=number(b.get('seconds',1),0,600)
   if kind=='sensor':b['sensor']=str(b.get('sensor',''))[:60];b['expected']=number(b.get('expected',1));b['timeout']=number(b.get('timeout',10),.1,600)
   if kind=='repeat':b['start']=int(number(b.get('start',0),0,199));b['count']=int(number(b.get('count',2),1,100))
   result.append(b)
  # Loops are bounded and cannot contain other loop blocks.
  for i,b in enumerate(result):
   if b['kind']=='repeat' and (b['start']>=i or any(x['kind']=='repeat' for x in result[b['start']:i])):raise ValueError('Ripeti deve riferirsi a blocchi precedenti senza cicli annidati.')
  return result
 def expanded_program(self):
  result=[]
  for i,b in enumerate(self.blocks):
   if not b['enabled']:continue
   if b['kind']=='repeat':result.extend([(k,copy.deepcopy(self.blocks[k])) for _ in range(b['count']-1) for k in range(b['start'],i) if self.blocks[k]['enabled']])
   else:result.append((i,copy.deepcopy(b)))
   if len(result)>2000:raise ValueError('Programma oltre 2000 istruzioni espanse.')
  return result
 def run_program(self):
  c=self.controller
  with c.lock:
   c.check()
   if c.busy or c.playing or self.program_running or c.trail:raise ValueError('Avvia da HOME e da fermo.')
   steps=self.expanded_program()
   if not steps:raise ValueError('Aggiungi almeno un blocco.')
   sequence=copy.deepcopy(c.sequence)
   for _,b in steps:
    if b['kind']=='pose' and not 0<=b['index']<len(sequence):raise ValueError('Posa del blocco non presente.')
   steps=[(i,b) for i,b in steps if b['kind']!='pose' or sequence[b['index']].get('enabled',True)]
   if not steps:raise ValueError('Tutte le pose del programma sono escluse.')
   for _,b in steps:
    if b['kind']=='pose':
     if not 0<=b['index']<len(sequence):raise ValueError('Posa del blocco non presente.')
     pose=sequence[b['index']]
     if pose.get('mode')!=c.mode:raise ValueError('Posa appartenente a una modalità diversa.')
     c.validate_path(pose['path']);p=[0.]*6
     for step in pose['path']:
      p[step['axis']]+=step['delta']
      if not c.limits[step['axis']][0]<=p[step['axis']]<=c.limits[step['axis']][1]:raise ValueError('Programma fuori limite.')
     if any(abs(a-b)>.02 for a,b in zip(p,pose['pos'])):raise ValueError('Posa incoerente.')
    if b['kind']=='sensor' and b['sensor'] not in self.sensors:raise ValueError('Sensore del blocco non definito.')
   self.program_running=True;self.program_error='';self.cancel.clear();generation=c.generation
   def run(g):
    def check():
     if self.cancel.is_set() or g!=c.generation:raise ValueError('Programma interrotto; nessuna ripresa automatica.')
     while c.paused:
      if self.cancel.is_set() or g!=c.generation:raise ValueError('Programma interrotto; nessuna ripresa automatica.')
      time.sleep(.03)
    def wait(seconds):
     deadline=time.monotonic()+seconds
     while time.monotonic()<deadline:
      check();time.sleep(.03)
    try:
     for index,b in steps:
      check();self.program_index=index
      if b['kind']=='pose':
       pose=sequence[b['index']];c.follow_path(pose['path'],g)
       if pose.get('grip') in ('apri','chiudi'):c.servo(pose['grip'],g)
       wait(pose.get('dwell',0))
      elif b['kind']=='grip':c.servo(b['command'],g)
      elif b['kind']=='wait':wait(b['seconds'])
      elif b['kind']=='sensor':
       deadline=time.monotonic()+b['timeout']
       while True:
        check();sensor=self.sensors[b['sensor']]
        fresh=time.time()-sensor['stamp']<1
        trusted=c.mode=='demo' or sensor['source'] not in ('simulato','non collegato')
        if fresh and trusted and sensor['value']==b['expected']:break
        if time.monotonic()>deadline:raise ValueError('Timeout sensore: '+b['sensor'])
        time.sleep(.03)
      elif b['kind']=='note':c.log(b['name'])
     c.back(g);c.cycle+=1;c.log('Programma completato e ritorno a HOME nel conteggio impulsi.')
    except Exception as error:self.program_error=str(error);raise
    finally:self.program_running=False;self.program_index=-1
   c.playing=True;c.spawn(run)
 def preview_sequence(self,index,fraction):
  poses=[p for p in self.controller.sequence if p.get('enabled',True)]
  if not poses:raise ValueError('Nessuna posa abilitata da visualizzare.')
  if not 0<=index<len(poses):raise ValueError('Posa non valida.')
  fraction=number(fraction,0,1)
  previous=[] if index==0 else poses[index-1]['path'];following=poses[index]['path'];common=0
  while common<min(len(previous),len(following)) and previous[common]==following[common]:common+=1
  segments=[dict(axis=x['axis'],delta=-x['delta']) for x in reversed(previous[common:])]+following[common:]
  self.controller.validate_path(segments)
  values=[0.]*6
  for step in previous:values[step['axis']]+=step['delta']
  distance=sum(abs(x['delta']) for x in segments)*fraction
  for step in segments:
   part=min(distance,abs(step['delta']));values[step['axis']]+=math.copysign(part,step['delta']);distance-=part
   if distance<=0:break
  self.follow=False
  for j in self.independent():
   axis=self.mapping[j['name']]
   if axis>=0 and self.effective_enabled()[j['name']]:self.preview[j['name']]=math.radians(values[axis])
  self.status='Anteprima del percorso registrato, inclusi i tratti a ritroso; nessun comando al robot.'
 def export_recording(self,path):
  output=io.StringIO();writer=csv.writer(output);writer.writerow(['time','mode','j1_deg','j2_deg','j3_deg','j4_deg','j5_deg','j6_deg','busy','gripper'])
  for s in self.samples:writer.writerow([s['time'],s['mode'],*s['commanded'],s['busy'],s['grip']])
  Path(path).write_text(output.getvalue());self.status='Registrazione CSV esportata.'
 def export_project(self,path):
  data=copy.deepcopy(self.data());data['urdf']=self.visualization_urdf(relative=True)
  data['sequence']=copy.deepcopy(self.controller.sequence);data['firmware_identity']=getattr(self.controller,'expected_profile','')
  with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
   for link in data['model']['links']:
    for visual in link['visuals']:
     if visual.get('mesh'):
      p=Path(visual['mesh']);name='meshes/'+p.name
      if name not in archive.namelist():archive.write(p,name)
      visual['mesh']=name
   archive.writestr('robot.urdf',data['urdf']);archive.writestr('project.json',json.dumps(data,ensure_ascii=False,indent=2));archive.writestr('NOTICE.txt','URDF e mesh importati dall’utente: verificare le rispettive licenze prima della ridistribuzione. Nessuna conversazione o credenziale inclusa.\n')
  self.status='Progetto esportato senza conversazioni, credenziali o autorizzazioni hardware.'
 def import_project(self,path):
  self.idle_configuration();destination=self.folder/'models'/uuid.uuid4().hex;destination.mkdir(parents=True)
  try:
   with zipfile.ZipFile(path) as archive:
    infos=archive.infolist()
    if len(infos)>600 or sum(i.file_size for i in infos)>200_000_000:raise ValueError('Progetto troppo grande.')
    for info in infos:
     p=Path(info.filename)
     if p.is_absolute() or '..' in p.parts or ((info.external_attr>>16)&0o170000)==0o120000:raise ValueError('Percorso non consentito nel progetto.')
     if info.filename not in ('project.json','NOTICE.txt','robot.urdf') and not (len(p.parts)==2 and p.parts[0]=='meshes' and p.suffix.lower() in ('.stl','.obj','.dae')):raise ValueError('File non consentito nel progetto.')
    data=json.loads(archive.read('project.json'))
    for link in data.get('model',{}).get('links',[]):
     for visual in link.get('visuals',[]):
      mesh=visual.get('mesh','')
      if mesh:
       if mesh not in archive.namelist() or not mesh.startswith('meshes/'):raise ValueError('Mesh del progetto non valida.')
       target=destination/Path(mesh).name;target.write_bytes(archive.read(mesh));visual['mesh']=str(target)
   sequence=self.validate_project_sequence(data.get('sequence',[]))
   self.load_data(data)
   for name,enabled in self.enabled.items():
    if not enabled and self.mapping[name]>=0:self.controller.action(dict(op='joint_enable',axis=self.mapping[name],enabled=False))
   if 'sequence' in data:
    self.controller.sequence_undo=copy.deepcopy(self.controller.sequence);self.controller.sequence=sequence;self.controller.save()
   self.save()
  except Exception:shutil.rmtree(destination);raise
 @staticmethod
 def validate_project_sequence(sequence):
  if not isinstance(sequence,list) or len(sequence)>1000:raise ValueError('Sequenza progetto non valida.')
  result=[]
  for raw in sequence:
   name=raw.get('name','');mode=raw.get('mode');grip=raw.get('grip','non comandata');enabled=raw.get('enabled',True)
   if not isinstance(name,str) or not name.strip() or len(name)>60 or mode not in ('robot','demo') or grip not in ('apri','chiudi','non comandata') or type(enabled)!=bool:raise ValueError('Metadati posa non validi.')
   pos=[number(v,-360,360) for v in raw['pos']]
   if len(pos)==5:pos.append(0.)
   if len(pos)!=6 or not isinstance(raw['path'],list) or len(raw['path'])>4000:raise ValueError('Percorso posa non valido.')
   total=[0.]*6;path=[]
   for step in raw['path']:
    axis=step['axis'];delta=number(step['delta'],-360,360)
    if type(axis)!=int or not 0<=axis<6:raise ValueError('Asse della posa non valido.')
    total[axis]+=delta
    if abs(total[axis])>360.01:raise ValueError('Percorso posa oltre gli angoli ammessi.')
    path.append(dict(axis=axis,delta=delta))
   if any(abs(a-b)>.02 for a,b in zip(total,pos)):raise ValueError('Posa e percorso non coerenti.')
   result.append(dict(name=name,mode=mode,grip=grip,enabled=enabled,pos=pos,path=path,dwell=number(raw.get('dwell',0),0,60)))
  return result
 def visualization_urdf(self,relative=False):
  import xml.etree.ElementTree as ET
  tree=ET.fromstring(self.raw);assets={}
  for link in self.model['links']:
   for visual in link['visuals']:
    if visual.get('source_mesh') and visual.get('mesh'):assets[visual['source_mesh']]=visual['mesh']
  for element in tree.iter():
   for child in list(element):
    if child.tag=='texture':element.remove(child)
    if child.tag=='mesh':
     asset=assets.get(child.get('filename',''))
     if asset:child.set('filename','meshes/'+Path(asset).name if relative else Path(asset).as_uri())
     else:
      element.remove(child);ET.SubElement(element,'box',size='0.04 0.04 0.04')
  return ET.tostring(tree,encoding='unicode')
 def ros_snapshot(self):
  state=self.controller.state();positions=self.current_positions(state);cal=self.calibration
  values={j['name']:positions[j['name']]*cal[j['name']]['sign']+cal[j['name']]['offset'] for j in self.independent()}
  return dict(model=self.model,positions=values,gripper=positions.get('__gripper',0),source='preview' if not self.follow or state['mode']=='demo' else 'command_estimate',prefix='robot_console/',urdf=self.visualization_urdf())
 def action(self,request):
  op=request['op'];c=self.controller
  with self.lock:
   if op=='studio_import':self.import_urdf(request['path'])
   elif op=='studio_default':
    self.idle_configuration();self.load_reference();self.save()
   elif op=='studio_preview':
    name=request['joint'];j=next(j for j in self.independent() if j['name']==name)
    if not self.effective_enabled()[name]:raise ValueError('Giunto escluso dall’anteprima.')
    v=number(request['value']);cal=self.calibration[name];angle=v*cal['sign']+cal['offset']
    if not j['lower']-1e-6<=angle<=j['upper']+1e-6:raise ValueError('Target fuori dai limiti URDF.')
    if self.follow:self.preview=self.current_positions()
    self.preview[name]=v;self.follow=False;self.selected=name
   elif op=='studio_follow':self.follow=bool(request['enabled'])
   elif op=='studio_select':self.selected=str(request['joint'])
   elif op=='studio_joint':
    name=request['joint']
    if name not in self.enabled:raise ValueError('Giunto non presente.')
    if 'enabled' in request:
     enabled=request['enabled']
     if type(enabled)!=bool:raise ValueError('Abilitazione non valida.')
     axis=self.mapping[name]
     if axis>=0:c.action(dict(op='joint_enable',axis=axis,enabled=enabled))
     self.enabled[name]=enabled
    if any(k in request for k in ('axis','offset','sign')):
     self.idle_configuration();axis=request.get('axis',self.mapping[name])
     if type(axis)!=int or not -1<=axis<6:raise ValueError('Canale hardware non valido.')
     if axis>=0 and any(v==axis and key!=name for key,v in self.mapping.items()):raise ValueError('Canale già associato a un altro giunto.')
     sign=number(request.get('sign',self.calibration[name]['sign']),-1,1)
     if sign not in (-1,1):raise ValueError('Segno ammesso: −1 o +1.')
     self.calibration[name]=dict(sign=sign,offset=number(request.get('offset',self.calibration[name]['offset']),-20,20));self.mapping[name]=axis;self.verified=False
    self.save()
   elif op=='studio_tcp':
    self.idle_configuration();tip=request['tip'];tool=[number(v,-2,2) for v in request['tool']]
    if tip not in {l['name'] for l in self.model['links']} or len(tool)!=3:raise ValueError('TCP non valido.')
    self.tip=tip;self.tool=tool;self.verified=False;self.save()
   elif op=='studio_verified':
    self.idle_configuration();self.verified=request.get('confirmed') is True;self.status='Corrispondenza fisica dichiarata dall’operatore; la console non la misura.';self.save()
   elif op=='studio_ik':
    enabled=self.effective_enabled()
    result=position_ik(self.model,self.current_positions(),request['target'],enabled,self.calibration,self.tip,self.tool)
    self.status=('Target raggiungibile nel modello' if result['converged'] else 'Target non raggiunto: soluzione approssimata')+' · errore %.2f mm'%(result['error_m']*1000)
    self.preview=result['positions'];self.follow=False
   elif op=='studio_execute':
    if request.get('confirmed') is not True:raise ValueError('Conferma esplicita richiesta.')
    self.execute_preview()
   elif op=='studio_obstacles':self.idle_configuration();self.obstacles=self.validate_obstacles(request['boxes']);self.save()
   elif op=='studio_blocks':
    if c.busy or c.playing or self.program_running:raise ValueError('Attendi prima di modificare il programma.')
    self.blocks=self.validate_blocks(request['blocks']);self.save()
   elif op=='studio_run':
    if request.get('confirmed') is not True:raise ValueError('Conferma esplicita richiesta.')
    self.run_program()
   elif op=='studio_cancel':self.cancel.set();c.action(dict(op='stop'))
   elif op=='studio_record':
    enabled=request.get('enabled') is True
    if enabled and not self.recording:self.samples=[]
    self.recording=enabled
   elif op=='studio_export_csv':self.export_recording(request['path'])
   elif op=='studio_export':self.idle_configuration();self.export_project(request['path'])
   elif op=='studio_open':self.import_project(request['path'])
   elif op=='studio_sensor_add':self.define_sensor(request['name'],request.get('kind','digital'));self.save()
   elif op=='studio_sensor_value':
    if c.mode!='demo':raise ValueError('Gli ingressi sintetici sono disponibili solo in Anteprima.')
    self.sensor_value(request['name'],request['value'])
   elif op=='studio_sequence':self.preview_sequence(int(request['index']),request['fraction'])
   elif op=='studio_save':self.project_name=str(request.get('name',self.project_name))[:100];self.save();self.status='Progetto salvato.'
   else:raise ValueError('Operazione Studio non valida.')
 def close(self):
  self.cancel.set()
  if self.program_thread:self.program_thread.join(timeout=2)
