# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Arm projects, preview planning, program blocks and timestamped telemetry.
All execution requests pass through the existing controller. Model import never
opens serial or changes firmware. No automatic recovery or model downloads.
"""
import copy, csv, hashlib, io, json, math, os, shutil, tempfile, threading, time, uuid, zipfile
from pathlib import Path
from robot_model import default_urdf, parse_urdf, frames, tcp, number
from work_scene import validate_scene, scene_state
from movej_studio import MoveJPreview
from ik_studio import CartesianPreview
from collision import Geometry
from validation import validate
from program_plan import is_motion_program
import program_lang
import program_functions
from movej_preview import coordinates
from io_adapters import AdapterHub, digital

class Studio:
 def __init__(self,folder,controller,journal=None,builtin=True):
  self.folder=Path(folder)/'studio';self.folder.mkdir(parents=True,exist_ok=True)
  self.controller=controller;self.journal=journal;self.lock=threading.RLock()
  self.model=parse_urdf(default_urdf(6));self.model.update(approximate=True,schematic=True);self.raw=default_urdf(6).decode()
  self.project_name='DOC · progetto iniziale';self.preview={};self.enabled={};self.mapping={};self.calibration={};self.tool=[0,0,.10];self.tip=self.model['tip'];self.verified=False
  self.work_frames=[];self.cartesian_targets=[];self.selected_target=''
  self.outputs={};self.io=AdapterHub(self)
  self.obstacles=[];self.blocks=[];self.sensors={};self.recording=False;self.samples=[];self.last_sample=0;self.selected='';self.follow=True;self.status='Modello schematico: dimensioni e HOME da calibrare.'
  self.program_running=False;self.program_index=-1;self.program_error='';self.cancel=threading.Event();self.program_thread=None
  self.movej=MoveJPreview(self);self.cartesian=CartesianPreview(self)
  self.workcell=dict(floor=True,margin=.01);self._geometry=None;self.validation=None
  controller.preflight=self.preflight
  self.reset_joints(default=True)
  if builtin and (Path(__file__).parent/'models/doc5/doc5.urdf').is_file():self.load_reference()
  try:
   if (self.folder/'project.json').exists():
    saved=json.loads((self.folder/'project.json').read_text());self.load_data(saved)
    if saved.get('schema')==1:
     shutil.copy2(self.folder/'project.json',self.folder/('project-prima-schema2-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json'))
     self.save()
  except (OSError,ValueError,KeyError,TypeError) as e:self.status='Progetto salvato non leggibile; modello iniziale attivo: '+str(e)
  if builtin and self.raw.encode() in (default_urdf(5),default_urdf(6)) and (Path(__file__).parent/'models/doc5/doc5.urdf').is_file():self.load_reference()
  bundled=Path(__file__).parent/'models/doc5/doc5.urdf'
  if builtin and self.model.get('reference')=='doc5-presentation' and bundled.is_file() and self.raw.encode()!=bundled.read_bytes():self.upgrade_reference()
  elif builtin and self.model.get('reference')=='doc5-presentation':
   import eb15_model
   try:eb15_model.adopt(self.model,self.folder)
   except (OSError,ValueError):pass
   if self.model.get('mesh_variant')!=self.reference_variant()[0]:self.switch_reference_meshes()
 def upgrade_reference(self):
  # The bundled DOC model changed (older illustrative model -> EB-15 assembly): keep mapping, signs and scene; offsets follow the new nominal HOME.
  backup=None
  if (self.folder/'project.json').exists():backup=self.folder/('project-prima-modello-'+time.strftime('%Y%m%d-%H%M%S')+'.json');shutil.copy2(self.folder/'project.json',backup)
  mapping,enabled,signs=dict(self.mapping),dict(self.enabled),{k:v['sign'] for k,v in self.calibration.items()}
  kept=(self.project_name,self.obstacles,self.blocks,self.sensors,self.outputs)
  self.load_reference()
  for name in self.mapping:
   if name in mapping:self.mapping[name]=mapping[name];self.enabled[name]=enabled.get(name,True);self.calibration[name]['sign']=signs.get(name,1)
  self.project_name,self.obstacles,self.blocks,self.sensors,self.outputs=kept;self.save()
  self.status='Modello DOC aggiornato ai pezzi EB-15; offset riportati alla HOME nominale.'+(' Copia del progetto precedente: '+backup.name if backup else '')
 def attach_reference_collision(self,model,raw):
  """The bundled DOC URDF carries a measured collision envelope (models/doc5/collision.json)."""
  folder=Path(__file__).parent/'models/doc5'
  try:
   if raw!=(folder/'doc5.urdf').read_bytes():return
   links=json.loads((folder/'collision.json').read_text())['links']
   known={link['name'] for link in model['links']}
   capsules={name:[dict(a=[number(v,-2,2) for v in c['a']],b=[number(v,-2,2) for v in c['b']],r=number(c['r'],.001,.5)) for c in items] for name,items in links.items() if name in known and len(items)<=8}
  except (OSError,ValueError,KeyError,TypeError):return
  model['collision_capsules']=capsules
 def reference_variant(self):
  """Detailed EB-15 meshes generated on this computer, else the bundled schematic ones."""
  import eb15_model
  folder=eb15_model.installed(self.folder)
  return ('eb15',folder) if folder else ('schematic',Path(__file__).parent/'models/doc5')
 def load_reference(self):
  source=Path(__file__).parent/'models/doc5/doc5.urdf';raw=source.read_bytes();variant,base=self.reference_variant()
  directory=self.folder/'models'/('doc5-'+hashlib.sha256(raw+variant.encode()).hexdigest()[:16]);directory.mkdir(parents=True,exist_ok=True)
  self.model=parse_urdf(raw,base,directory);self.model.update(approximate=True,schematic=False,mesh_variant=variant);self.attach_reference_collision(self.model,raw);self.raw=raw.decode();self.reset_joints(True);self.tip=self.model['tip'];self.tool=[0,0,0];self.follow=True;self.verified=False
  for joint,offset in zip(self.independent(),self.model.get('nominal_home',[])):self.calibration[joint['name']]['offset']=offset
  self.status=('Modello DOC con i pezzi EB-15 generati su questo computer; ' if variant=='eb15' else 'Modello DOC schematico; ')+'non CAD calibrato del DOC fisico.'
 def switch_reference_meshes(self):
  """Same URDF and joint frames with other display meshes: keep mapping, calibration and scene."""
  keep=(copy.deepcopy(self.mapping),copy.deepcopy(self.enabled),copy.deepcopy(self.calibration),self.tool[:],self.tip,self.verified,self.project_name,self.obstacles,self.blocks,self.sensors,self.outputs)
  self.load_reference()
  mapping,enabled,calibration,self.tool,self.tip,self.verified,self.project_name,self.obstacles,self.blocks,self.sensors,self.outputs=keep
  for name in self.mapping:
   if name in mapping:self.mapping[name]=mapping[name];self.enabled[name]=enabled.get(name,True);self.calibration[name]=calibration.get(name,self.calibration[name])
  self._geometry=None;self.save()
 def import_eb15(self,paths):
  import eb15_model
  self.idle_configuration()
  if not isinstance(paths,list) or not paths or not all(isinstance(p,str) for p in paths):raise ValueError('Scegli i pacchetti EB-15 ed EBG-30 scaricati da Thingiverse.')
  report=eb15_model.install(paths,self.folder)
  if self.model.get('reference')=='doc5-presentation':self.switch_reference_meshes()
  self.status='Modello EB-15 generato localmente: %d mesh.'%report['meshes']
 def independent(self):return [j for j in self.model['joints'] if j['kind']!='fixed' and not j['mimic']]
 def effective_enabled(self):return {name:(self.controller.axes_enabled[self.mapping[name]] if self.mapping[name]>=0 else enabled) for name,enabled in self.enabled.items()}
 def reset_joints(self,default=False):
  self.preview={j['name']:max(j['lower'],min(j['upper'],0)) for j in self.independent()}
  self.enabled={j['name']:True for j in self.independent()};self.mapping={j['name']:i if default and i<6 else -1 for i,j in enumerate(self.independent())}
  self.calibration={j['name']:dict(sign=1,offset=0) for j in self.independent()};self.selected=self.independent()[0]['name']
 def idle_edit(self):
  c=self.controller
  if c.busy or c.playing or c.firmware_busy or self.program_running or self.movej.running or self.movej.executing:raise ValueError('Attendi che movimento e anteprima siano fermi prima di modificare i dati.')
 def idle_configuration(self):
  self.idle_edit();c=self.controller
  if c.connected:raise ValueError('Scollega il controllo prima di cambiare modello, mapping o calibrazione.')
 def save(self):
  tmp=self.folder/'project.tmp';tmp.write_text(json.dumps(self.data(),ensure_ascii=False,indent=2));tmp.replace(self.folder/'project.json')
 def data(self):
  return dict(schema=2,outputs=dict(self.outputs),workcell=dict(self.workcell),work_frames=copy.deepcopy(self.work_frames),cartesian_targets=copy.deepcopy(self.cartesian_targets),selected_target=self.selected_target,name=self.project_name,model=self.model,urdf=self.raw,preview=self.preview,enabled=self.effective_enabled(),mapping=self.mapping,calibration=self.calibration,tool=self.tool,tip=self.tip,verified=self.verified,obstacles=self.obstacles,blocks=self.blocks,sensors={k:dict(kind=v['kind'],value=None,stamp=0.,source='non collegato') for k,v in self.sensors.items()})
 def load_data(self,data):
  fields=('workcell','model','raw','project_name','preview','enabled','mapping','calibration','tool','tip','verified','obstacles','blocks','sensors','outputs','follow','selected','status','work_frames','cartesian_targets','selected_target')
  previous={key:copy.deepcopy(getattr(self,key)) for key in fields}
  try:self._load_data(data)
  except Exception:
   for key,value in previous.items():setattr(self,key,value)
   raise
 def _load_data(self,data):
  if type(data.get('schema'))!=int or data['schema'] not in (1,2):raise ValueError('Versione progetto non supportata.')
  work_frames,targets=validate_scene(data.get('work_frames') if data['schema']==2 else [],data.get('cartesian_targets') if data['schema']==2 else [])
  selected=data.get('selected_target','') if data['schema']==2 else ''
  if not isinstance(selected,str) or selected and selected not in {t['id'] for t in targets}:raise ValueError('Target selezionato non presente.')
  # Reparse URDF rather than trusting matrices or geometry from an imported JSON.
  checked=parse_urdf(data['urdf'].encode());old=data.get('model',{})
  checked['approximate']=bool(old.get('approximate',False))
  checked['schematic']=bool(old.get('schematic',False))
  if old.get('mesh_variant') in ('eb15','schematic'):checked['mesh_variant']=old['mesh_variant']
  self.attach_reference_collision(checked,data['urdf'].encode())
  old_visuals={link['name']:link.get('visuals',[]) for link in old.get('links',[])}
  for link in checked['links']:
   for index,visual in enumerate(link['visuals']):
    previous=old_visuals.get(link['name'],[])
    if index<len(previous):
     mesh=Path(previous[index].get('mesh',''))
     if mesh.is_file() and mesh.resolve().is_relative_to(self.folder.resolve()):visual['mesh']=str(mesh.resolve())
  # Parsing a portable/saved URDF cannot resolve assets until the validated
  # project mesh paths above are restored. Keep genuine missing-asset warnings.
  visuals=[v for link in checked['links'] for v in link['visuals'] if v['kind']=='mesh']
  missing={v.get('source_mesh','') for v in visuals if not v['mesh']}
  recovered={v.get('source_mesh','') for v in visuals if v['mesh']}-missing
  recovered_warnings={'Mesh non disponibile: '+name+'; visualizzazione con segnaposto.' for name in recovered}
  checked['warnings']=[warning for warning in checked['warnings'] if warning not in recovered_warnings]
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
  self.blocks=self.bind_pose_references(self.validate_blocks(data.get('blocks',[])));self.outputs=self.io.definitions(data.get('outputs',{}));self.sensors={}
  for name,definition in data.get('sensors',{}).items():self.define_sensor(name,definition.get('kind','digital'))
  self.work_frames,self.cartesian_targets,self.selected_target=work_frames,targets,selected
  self.workcell=self.validate_workcell(data.get('workcell',dict(floor=True,margin=.01)))
  self.follow=False;self.status='Progetto caricato; verifica mapping, HOME e calibrazione prima dell’uso fisico.'
 def save_scene(self,work_frames,targets,selected):
  self.idle_edit()
  checked_frames,checked_targets=validate_scene(work_frames,targets)
  if selected and selected not in {t['id'] for t in checked_targets}:selected=''
  old=(self.work_frames,self.cartesian_targets,self.selected_target,self.status)
  self.work_frames,self.cartesian_targets,self.selected_target=checked_frames,checked_targets,selected
  self.status='Scena salvata: riferimenti e target geometrici, nessun comando al robot.'
  try:self.save()
  except Exception:
   self.work_frames,self.cartesian_targets,self.selected_target,self.status=old
   raise
 def edit_scene(self,request):
  self.idle_edit();op=request['op']
  work_frames=copy.deepcopy(self.work_frames);targets=copy.deepcopy(self.cartesian_targets)
  selected=self.selected_target
  if op in ('studio_frame_save','studio_target_save'):
   entries=work_frames if op=='studio_frame_save' else targets
   key=request.get('id','')
   if key and not any(e['id']==key for e in entries):raise ValueError('Elemento della scena non presente: ricarica i campi.')
   key=key or uuid.uuid4().hex
   entry=dict(id=key,name=request.get('name'),xyz=request.get('xyz'),rpy=request.get('rpy'))
   if op=='studio_frame_save':entry['parent']='base'
   else:entry['frame_id']=request.get('frame_id');selected=key
   entries[:]=[entry if e['id']==key else e for e in entries] if any(e['id']==key for e in entries) else [*entries,entry]
  elif op=='studio_frame_delete':
   key=request.get('id')
   if not any(e['id']==key for e in work_frames):raise ValueError('Riferimento di lavoro non presente o base immutabile.')
   if any(t['frame_id']==key for t in targets):raise ValueError('Il riferimento contiene target: riassegnali o eliminali prima.')
   work_frames=[e for e in work_frames if e['id']!=key]
  elif op=='studio_target_delete':
   key=request.get('id')
   if not any(t['id']==key for t in targets):raise ValueError('Target non presente.')
   targets=[t for t in targets if t['id']!=key]
  else:raise ValueError('Operazione scena non valida.')
  self.save_scene(work_frames,targets,selected)
 def current_positions(self,state=None):
  state=state or self.controller.state();result=self.preview.copy();result['__gripper']=1. if state.get('grip')=='apri' else 0.
  if self.movej.visual_active:
   result['__gripper']=1. if self.movej.grip=='apri' else 0.
  elif self.follow:
   values=state.get('preview_pos',state['pos'])
   for name,axis in self.mapping.items():
    if axis>=0:result[name]=math.radians(values[axis]) if next(j for j in self.independent() if j['name']==name)['kind']!='prismatic' else values[axis]/1000
  return result
 @staticmethod
 def validate_workcell(value):
  if not isinstance(value,dict) or type(value.get('floor',True))!=bool:raise ValueError('Ambiente di lavoro non valido.')
  return dict(floor=value.get('floor',True),margin=number(value.get('margin',.01),0,.1))
 def geometry(self):
  # Capsules depend only on the model and its mesh files; rebuild when either changes.
  key=(self.model['source_hash'],tuple(v.get('mesh','') for l in self.model['links'] for v in l['visuals']))
  if not self._geometry or self._geometry[0]!=key:self._geometry=(key,Geometry(self.model))
  return self._geometry[1]
 def collision_details(self,positions):
  return self.geometry().check(positions,self.calibration,self.obstacles,self.workcell['floor'],self.workcell['margin'])
 def collision_report(self,positions):
  return [hit['a']+' / '+hit['b'] for hit in self.collision_details(positions)]
 def preflight(self,source,*,repeat=False,return_home=True,index=None,motion=None):
  """Whole-route check before Play or Run program; blocks when the model is trusted."""
  warnings_only=source in ('sequence','home','pose') and not self.controller.operator_collision_checks
  report=validate(self,source,repeat=repeat,return_home=return_home,index=index,collision_warnings=warnings_only,motion=motion);self.validation=report
  if warnings_only:
   for note in report['notes']:
    if note.startswith('Interferenza modello'):self.controller.log('SOLO AVVISI · '+note)
  if report['ok']:return
  first=report['issues'][0];c=self.controller
  message='Validazione: %d problemi; il primo %s — %s.'%(len(report['issues']),first['where'],first['detail'])
  if c.mode=='demo' or self.verified or source in ('sequence','home','pose'):raise ValueError(message+' Apri «Valida» nel pannello Programma per i dettagli.')
  c.log(message+' Modello non dichiarato conforme al robot: esecuzione non bloccata.')
 def state(self):
  with self.lock:
   self.movej.tick()
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
   work_frames,cartesian_targets=scene_state(self.work_frames,self.cartesian_targets)
   return dict(io=self.io.state(),workcell=self.workcell,validation=self.validation,cartesian=self.cartesian.state(positions),movej_preview=self.movej.state(),work_frames=work_frames,cartesian_targets=cartesian_targets,selected_target=self.selected_target,name=self.project_name,model=self.model,positions=positions,enabled=self.effective_enabled(),mapping=self.mapping,calibration=self.calibration,tool=self.tool,tip=self.tip,verified=self.verified,selected=self.selected,follow=self.follow,status=self.status,
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
  self.work_frames=[];self.cartesian_targets=[];self.selected_target=''
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
   if c.mode=='demo' or c.multi_axis:
    # Shared MoveJ: the same simultaneous plan, interference sampling and executor as poses/programs.
    if c.mode=='robot' and not self.verified:raise ValueError('Conferma prima la corrispondenza fisica di modello, mapping e calibrazione.')
    self.movej.prepare(dict(source='studio'));self.movej.execute(dict(id=self.movej.plan['id'],confirmed=True));return
   # Legacy firmware without MULTI_AXIS_V1: one joint at a time, as before.
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
  self.sensors[name].update(value=value,stamp=time.time(),source=source,simulated=source in ('simulato','non collegato'))
  self.sensors[name].pop('adapter_id',None)
 def bind_pose_references(self,blocks):
  self.controller.ensure_pose_ids()
  for b in blocks:
   if b['kind']=='pose' or b['kind']=='movej' and b.get('to')=='pose':
    if not b.get('pose_id'):
     index=b.get('index',-1)
     if 0<=index<len(self.controller.sequence):b['pose_id']=self.controller.sequence[index]['id']
  return blocks
 def pose_index(self,block):
  if block.get('pose_id'):
   index=next((i for i,p in enumerate(self.controller.sequence) if p.get('id')==block['pose_id']),None)
   if index is None:raise ValueError('Posa eliminata: scegli esplicitamente un’altra posa per questa istruzione.')
   return index
  index=block.get('index',-1)
  if type(index)!=int or not 0<=index<len(self.controller.sequence):raise ValueError('Posa non presente.')
  return index
 @staticmethod
 def validate_blocks(blocks):
  if not isinstance(blocks,list) or len(blocks)>200:raise ValueError('Massimo 200 blocchi.')
  result=[]
  for raw in blocks:
   b=copy.deepcopy(raw);kind=b.get('kind')
   if kind not in ('pose','grip','wait','sensor','repeat','note','movej','movel','loop','if','else','end','set','output','function','call','return'):raise ValueError('Tipo di blocco non supportato.')
   b['name']=str(b.get('name',kind))[:80];b['enabled']=b.get('enabled',True) is True
   if b.get('pose_id') is not None and (not isinstance(b['pose_id'],str) or not 1<=len(b['pose_id'])<=64):raise ValueError('Riferimento stabile della posa non valido.')
   if kind=='pose':
    b['index']=int(number(b.get('index',0),0,10000))
   if kind=='grip' and b.get('command') not in ('apri','chiudi'):raise ValueError('Comando pinza non valido.')
   if kind=='wait':b['seconds']=number(b.get('seconds',1),0,600)
   if kind=='output':
    b['output']=str(b.get('output',''))[:60];b['output_value']=digital(b.get('output_value',True));b['timeout']=number(b.get('timeout',10),.1,600)
   if kind=='sensor':b['sensor']=str(b.get('sensor',''))[:60];b['expected']=number(b.get('expected',1));b['timeout']=number(b.get('timeout',10),.1,600)
   if kind=='repeat':b['start']=int(number(b.get('start',0),0,199));b['count']=int(number(b.get('count',2),1,100))
   if kind in ('movej','movel'):Studio.validate_motion_block(b)
   if kind=='loop':
    b['times']=str(b.get('times',b.get('count',2)));program_lang.parse(b['times'])
    if b.get('variable'):program_lang.check_name(b['variable'],'Nome della variabile del ciclo')
    else:b.pop('variable',None)
   if kind=='if':b['condition']=str(b.get('condition',''));program_lang.parse(b['condition'])
   if kind=='set':program_lang.check_name(b.get('variable'),'Nome della variabile');b['value']=str(b.get('value','0'));program_lang.parse(b['value'])
   if kind in ('function','call','return'):program_functions.validate_block(b)
   if kind in ('else','end'):b['enabled']=True  # structure markers follow their Ripeti/Se
   result.append(b)
  # Ripeti N volte / Se ... Fine: balanced, bounded nesting. The older back-jump Ripeti stays for simple programs.
  program_functions.definitions(result,program_lang.structure(result))
  if any(b['kind']=='repeat' for b in result) and any(b['kind'] in ('loop','if','function','call','return') for b in result):raise ValueError('Con «Ripeti N volte» e «Se» usa la struttura … Fine al posto del vecchio blocco Ripeti.')
  # Loops are bounded and cannot contain other loop blocks.
  for i,b in enumerate(result):
   if b['kind']=='repeat' and (b['start']>=i or any(x['kind']=='repeat' for x in result[b['start']:i])):raise ValueError('Ripeti deve riferirsi a blocchi precedenti senza cicli annidati.')
  return result
 @staticmethod
 def validate_motion_block(b):
  # Offline-program motion: destination, per-instruction speed (% of the joint speeds) and, for MoveL, the line options.
  b['speed']=round(number(b.get('speed',100),10,100))
  places=('home','joints','pose','target') if b['kind']=='movej' else ('target','point')
  if b.get('to') not in places:raise ValueError('Destinazione '+('MoveJ' if b['kind']=='movej' else 'MoveL')+' non valida.')
  if b['to']=='joints':b['angles']=coordinates(b.get('angles'))
  if b['to']=='pose':b['index']=int(number(b.get('index',0),0,10000))
  if b['to']=='target':
   if not isinstance(b.get('target'),str) or not b['target']:raise ValueError('Scegli il target dell’istruzione.')
   offset=b.get('offset',[0,0,0])
   if not isinstance(offset,list) or len(offset)!=3:raise ValueError('Scostamento dal target non valido.')
   b['offset']=[number(v,-500,500) for v in offset]
   expressions=b.get('offset_expr')
   if expressions is not None:
    if not isinstance(expressions,list) or len(expressions)!=3 or any(not isinstance(e,str) for e in expressions):raise ValueError('Scostamento con variabili non valido.')
    for e in expressions:
     if e.strip():program_lang.parse(e)
    b['offset_expr']=[e.strip() for e in expressions]
    if not any(b['offset_expr']):b.pop('offset_expr')
  if b['to']=='point':
   if not isinstance(b.get('frame'),str) or b['frame']=='tool':raise ValueError('MoveL: scegli la base o un riferimento di lavoro.')
   xyz=b.get('xyz')
   if not isinstance(xyz,list) or len(xyz)!=3:raise ValueError('MoveL richiede X, Y e Z in millimetri.')
   b['xyz']=[number(v,-2000,2000) for v in xyz]
  if b['kind']=='movej':
   b['orientation']=b.get('orientation','axis')
   if b['orientation'] not in ('axis','position'):raise ValueError('Orientamento MoveJ non valido.')
  else:
   b['orientation']=b.get('orientation','keep');b['tolerance']=number(b.get('tolerance',.5),.05,5)
   if b['orientation'] not in ('keep','free'):raise ValueError('Orientamento MoveL non valido.')
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
   if c.busy or c.playing or self.program_running:raise ValueError('Avvia da fermo con riferimento valido.')
   if is_motion_program(self.blocks):raise ValueError('Programma con MoveJ/MoveL: pianificalo e usa «Esegui programma…» sul piano mostrato.')
   steps=[(i,dict(b,index=self.pose_index(b))) if b['kind']=='pose' else (i,b) for i,b in self.expanded_program()]
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
     c.validate_pose(pose)
    if b['kind']=='sensor' and b['sensor'] not in self.sensors:raise ValueError('Sensore del blocco non definito.')
   if any(b['kind'] in ('pose','grip') for _,b in steps):self.preflight('program',return_home=False)
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
       pose=sequence[b['index']];c.follow_position(pose['pos'],g)
       if pose.get('grip') in ('apri','chiudi'):c.servo(pose['grip'],g)
       wait(pose.get('dwell',0))
      elif b['kind']=='grip':c.servo(b['command'],g)
      elif b['kind']=='wait':wait(b['seconds'])
      elif b['kind']=='sensor':
       deadline=time.monotonic()+b['timeout']
       while True:
        check()
        try:matched=self.movej.read_sensor(b['sensor'])==b['expected']
        except ValueError:matched=False
        if matched:break
        if time.monotonic()>deadline:raise ValueError('Timeout sensore: '+b['sensor'])
        time.sleep(.03)
      elif b['kind']=='note':c.log(b['name'])
     c.cycle+=1;c.log('Programma completato; ultima posa mantenuta, riferimento valido.')
    except Exception as error:self.program_error=str(error);raise
    finally:self.program_running=False;self.program_index=-1
   c.playing=True;c.spawn(run)
 def preview_sequence(self,index,fraction):
  poses=[p for p in self.controller.sequence if p.get('enabled',True)]
  if not poses:raise ValueError('Nessuna posa abilitata da visualizzare.')
  if not 0<=index<len(poses):raise ValueError('Posa non valida.')
  fraction=number(fraction,0,1)
  previous=self.controller.pos[:] if index==0 else poses[index-1]['pos'];following=poses[index]['pos']
  previous=list(previous)+[0.]*(6-len(previous));following=list(following)+[0.]*(6-len(following))
  values=[a+(b-a)*fraction for a,b in zip(previous,following)]
  self.follow=False
  for j in self.independent():
   axis=self.mapping[j['name']]
   if axis>=0 and self.effective_enabled()[j['name']]:self.preview[j['name']]=math.radians(values[axis])
  self.status='Anteprima della transizione diretta fra le pose attive; nessun passaggio storico nascosto.'
 def export_recording(self,path):
  output=io.StringIO();writer=csv.writer(output);writer.writerow(['time','mode','j1_deg','j2_deg','j3_deg','j4_deg','j5_deg','j6_deg','busy','gripper'])
  for s in self.samples:writer.writerow([s['time'],s['mode'],*s['commanded'],s['busy'],s['grip']])
  Path(path).write_text(output.getvalue());self.status='Registrazione CSV esportata.'
 def export_project(self,path):
  data=copy.deepcopy(self.data());data['urdf']=self.visualization_urdf(relative=True)
  data['sequence']=copy.deepcopy(self.controller.sequence);data['sequence_motion']=copy.deepcopy(self.controller.require_sequence_motion());data['firmware_identity']=getattr(self.controller,'expected_profile','')
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
   from server import sequence_motion_settings
   motion=sequence_motion_settings(data.get('sequence_motion'))
   self.load_data(data)
   for name,enabled in self.enabled.items():
    if not enabled and self.mapping[name]>=0:self.controller.action(dict(op='joint_enable',axis=self.mapping[name],enabled=False))
   if 'sequence' in data:
    c=self.controller
    previous=(c.sequence_undo,c.sequence,c.sequence_motion)
    c.sequence_undo=copy.deepcopy(c.sequence);c.sequence=sequence;c.sequence_motion=motion
    try:c.save()
    except OSError:
     c.sequence_undo,c.sequence,c.sequence_motion=previous
     raise
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
    entry=dict(axis=axis,delta=delta)
    if 'group' in step:entry['group']=step['group']
    path.append(entry)
   from server import path_units
   path_units(path)
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
 def home_calibration(self,offsets,model_hash):
  if model_hash!=self.model['source_hash']:raise ValueError('Modello cambiato: riapri la regolazione HOME.')
  names={j['name'] for j in self.independent()}
  if not isinstance(offsets,dict) or set(offsets)!=names:raise ValueError('Specifica la HOME di ogni giunto del modello.')
  calibration=copy.deepcopy(self.calibration)
  for joint in self.independent():
   value=number(offsets[joint['name']],joint['lower'],joint['upper'])
   calibration[joint['name']]['offset']=value
  return calibration
 def preview_home(self,offsets,model_hash):
  with self.lock:
   calibration=self.home_calibration(offsets,model_hash);zero={j['name']:0. for j in self.independent()}
   transforms=frames(self.model,zero,calibration)
   return dict(frames=[dict(name=name,matrix=[v for row in matrix for v in row]) for name,matrix in transforms.items()],tcp=tcp(self.model,zero,calibration,self.tip,self.tool),model_hash=self.model['source_hash'])
 def apply_home(self,offsets,model_hash):
  self.idle_edit();calibration=self.home_calibration(offsets,model_hash)
  old=dict(calibration=copy.deepcopy(self.calibration),preview=self.preview.copy(),verified=self.verified,follow=self.follow,status=self.status)
  saved=self.folder/'project.json'
  if saved.exists():
   history=self.folder/'home-revisions';history.mkdir(exist_ok=True)
   shutil.copyfile(saved,history/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json'))
  try:
   self.calibration=calibration;self.preview={j['name']:0. for j in self.independent()};self.verified=False;self.follow=all(abs(q)<.000001 for q in self.controller.pos)
   self.status='HOME del modello salvata a vista; non è una calibrazione misurata. Verifica nuovamente il mapping prima dei target reali.'
   self.save()
  except Exception:
   for key,value in old.items():setattr(self,key,value)
   raise
  self.controller.log('HOME del modello aggiornata: nessun comando ai motori e nessuno zero hardware modificato.')
 def action(self,request):
  op=request['op'];c=self.controller
  with self.lock:
   if op in ('studio_preview','studio_ik','studio_ik_target','studio_ik_choose','studio_jog','studio_follow','studio_sequence','studio_home_apply','studio_import','studio_default','studio_open'):
    self.movej.clear()
   if op=='studio_sequence_motion':
    self.idle_edit()
    from server import sequence_motion_settings
    motion=sequence_motion_settings(request.get('motion'))
    previous=c.sequence_motion
    c.sequence_motion=motion
    try:c.save()
    except OSError:
     c.sequence_motion=previous
     raise
    self.movej.clear()
   elif op=='studio_operator_collisions':
    self.idle_edit();enabled=request.get('enabled')
    if type(enabled)!=bool:raise ValueError('Scelta controllo modello non valida.')
    if not enabled and request.get('confirmed') is not True:raise ValueError('Conferma esplicita richiesta per usare solo avvisi del modello.')
    c.operator_collision_checks=enabled;c.pending_voice=None;self.movej.clear()
    c.log('Interferenze modello in Operatore: '+('bloccanti.' if enabled else 'SOLO AVVISI per sequenze, pose e HOME. Limiti, velocità e STOP restano attivi.'))
   elif op=='studio_movej_plan':self.movej.prepare(request)
   elif op=='studio_movej_play':self.movej.play(request.get('id'))
   elif op=='studio_movej_seek':self.movej.seek(request.get('id'),request.get('elapsed'))
   elif op=='studio_movej_stop':self.movej.stop()
   elif op=='studio_movej_execute':self.movej.execute(request)
   elif op=='studio_movej_clear':self.movej.clear()
   elif op=='studio_home_apply':
    if request.get('confirmed') is not True:raise ValueError('Conferma esplicita richiesta.')
    self.apply_home(request.get('offsets'),request.get('model_hash'))
   elif op in ('studio_frame_save','studio_frame_delete','studio_target_save','studio_target_delete'):self.edit_scene(request)
   elif op=='studio_target_select':
    key=request.get('id','')
    if not isinstance(key,str) or key and not any(t['id']==key for t in self.cartesian_targets):raise ValueError('Target non presente.')
    self.selected_target=key
   elif op=='studio_import':self.import_urdf(request['path'])
   elif op=='studio_import_eb15':self.import_eb15(request.get('paths'))
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
     self.idle_edit();axis=request.get('axis',self.mapping[name])
     if type(axis)!=int or not -1<=axis<6:raise ValueError('Canale hardware non valido.')
     if axis>=0 and any(v==axis and key!=name for key,v in self.mapping.items()):raise ValueError('Canale già associato a un altro giunto.')
     sign=number(request.get('sign',self.calibration[name]['sign']),-1,1)
     if sign not in (-1,1):raise ValueError('Segno ammesso: −1 o +1.')
     self.calibration[name]=dict(sign=sign,offset=number(request.get('offset',self.calibration[name]['offset']),-20,20));self.mapping[name]=axis;self.verified=False
    self.save()
   elif op=='studio_tcp':
    self.idle_edit();tip=request['tip'];tool=[number(v,-2,2) for v in request['tool']]
    if tip not in {l['name'] for l in self.model['links']} or len(tool)!=3:raise ValueError('TCP non valido.')
    self.tip=tip;self.tool=tool;self.verified=False;self.save()
   elif op=='studio_verified':
    self.idle_edit();self.verified=request.get('confirmed') is True;self.status='Corrispondenza fisica dichiarata dall’operatore; la console non la misura.';self.save()
   elif op=='studio_ik':self.cartesian.point(request)
   elif op=='studio_ik_target':self.cartesian.target(request)
   elif op=='studio_ik_choose':self.cartesian.choose(request.get('index'))
   elif op=='studio_jog':self.cartesian.jog(request)
   elif op=='studio_execute':
    if request.get('confirmed') is not True:raise ValueError('Conferma esplicita richiesta.')
    self.execute_preview()
   elif op=='studio_obstacles':self.idle_edit();self.obstacles=self.validate_obstacles(request['boxes']);self.save()
   elif op=='studio_workcell':
    self.idle_edit();self.workcell=self.validate_workcell(dict(floor=request.get('floor',self.workcell['floor']),margin=number(request.get('margin',self.workcell['margin']*1000),0,100)/1000));self.save()
    self.status='Ambiente aggiornato: piano di lavoro %s, margine %.0f mm.'%('attivo' if self.workcell['floor'] else 'escluso',self.workcell['margin']*1000)
   elif op=='studio_validate':
    report=validate(self,request.get('source','program'),return_home=request.get('return_home',False));self.validation=report
    self.status=('Validazione superata: %d pose, %d campioni, nessun problema.'%(report['poses'],report['samples']) if report['ok'] else 'Validazione: %d problemi lungo i percorsi.'%len(report['issues']))
   elif op=='studio_blocks':
    if c.busy or c.playing or self.program_running:raise ValueError('Attendi prima di modificare il programma.')
    self.blocks=self.bind_pose_references(self.validate_blocks(request['blocks']));self.save()
   elif op=='studio_run':
    if request.get('confirmed') is not True:raise ValueError('Conferma esplicita richiesta.')
    self.run_program()
   elif op=='studio_program_plan':self.movej.prepare(dict(source='program',scenario=request.get('scenario') or {},offline=True))
   elif op=='studio_program_execute':
    plan=self.movej.plan
    if not plan or plan.get('program') is None or plan.get('id')!=request.get('id'):raise ValueError('Piano del programma scaduto: ripianifica dopo le modifiche.')
    self.movej.execute(dict(id=request.get('id'),confirmed=request.get('confirmed'),step=request.get('step') is True))
   elif op=='studio_program_step':self.movej.release()
   elif op=='studio_program_continue':self.movej.release(continuous=True)
   elif op=='studio_cancel':self.cancel.set();c.action(dict(op='stop'))
   elif op=='studio_record':
    enabled=request.get('enabled') is True
    if enabled and not self.recording:self.samples=[]
    self.recording=enabled
   elif op=='studio_export_csv':self.export_recording(request['path'])
   elif op=='studio_export':self.idle_edit();self.export_project(request['path'])
   elif op=='studio_open':self.import_project(request['path'])
   elif op=='studio_output_add':
    if c.busy or c.playing or self.movej.executing:raise ValueError('Attendi prima di definire un’uscita.')
    self.io.define(request['name']);self.save()
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
