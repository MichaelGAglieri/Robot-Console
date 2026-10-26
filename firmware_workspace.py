# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Editable firmware workspace and validated parameters for the current Mega.
Saving never flashes a board. All historical revisions remain local.
"""
import copy, hashlib, json, math, re, shutil, time
from pathlib import Path

DEFAULT=dict(schema=1,name='DOC · Mega 2560 / RAMPS 1.4',board='mega2560',axes=[dict(driver='DM542' if i==1 else 'A4988',steps=200,microstep=8,reduction=38.4,invert=False) for i in range(5)]+[dict(driver='DM542',steps=200,microstep=8,reduction=38.4,invert=False,active=False,step_pin=-1,dir_pin=-1,enable_pin=-1)])

def validate(profile):
 if not isinstance(profile,dict) or profile.get('schema')!=1 or profile.get('board')!='mega2560':raise ValueError('Questo backend firmware supporta Mega 2560 / RAMPS 1.4.')
 axes=copy.deepcopy(profile.get('axes'))
 if isinstance(axes,list) and len(axes)==5:axes.append(copy.deepcopy(DEFAULT['axes'][5]))
 if not isinstance(axes,list) or len(axes)!=6:raise ValueError('Il backend richiede cinque canali RAMPS e J6 esterno opzionale.')
 result=dict(schema=1,name=str(profile.get('name','Profilo robot'))[:80],board='mega2560',axes=[])
 for i,a in enumerate(axes):
  if not isinstance(a,dict):raise ValueError('Parametri asse non validi.')
  driver=a.get('driver');steps=a.get('steps');micro=a.get('microstep');ratio=a.get('reduction');invert=a.get('invert')
  expected=('DM542',) if i==1 else (('DM542','A4988','DRV8825') if i==5 else ('A4988','DRV8825'))
  options=(1,2,4,8,16) if driver=='A4988' else ((1,2,4,8,16,32) if driver=='DRV8825' else (1,2,4,5,8,10,16,20,25,32,40,50,64,100,128))
  if driver not in expected:raise ValueError('J%d: driver incompatibile con il cablaggio del backend corrente.'%(i+1))
  if type(steps)!=int or not 1<=steps<=10000 or type(micro)!=int or micro not in options or steps*micro>65535:raise ValueError('J%d: passi motore o microstepping non validi.'%(i+1))
  if type(ratio) not in (int,float) or not math.isfinite(ratio) or not .01<=ratio<=1000 or not 1<=steps*micro*ratio<=1_440_000:raise ValueError('J%d: riduzione fuori dal budget del generatore di impulsi.'%(i+1))
  if type(invert)!=bool:raise ValueError('Inversione non valida.')
  axis=dict(driver=driver,steps=steps,microstep=micro,reduction=float(ratio),invert=invert)
  if i==5:
   active=a.get('active',False);pins=[a.get(k,-1) for k in ('step_pin','dir_pin','enable_pin')]
   allowed={-1,40,42,44,57,58,59,63,64,65,66}
   if type(active)!=bool or any(type(pin)!=int or pin not in allowed for pin in pins):raise ValueError('J6: scegli pin liberi consentiti per il driver esterno.')
   if active and (pins[0]<0 or pins[1]<0 or pins[0]==pins[1] or (pins[2]>=0 and pins[2] in pins[:2])):raise ValueError('J6 richiede STEP e DIR distinti; ENA può restare non gestito.')
   if driver=='DM542' and pins[2]!=-1:raise ValueError('Per DM542 ENA resta non gestito, come sul banco J2.')
   axis.update(active=active,step_pin=pins[0],dir_pin=pins[1],enable_pin=pins[2])
  result['axes'].append(axis)
 return result

def identity(profile):
 p=validate(profile);p.pop('name');
 if not p['axes'][5]['active']:p['axes']=p['axes'][:5]
 return hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:16]

def speed_limit(profile):
 pulses=max(a['steps']*a['microstep']*a['reduction'] for i,a in enumerate(validate(profile)['axes']) if i<5 or a['active'])
 return max(1.,min(20.,math.floor(4000*360/pulses*2)/2))

class FirmwareWorkspace:
 def __init__(self,folder,controller,source=None):
  self.folder=Path(folder)/'firmware_workspace';self.folder.mkdir(parents=True,exist_ok=True)
  self.path=self.folder/'RegiaDemo';self.controller=controller;self.profile=copy.deepcopy(DEFAULT);self.error='';self.status='Firmware del banco pronto; nessun caricamento automatico.'
  source=Path(source or Path(__file__).parent/'RegiaDemo')
  if not self.path.exists():shutil.copytree(source,self.path)
  try:
   if (self.folder/'profile.json').exists():self.profile=validate(json.loads((self.folder/'profile.json').read_text()))
  except (OSError,ValueError,KeyError,TypeError) as e:self.error='Profilo firmware illeggibile: '+str(e)
  if not self.error:self.error=self.source_error()
  self.install_profile()
 def source_error(self):
  try:code=(self.path/'RegiaDemo.ino').read_text()
  except OSError:return 'Sorgente principale assente: ripristina il firmware originale.'
  legacy='const byte AXES = 5;' in code;axes=self.profile['axes'][:5] if legacy else self.profile['axes']
  extra=self.profile['axes'][5]
  if extra['active']:
   for name,value in dict(J6_CONFIGURED='true',J6_STEP_PIN=str(extra['step_pin']),J6_DIR_PIN=str(extra['dir_pin']),J6_ENABLE_PIN=str(extra['enable_pin'] if extra['enable_pin']>=0 else 255)).items():
    if not re.search(r'\b'+name+r'\s*=\s*'+value+r'\s*;',code):return 'Pin J6 del sorgente diversi dal profilo: genera nuovamente il firmware.'
  for name,expected in [('PULSES_PER_MOTOR_REV',[a['steps']*a['microstep'] for a in axes]),('REDUCTION',[a['reduction'] for a in axes]),('INVERT_DIRECTION',[int(a['invert']) for a in axes])]:
   match=re.search(r'\b'+name+r'\[AXES\]\s*=\s*\{([^}]+)\}',code)
   try:actual=[float(v.strip().rstrip('f').replace('false','0').replace('true','1')) for v in match[1].split(',')] if match else []
   except ValueError:actual=[]
   if len(actual)!=len(expected) or any(abs(a-b)>1e-4 for a,b in zip(actual,expected)):return 'Costanti del sorgente diverse dal profilo: allinea i parametri e genera il firmware prima del controllo reale.'
  return ''
 def install_profile(self):
  c=self.controller;c.expected_profile=identity(self.profile);c.profile_default=identity(self.profile)==identity(DEFAULT);c.profile_speed_limit=speed_limit(self.profile);c.profile_error=self.error;c.configured_axes=6 if self.profile['axes'][5]['active'] else 5
 def gate(self):
  c=self.controller
  if c.connected or c.busy or c.playing or c.firmware_busy:raise ValueError('Scollega il controllo e attendi la fine delle operazioni firmware.')
 def files(self):return sorted(p.name for p in self.path.iterdir() if p.is_file() and p.suffix in ('.ino','.h','.cpp'))
 def file(self,name):
  if name not in self.files() or Path(name).name!=name:raise ValueError('File firmware non valido.')
  p=self.path/name
  if p.stat().st_size>250000:raise ValueError('File firmware troppo grande.')
  return p
 def state(self):
  c=self.controller
  return dict(axis_control_source='FEATURES AXIS_ENABLE' in self.file('RegiaDemo.ino').read_text(),profile=self.profile,identity=identity(self.profile),default=DEFAULT,max_speed=speed_limit(self.profile),files=self.files(),folder=str(self.path),status=self.status,error=self.error,received_identity=getattr(c,'firmware_profile',''),matches=c.hardware_ok())
 def backup(self):
  name=time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns()%1_000_000)
  dest=self.folder/'revisions'/name;dest.parent.mkdir(exist_ok=True);shutil.copytree(self.path,dest)
  if (self.folder/'profile.json').exists():shutil.copyfile(self.folder/'profile.json',dest/'profile.json')
 def save_file(self,name,content):
  self.gate();p=self.file(name)
  if not isinstance(content,str) or len(content.encode())>250000 or '\x00' in content:raise ValueError('Sorgente firmware non valido.')
  self.backup();tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(content);tmp.replace(p)
  self.error=self.source_error();self.install_profile()
  self.status='File salvato. Verifica la compilazione prima di caricarlo; il codice libero può cambiare il comportamento del robot.'
 def generate(self,profile):
  self.gate();p=validate(profile);source=self.path/'RegiaDemo.ino';code=source.read_text();self.backup()
  replacements={
   r'const uint16_t PULSES_PER_MOTOR_REV\[AXES\] = \{[^}]+\};':'const uint16_t PULSES_PER_MOTOR_REV[AXES] = {'+', '.join(str(a['steps']*a['microstep']) for a in p['axes'])+'};',
   r'const float REDUCTION\[AXES\] = \{[^}]+\};':'const float REDUCTION[AXES] = {'+', '.join(str(a['reduction'])+'f' for a in p['axes'])+'};',
   r'const bool INVERT_DIRECTION\[AXES\] = \{[^}]+\};':'const bool INVERT_DIRECTION[AXES] = {'+', '.join('true' if a['invert'] else 'false' for a in p['axes'])+'};',
  }
  for pattern,replacement in replacements.items():
   code,count=re.subn(pattern,lambda _:replacement,code)
   if count!=1:raise ValueError('Il codice è stato modificato e il generatore non trova la configurazione prevista. Ripristina il sorgente del banco o modifica i parametri manualmente.')
  if 'const byte AXES = 5;' in code:raise ValueError('Workspace precedente a J6: esporta le modifiche e ripristina il firmware originale prima di generare sei assi.')
  extra=p['axes'][5]
  for key,value in dict(J6_CONFIGURED='true' if extra['active'] else 'false',J6_DM542='true' if extra['driver']=='DM542' else 'false',J6_STEP_PIN=max(-1,extra['step_pin']) if extra['step_pin']>=0 else 255,J6_DIR_PIN=extra['dir_pin'] if extra['dir_pin']>=0 else 255,J6_ENABLE_PIN=extra['enable_pin'] if extra['enable_pin']>=0 else 255).items():
   code,count=re.subn(r'(const (?:bool|byte) '+key+r' = )[^;]+;',lambda m:m[1]+str(value)+';',code)
   if count!=1:raise ValueError('Configurazione J6 assente: ripristina il sorgente originale aggiornato.')
  # Generated ID is announced without changing the existing Regia 4 protocol.
  code=re.sub(r'\s*Serial\.println\(F\("CONFIG [a-f0-9]+"\)\);','',code)
  announce='Serial.println(F("DOC REGIA 4"));'
  if announce not in code:raise ValueError('Identificazione firmware non presente; impossibile generare un profilo compatibile.')
  code=re.sub(r'float MAX_OUTPUT_SPEED = [0-9.]+f;', 'float MAX_OUTPUT_SPEED = '+str(min(5.,speed_limit(p)))+'f;',code)
  code=code.replace(announce,announce+' Serial.println(F("CONFIG '+identity(p)+'"));')
  code=re.sub(r'value>\d+\) \{\n      Serial.println\(F\("ERROR SPEED 1\.\.\d+"\)\);return;',lambda _: 'value>'+str(int(speed_limit(p)*100))+') {\n      Serial.println(F("ERROR SPEED 1..'+str(speed_limit(p))+'"));return;',code)
  (self.path/'RegiaDemo.ino').write_text(code);self.profile=p;tmp=self.folder/'profile.tmp';tmp.write_text(json.dumps(p,indent=2));tmp.replace(self.folder/'profile.json');self.error='';self.install_profile()
  self.controller.home=False;self.controller.identified=False;self.controller.speed_confirmed=False
  self.status='Parametri generati e salvati. Jumper e DIP devono corrispondere. Compila e carica con conferma; poi ristabilisci HOME.'
 def upgrade_axis_control(self):
  self.gate();self.backup()
  # Preserve electrical/mechanical profile; only replace the main sketch explicitly.
  (self.path/'RegiaDemo.ino').write_text((Path(__file__).parent/'RegiaDemo'/'RegiaDemo.ino').read_text())
  self.generate(self.profile)
  self.status='Comandi giunti aggiornati; parametri e revisioni conservati. Nessun caricamento sulla Mega.'
 def restore(self):
  self.gate();self.backup()
  for p in (Path(__file__).parent/'RegiaDemo').iterdir():
   if p.is_file():shutil.copyfile(p,self.path/p.name)
  self.profile=copy.deepcopy(DEFAULT);(self.folder/'profile.json').write_text(json.dumps(self.profile));self.error='';self.install_profile();self.status='Sorgenti originali ripristinati nel workspace, nessuna scrittura sulla Mega.'
 def export(self,path):
  import zipfile
  with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
   for name in self.files():archive.write(self.path/name,'RegiaDemo/'+name)
   archive.writestr('profile.json',json.dumps(self.profile,indent=2))
