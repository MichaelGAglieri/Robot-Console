#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Local-only DOC presentation controller. No third-party Python dependencies."""
import hashlib, uuid, json, math, os, select, termios, threading, time, glob, secrets, fcntl, struct
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get("DOC_REGIA_DATA", str(ROOT)))
DATA.mkdir(parents=True,exist_ok=True)
from voice_commands import parse_command, confirmation
from serial_transport import ensure_port_available, claim_exclusive
USB_BOOT_QUIET=3.0
HELLO_RETRY=4.0
AXES=6
TOKEN=secrets.token_urlsafe(24)
def path_units(path):
 """Legacy edges stay sequential; explicit contiguous groups are atomic."""
 units=[];seen=set()
 for edge in path:
  group=edge.get('group')
  if group is not None:
   if not isinstance(group,str) or not 1<=len(group)<=64:raise ValueError('Gruppo movimento non valido.')
   if units and units[-1][0].get('group')==group:
    if any(x['axis']==edge['axis'] for x in units[-1]):raise ValueError('Asse ripetuto nel gruppo.')
    units[-1].append(edge);continue
   if group in seen:raise ValueError('Gruppo movimento non contiguo.')
   seen.add(group)
  units.append([edge])
 return units

def motion_duration(distance,speed,a=20.0):
 distance=abs(distance)
 return 2*math.sqrt(distance/a) if distance<speed*speed/a else distance/speed+speed/a

def motion_fraction(distance,speed,elapsed,a=20.0):
 distance=abs(distance)
 if not distance:return 1.
 peak=min(speed,math.sqrt(distance*a));ramp=peak/a;duration=motion_duration(distance,speed,a)
 if elapsed<=0:return 0.
 if elapsed>=duration:return 1.
 if elapsed<ramp:return .5*a*elapsed*elapsed/distance
 if elapsed>duration-ramp:return 1-.5*a*(duration-elapsed)**2/distance
 return (peak*(elapsed-ramp)+.5*a*ramp*ramp)/distance

class Controller:
 def __init__(self):
  self.journal=None; self.firmware_busy=False; self.lock=threading.RLock(); self.fd=None; self.mode='demo'; self.connected=False
  self.home=False; self.pos=[0.0]*AXES; self.limits=[[0.0,0.0] for _ in range(AXES)]
  self.trail=[]; self.sequence=[]; self.events=[];self.robot_events=[];self.event_counter=0; self.busy=False; self.playing=False
  self.repeat_cycle=False; self.paused=False; self.generation=0; self.done=threading.Event(); self.browser=time.monotonic()
  self.speed=5.0; self.requested_speed=5.0; self.speed_confirmed=False; self.speed_sent=0.0; self.firmware=''; self.connected_at=0.0; self.last_hello=0.0
  self.sequence_undo=None; self.max_speed=20.0; self.sequence_revision=0; self.awaiting_halt=False; self.boot_ready_at=0.0; self.serial_lines=0; self.last_serial=''; self.error=''; self.grip='non comandata'; self.cycle=0; self.identified=False; self.rx=b''
  self.axes_enabled=[True]*AXES;self.motion=None;self.firmware_profile="";self.profile_error="";self.profile_speed_limit=20.;self.reported_axes=5;self.configured_axes=5
  self.pending_voice=None;self.multi_axis=False;self.multi_ack=False;self.pulses_per_rev=[61440]*AXES
  self.axis_speeds=[5.0]*AXES;self.multi_axis=False;self.axis_control=False;self.drive_caps=[False]*AXES;self.drive_state=[None]*AXES;self.pending_off={};self.preparing_axis=None
  try:
   values=json.loads((DATA/'axis_speeds.json').read_text())
   if len(values)==AXES and all(type(v) in (int,float) and math.isfinite(v) and 1<=v<=20 for v in values):self.axis_speeds=values
  except (OSError,ValueError,TypeError):pass
  try:
   if (DATA/'axes_enabled.json').exists():
    mask=json.loads((DATA/'axes_enabled.json').read_text())
    if not isinstance(mask,list) or len(mask) not in (5,AXES) or any(type(v)!=bool for v in mask):raise ValueError('Maschera giunti non valida')
    self.axes_enabled=mask+[True]*(AXES-len(mask))
  except (OSError,ValueError):self.axes_enabled=[False]*AXES;self.error='Abilitazione giunti illeggibile: movimenti bloccati.'
  if (DATA/'sequenza.json').exists():
   try:
    self.sequence=json.loads((DATA/'sequenza.json').read_text())['sequence']
    for pose in self.sequence:
     if isinstance(pose.get('pos'),list) and len(pose['pos'])==5:pose['pos'].append(0.)
   except (ValueError,KeyError):self.error='Sequenza salvata non leggibile'
  threading.Thread(target=self.io,daemon=True).start()
 def log(self,s):
  self.event_counter+=1
  self.robot_events=(self.robot_events+[dict(id=self.event_counter,time=time.time(),mode=self.mode,text=s)])[-300:]
  self.events=(self.events+[s])[-30:]
  if self.journal:
   try:self.journal.add('event',self.mode,s)
   except Exception:pass # Storage errors must never prevent STOP.
 def write(self,s):
  if self.fd is not None: os.write(self.fd,s.encode())
 def halt(self,reason,send=True):
  with self.lock:
   try:
    if send:
     self.awaiting_halt=self.fd is not None
     self.write('!')
   except OSError:pass
   self.generation+=1; self.home=False; self.playing=False; self.paused=False; self.busy=False;self.motion=None;self.preparing_axis=None
   self.error=reason; self.done.set(); self.log(reason)
 def receive(self,s):
  with self.lock:
   self.serial_lines+=1; self.last_serial=s[:180]
   if self.serial_lines<=8:self.log('USB RX: '+s[:180])
   if s.startswith('DOC REGIA '):
    self.firmware=s
    if s not in ('DOC REGIA 2','DOC REGIA 4'):
     self.identified=False;self.speed_confirmed=False
     self.error='Firmware non compatibile: usa la sezione Firmware per caricare il firmware incluso.';return
    if self.identified and (self.home or self.busy):self.halt('Reset della Mega: home da ristabilire.')
    self.max_speed=min(20.0 if s=='DOC REGIA 4' else 10.0,self.profile_speed_limit)
    self.identified=True
    self.multi_axis=False;self.axis_control=False;self.drive_caps=[False]*AXES;self.drive_state=[None]*AXES
    # A startup identity may mean the board reset to its default speed/ENABLEs.
    # Require fresh acknowledgements instead of retaining stale hardware state.
    self.speed_confirmed=False;self.speed_sent=0.0
    if not self.error.startswith('Reset della Mega'):self.error=''
    self.log('Firmware riconosciuto; verifica velocità in corso.')
   elif s.startswith('Formato: j1 ') or s.startswith('TEST 5 STEPPER'):
    if not self.identified:self.error='Firmware di test rilevato: serve Regia dall’app. Apri Firmware, seleziona la Mega attuale e carica il firmware incluso.'
   elif s.startswith('CAPS '):
    try:self.reported_axes=max(5,min(AXES,int(s[5:])))
    except ValueError:pass
   elif s=='FEATURES AXIS_ENABLE':self.axis_control=True
   elif s=='FEATURES MULTI_AXIS_V1':self.multi_axis=True
   elif s=='MULTI ACK':
    if self.motion and 'axes' in self.motion:self.multi_ack=True
   elif s.startswith('DRIVE_CAPS '):
    bits=s[11:]
    if len(bits)==AXES and set(bits)<=set('01'):self.drive_caps=[v=='1' for v in bits]
   elif s.startswith('DRIVES '):
    bits=s[7:]
    if len(bits)==AXES and set(bits)<=set('01?'):self.drive_state=[None if v=='?' else v=='1' for v in bits]
   elif s.startswith('AXIS_OFF '):
    try:axis=int(s[9:])-1
    except ValueError:return
    if axis in self.pending_off:
     del self.pending_off[axis]
     if self.drive_caps[axis] and self.drive_state[axis] is not False:
      self.halt('ENABLE non confermato disattivato: stato del driver incerto.');return
     self.log('J%d: %s'%(axis+1,'ENABLE disattivato; corrente alle bobine esclusa dal driver.' if self.drive_caps[axis] else 'movimenti esclusi; ENA non collegato, coppia ancora possibile.'))
   elif s.startswith('CONFIG '):
    self.firmware_profile=s[7:].strip()
    if not self.hardware_ok():self.error='Profilo firmware diverso dal profilo attivo: movimenti bloccati.'
   elif s.startswith('SPEED '):
    try:value=float(s[6:])
    except ValueError:return
    if self.identified and math.isfinite(value) and 1<=value<=self.max_speed and abs(value-self.requested_speed)<.005:
     self.speed=value;self.speed_confirmed=True;self.error=''
     self.log('Velocità confermata: %.2f gradi/s'%value)
   elif ' DONE:' in s:
    if self.motion and 'axes' in self.motion:
     if self.multi_ack and s.startswith('MULTI DONE:'):self.done.set()
    elif not s.startswith('MULTI '):self.done.set()
   elif s=='HALTED':
    if self.awaiting_halt:self.awaiting_halt=False;self.log('STOP confermato dalla Mega.')
    else:self.halt('Mega arrestata: verifica e ristabilisci HOME.',False)
   elif s.startswith('ERROR'):self.halt('Firmware: '+s,False)
 def io(self):
  last=0
  while True:
   time.sleep(.02)
   with self.lock:
    now=time.monotonic()
    if self.connected and now-self.browser>2:
     self.halt('Interfaccia assente: STOP. Ristabilisci la home.');self.connected=False
    if self.fd is None:continue
    try:
     # Silence lets the Mega bootloader time out. Do not feed it heartbeat bytes.
     ready=self.connected and now>=self.boot_ready_at
     if ready and self.identified and now-last>.25:self.write('~');last=now
     if ready and self.identified and not self.speed_confirmed and not self.speed_sent:
      self.write('~speed %.2f\n'%self.requested_speed);self.speed_sent=now
     if self.connected and not self.identified:
      # USB can reset the Mega; repeat the non-motion handshake after its bootloader.
      if ready and now-self.last_hello>=HELLO_RETRY:self.write('hello\n');self.last_hello=now
      if now-self.connected_at>USB_BOOT_QUIET+6 and not self.identified and not self.error.startswith('Firmware di test rilevato'):
       self.error=('Mega senza risposta USB: verifica il cavo, premi RESET sulla Mega e attendi. Non serve ricaricare se il caricamento è già riuscito.' if not self.serial_lines else 'Dati USB ricevuti, ma identificazione non valida. Ultima riga: '+self.last_serial)
     if self.identified and not self.speed_confirmed and self.speed_sent and now-self.speed_sent>3:
      self.error='Velocità non confermata dalla Mega: comandi di movimento bloccati.'
     if any(now-deadline>3 for deadline in self.pending_off.values()):
      for axis in self.pending_off:self.drive_state[axis]=None
      self.pending_off.clear();self.halt('Disabilitazione non confermata: corrente del driver non verificata.');continue
     if select.select([self.fd],[],[],0)[0]:
      data=os.read(self.fd,4096)
      if not data:raise OSError('USB scollegata')
      self.rx+=data
      while b'\n' in self.rx:
       line,self.rx=self.rx.split(b'\n',1);self.receive(line.decode(errors='replace').strip())
    except OSError as e:
     self.halt(str(e));self.connected=False;os.close(self.fd);self.fd=None
 def guide(self):
  if not self.connected:return '1 · Avvia Anteprima senza hardware oppure scegli Robot USB e connetti la porta.'
  if not self.identified and self.connected and time.monotonic()<self.boot_ready_at:return '1 · Avvio Mega: attendo 3 secondi senza trasmettere sulla USB.'
  if not self.identified:return '1 · Porta USB aperta. Attendi il riconoscimento; consulta il messaggio diagnostico sotto. Il LED verde indica alimentazione USB.'
  if not self.speed_confirmed:return '1 · Attendi la conferma della velocità: finché manca, i movimenti sono bloccati.'
  if not self.hardware_ok():return '1 · Firmware e profilo non corrispondono: verifica i parametri e il sorgente, poi genera e carica il firmware corretto.'
  if not self.home:return '2 · Conferma HOME: scegli la posizione iniziale del braccio. In Anteprima confermi solo uno zero virtuale.'
  if all(lo==hi for lo,hi in self.limits):return '3 · Imposta e applica i limiti. Ora sono tutti 0/0: ogni giunto è bloccato. Per esempio, in Anteprima prova J1 da -5 a +5.'
  return '4 · Muovi con +/−, osserva il risultato e premi Registra posa. Per riprodurre torna prima a HOME.'
 def state(self):
  with self.lock:
   preview=self.pos[:]
   if self.motion:
    m=self.motion;f=max(0,min(1,(time.time()-m['started'])/max(.01,m['duration'])))
    if 'axes' in m:
     for i in m['axes']:
      progress=motion_fraction(1,m['path_speed'],time.time()-m['started'],m['path_acceleration'])
      preview[i]=m['starts'][i]+(m['targets'][i]-m['starts'][i])*progress
    else:preview[m['axis']]=m['start']+(m['target']-m['start'])*f
   return dict(robot_events=self.robot_events[:],multi_axis=self.mode=='demo' or self.multi_axis,active_axes=self.motion.get('axes',[self.motion.get('axis')]) if self.motion else [],axis_speeds=[min(v,self.max_speed) for v in self.axis_speeds],axis_control=self.mode=='demo' or self.axis_control,drive_caps=[True]*AXES if self.mode=='demo' else self.drive_caps,drive_state=self.drive_state,pending_off=list(self.pending_off),active_axis=self.motion.get('axis') if self.motion else self.preparing_axis,axes_available=[self.mode=='demo' or i<min(self.reported_axes,self.configured_axes) for i in range(AXES)],hardware_ok=self.hardware_ok(),firmware_profile=self.firmware_profile,mode=self.mode,connected=self.connected,home=self.home,pos=self.pos[:],preview_pos=preview,motion=self.motion,axes_enabled=self.axes_enabled[:],limits=self.limits,trail=len(self.trail),sequence=self.sequence,sequence_revision=self.sequence_revision,can_undo=self.sequence_undo is not None,max_speed=self.max_speed,events=self.events,busy=self.busy,playing=self.playing,paused=self.paused,error=self.error,grip=self.grip,identified=self.identified,firmware=self.firmware,speed=self.speed,speed_confirmed=self.speed_confirmed,guidance=self.guide(),cycle=self.cycle,ports=glob.glob('/dev/cu.usbmodem*')+glob.glob('/dev/cu.usbserial*'))
 def hardware_ok(self):
  if self.profile_error:return False
  expected=getattr(self,'expected_profile','')
  if not expected:return True
  if self.firmware_profile:return self.firmware_profile==expected
  return getattr(self,'profile_default',True)
 def check(self):
  if not self.connected:raise ValueError('Connetti prima la modalità scelta.')
  if not self.identified or not self.speed_confirmed:raise ValueError('Firmware o velocità non confermati: completa la connessione.')
  if not self.hardware_ok():raise ValueError('Firmware e profilo hardware non corrispondono. Genera, compila e carica il profilo scelto.')
  if not self.home:raise ValueError('Metti fisicamente il braccio nella home e confermala.')
 def validate(self,a,d):
  if not isinstance(a,int) or not 0<=a<AXES:raise ValueError('Asse non valido')
  if not isinstance(d,(int,float)) or not math.isfinite(d) or abs(d)>360:raise ValueError('Angolo non valido')
  if self.mode=='robot' and a>=min(self.reported_axes,self.configured_axes):raise ValueError('J6 richiede firmware configurato e driver esterno: nessun impulso inviato.')
  if not self.axes_enabled[a] and abs(d)>.001:raise ValueError('J%d disabilitato: riabilitalo prima di comandare questo movimento.'%(a+1))
  target=round(self.pos[a]+d,2)
  if not self.limits[a][0]<=target<=self.limits[a][1]:raise ValueError('Il movimento supera i limiti impostati di J'+str(a+1))
  return target
 def move(self,a,d,gen,record=True):
  with self.lock:
   self.check()
   if gen!=self.generation:raise ValueError('Interrotto')
   target=self.validate(a,d); self.busy=True; self.done.clear()
   if abs(d)<.001:return
   speed=min(self.axis_speeds[a],self.max_speed)
   self.preparing_axis=a
   if self.mode=='robot' and abs(self.speed-speed)>.005:
    self.requested_speed=speed;self.speed_confirmed=False;self.speed_sent=time.monotonic();self.write('~speed %.2f\n'%speed)
  # Do not hold the serial-reader lock while waiting for the speed acknowledgement.
  deadline=time.monotonic()+3
  while self.mode=='robot' and not self.speed_confirmed:
   if gen!=self.generation:raise ValueError('Interrotto')
   if time.monotonic()>deadline:raise ValueError('Velocità del giunto non confermata: nessun movimento inviato.')
   time.sleep(.01)
  with self.lock:
   self.check()
   if gen!=self.generation:raise ValueError('Interrotto')
   self.validate(a,d);self.preparing_axis=None
   self.motion=dict(axis=a,start=self.pos[a],target=target,started=time.time(),duration=abs(d)/speed+.5)
   self.write('j%d %.2f\n'%(a+1,d))
  duration=abs(d)/speed+.5
  if self.mode=='demo':
   end=time.monotonic()+duration
   while time.monotonic()<end:
    if gen!=self.generation:raise ValueError('Interrotto')
    time.sleep(.03)
  elif not self.done.wait(duration*2+4):
   self.halt('Timeout: posizione incerta, home da ristabilire.');raise ValueError('Timeout')
  with self.lock:
   if gen!=self.generation:raise ValueError('Interrotto')
   self.pos[a]=target;self.motion=None
   self.log('J%d %+.2f° → %.2f° · %s'%(a+1,d,target,'anteprima' if self.mode=='demo' else 'DONE firmware, posizione non misurata'))
   if record:self.trail.append(dict(axis=a,delta=d))
   if len(self.trail)>4000:self.halt('Percorso troppo lungo: salva e ristabilisci home.');raise ValueError('Limite percorso')
 def servo(self,command,gen):
  with self.lock:
   if gen!=self.generation:raise ValueError('Interrotto')
   self.check();self.write(command+'\n');self.grip=command;self.busy=True
  for _ in range(30):
   if gen!=self.generation:raise ValueError('Interrotto')
   time.sleep(.05)
 def group_plan(self,deltas):
  if not isinstance(deltas,list) or len(deltas)!=AXES or any(type(d) not in (int,float) or not math.isfinite(d) or abs(d)>360 for d in deltas):raise ValueError('Inserisci sei spostamenti relativi da -360 a 360 gradi.')
  deltas=[round(d,2) for d in deltas];targets=self.pos[:];axes=[]
  for i,d in enumerate(deltas):
   if not d:continue
   targets[i]=self.validate(i,d);axes.append(i)
   if abs(d)*self.pulses_per_rev[i]/360<.5:raise ValueError('Spostamento inferiore a un impulso: aumenta l’angolo.')
  if not axes:raise ValueError('Inserisci almeno uno spostamento diverso da zero.')
  if self.mode=='robot' and not self.multi_axis:raise ValueError('Movimento simultaneo: aggiorna e carica il firmware con MULTI_AXIS_V1.')
  speeds=[min(v,self.max_speed) for v in self.axis_speeds]
  total=sum(math.floor(abs(deltas[i])*self.pulses_per_rev[i]/360+.5) for i in axes)
  path_speed=min(min(speeds[i]/abs(deltas[i]) for i in axes),2000./total)
  path_acceleration=min(20./abs(deltas[i]) for i in axes)
  effective=[abs(d)*path_speed for d in deltas]
  duration=motion_duration(1,path_speed,path_acceleration)
  return deltas,targets,axes,speeds,effective,duration,path_speed,path_acceleration
 def group_context(self):
  return hashlib.sha256((self.voice_context()+json.dumps([self.max_speed,self.profile_speed_limit,self.pulses_per_rev,self.configured_axes,self.reported_axes])).encode()).hexdigest()
 def preview_group(self,deltas):
  with self.lock:
   try:
    if self.busy or self.playing:raise ValueError('Attendi il termine del movimento.')
    d,targets,axes,speeds,effective,duration,path_speed,path_acceleration=self.group_plan(deltas)
    peak=min(path_speed,math.sqrt(path_acceleration))
    pulse_total=sum(math.floor(abs(d[i])*self.pulses_per_rev[i]/360+.5) for i in axes)
    budget_limited=2000./pulse_total < min(speeds[i]/abs(d[i]) for i in axes)-1e-9
    return dict(valid=True,error='',deltas=d,targets=targets,axes=axes,requested=speeds,effective=effective,peaks=[abs(v)*peak for v in d],duration=duration,budget_limited=budget_limited,context=self.group_context())
   except (ValueError,TypeError) as error:
    return dict(valid=False,error=str(error),deltas=[],targets=[],axes=[],requested=[min(v,self.max_speed) for v in self.axis_speeds],effective=[0.]*AXES,peaks=[0.]*AXES,duration=0.,budget_limited=False,context='')
 def move_group(self,deltas,gen,record=True):
  with self.lock:
   self.check()
   if gen!=self.generation:raise ValueError('Interrotto')
   deltas,targets,axes,speeds,effective,duration,path_speed,path_acceleration=self.group_plan(deltas)
   self.busy=True;self.done.clear();self.multi_ack=False
   self.motion=dict(path_speed=path_speed,path_acceleration=path_acceleration,axes=axes,starts=self.pos[:],targets=targets,speeds=effective,started=time.time(),duration=duration)
   # One fully validated line, no per-axis start commands or streamed queue.
   self.write('~multi '+' '.join('%.2f %.2f'%(d,v) for d,v in zip(deltas,speeds))+'\n')
   self.log('Movimento simultaneo: '+', '.join('J%d %.2f°/s'%(i+1,effective[i]) for i in axes)+' · velocità limitate dal budget impulsi totale.')
  deadline=time.monotonic()+(duration if self.mode=='demo' else duration*2+4)
  while True:
   if gen!=self.generation:raise ValueError('Interrotto')
   if self.mode!='demo' and self.done.wait(.02):break
   if time.monotonic()>=deadline:
    if self.mode=='demo':break
    self.halt('Timeout movimento simultaneo: ristabilisci HOME.');raise ValueError('Timeout')
   if self.mode=='demo':time.sleep(.02)
  with self.lock:
   if gen!=self.generation:raise ValueError('Interrotto')
   self.pos=targets;self.motion=None
   if record:
    group=uuid.uuid4().hex
    self.trail.extend(dict(axis=i,delta=deltas[i],group=group) for i in axes)
   if len(self.trail)>4000:self.halt('Percorso troppo lungo.');raise ValueError('Limite percorso')
   self.log('Gruppo completato · '+('anteprima' if self.mode=='demo' else 'DONE firmware, posizione non misurata'))
 def run_unit(self,unit,gen,reverse=False,record=True):
  if unit[0].get('group') is not None:
   deltas=[0.]*AXES
   for step in unit:deltas[step['axis']]=step['delta']*(-1 if reverse else 1)
   self.move_group(deltas,gen,record)
  else:
   step=unit[0];self.move(step['axis'],step['delta']*(-1 if reverse else 1),gen,record)
 def wait_ready(self,gen):
  while self.paused:
   if gen!=self.generation:raise ValueError('Interrotto')
   time.sleep(.05)
  if gen!=self.generation:raise ValueError('Interrotto')
 def back(self,gen):
  self.validate_path(self.trail)
  for unit in reversed(path_units(self.trail)):
   self.wait_ready(gen);self.run_unit(unit,gen,True,False)
   with self.lock:del self.trail[-len(unit):]
  self.log('Home raggiunta secondo il conteggio impulsi. Pinza mantenuta.')
 def follow_path(self,path,gen):
  self.validate_path(self.trail);self.validate_path(path)
  previous=path_units(self.trail);following=path_units(path);common=0
  while common<min(len(previous),len(following)) and previous[common]==following[common]:common+=1
  for unit in reversed(previous[common:]):
   self.wait_ready(gen);self.run_unit(unit,gen,True,False)
   with self.lock:del self.trail[-len(unit):]
  for unit in following[common:]:
   self.wait_ready(gen);self.run_unit(unit,gen,False,False)
   with self.lock:self.trail.extend(x.copy() for x in unit)
  self.wait_ready(gen)
 def validate_path(self,path):
  path_units(path)
  if self.mode=='robot' and not self.multi_axis and any('group' in x for x in path):raise ValueError('Il percorso richiede il firmware MULTI_AXIS_V1.')
  for step in path:
   if type(step.get('axis'))!=int or not 0<=step['axis']<AXES:raise ValueError('Asse del percorso non valido.')
   delta=step.get('delta')
   if type(delta) not in (int,float) or not math.isfinite(delta) or abs(delta)>360:raise ValueError('Spostamento del percorso non valido.')
   if self.mode=='robot' and step['axis']>=min(self.reported_axes,self.configured_axes) and abs(delta)>.001:raise ValueError('Il percorso richiede J6, non configurato sul robot reale.')
   if abs(delta)>.001 and not self.axes_enabled[step['axis']]:raise ValueError('Il percorso richiede J%d, attualmente disabilitato.'%(step['axis']+1))
 def spawn(self,fn):
  gen=self.generation;self.busy=True
  def run():
   try:fn(gen)
   except Exception as e:
    with self.lock:
     if gen==self.generation:self.halt(str(e))
   finally:
    with self.lock:
     if gen==self.generation:self.busy=False;self.playing=False
  threading.Thread(target=run,daemon=True).start()
 def edit_pose(self,pose,b):
  name=b.get('name');dwell=b.get('dwell');pos=b.get('pos');pos=pos+[0.] if isinstance(pos,list) and len(pos)==5 else pos;grip=b.get('grip');enabled=b.get('enabled')
  if not isinstance(name,str) or not name.strip() or len(name)>60:raise ValueError('Nome posa: da 1 a 60 caratteri.')
  if type(dwell) not in (int,float) or not math.isfinite(dwell) or not 0<=dwell<=60:raise ValueError('Pausa da 0 a 60 secondi.')
  if not isinstance(pos,list) or len(pos)!=AXES or any(type(v) not in (int,float) or not math.isfinite(v) or not -360<=v<=360 for v in pos):raise ValueError('Inserisci sei angoli assoluti da −360° a +360°.')
  if grip not in ('apri','chiudi','non comandata') or type(enabled)!=bool:raise ValueError('Stato pinza o abilitazione non validi.')
  result=json.loads(json.dumps(pose));target=[round(v,2) for v in pos];result['pos']=target
  if target!=pose['pos']+[0.]*(AXES-len(pose['pos'])):
   # Keep the taught route as an anchor. Repeated edits replace only its extension.
   base=pose.get('edit_base_path',pose['path']);p=[0.0]*AXES
   for step in base:p[step['axis']]+=step['delta']
   path=json.loads(json.dumps(base))
   for axis,value in enumerate(target):
    delta=round(value-p[axis],2)
    while abs(delta)>.001:
     part=max(-360.0,min(360.0,delta));path.append(dict(axis=axis,delta=part));delta=round(delta-part,2)
   if len(path)>4000:raise ValueError('Percorso troppo lungo: registra una nuova posa.')
   result.update(pos=target,path=path,edit_base_path=base,angles_edited=path!=base)
  result.update(name=name.strip(),dwell=dwell,grip=grip,enabled=enabled)
  return result
 def validate_pose(self,pose):
  self.validate_path(pose['path'])
  if not pose.get('enabled',True):raise ValueError('Posa disabilitata.')
  if pose.get('mode')!=self.mode:raise ValueError('Posa appartenente a una modalità diversa.')
  p=[0.]*AXES
  for step in pose['path']:
   p[step['axis']]+=step['delta']
   if not self.limits[step['axis']][0]<=p[step['axis']]<=self.limits[step['axis']][1]:raise ValueError('Posa fuori dai limiti attuali.')
  if len(pose['pos'])!=AXES or any(abs(a-b)>.02 for a,b in zip(p,pose['pos'])):raise ValueError('Posa e percorso non coerenti.')
  if pose.get('grip','non comandata') not in ('apri','chiudi','non comandata'):raise ValueError('Pinza non valida.')
  if type(pose.get('dwell')) not in (int,float) or not math.isfinite(pose['dwell']) or not 0<=pose['dwell']<=60:raise ValueError('Pausa posa non valida.')
 def voice_context(self):
  return json.dumps([self.generation,self.mode,self.home,self.pos,self.trail,self.limits,self.axes_enabled,self.axis_speeds,self.sequence_revision,self.firmware_profile,self.firmware,self.multi_axis,self.hardware_ok()],sort_keys=True)
 def prepare_voice(self,text,language="it"):
  with self.lock:
   self.pending_voice=None;self.check()
   if self.busy or self.playing:raise ValueError('Attendi il termine o usa STOP.')
   command=parse_command(text)
   english=language=='en'
   if command['op']=='joint_targets':
    deltas=[0.]*AXES;phrases=[]
    for target in command['targets']:
     i=target['axis'];delta=round(target['value'] if target['relative'] else target['value']-self.pos[i],2)
     position=self.validate(i,delta);deltas[i]=delta
     phrases.append(('J%d to %.2f degrees, change %+.2f' if english else 'J%d a %.2f gradi, spostamento %+.2f')%(i+1,position,delta))
    active=[i for i,d in enumerate(deltas) if d]
    if not active:raise ValueError('Nessuno spostamento richiesto.')
    if len(active)>1:
     plan=self.preview_group(deltas)
     if not plan['valid']:raise ValueError(plan['error'])
     detail=', '.join(('J%d peak %.2f degrees per second' if english else 'J%d picco previsto %.2f gradi al secondo')%(i+1,plan['peaks'][i]) for i in active)
     phrases.append(detail)
     command=dict(op='multi_jog',deltas=deltas)
    else:command=dict(op='jog',axis=active[0],delta=deltas[active[0]])
    summary=('Move ' if english else 'Muovo ')+('; '.join(phrases))+'?'
   else:
    if not 0<=command['index']<len(self.sequence):raise ValueError('Posa non presente.')
    self.validate_pose(self.sequence[command['index']]);self.validate_path(self.trail)
    summary=('Run pose %d, %s, including its taught path and gripper action?' if english else 'Avvio posa %d, %s, incluso il percorso registrato e il comando pinza?')%(command['index']+1,self.sequence[command['index']]['name'])
   token=secrets.token_urlsafe(24)
   self.pending_voice=dict(token=token,command=command,context=self.voice_context(),expires=time.monotonic()+30)
   return dict(token=token,summary=summary,text=text)
 def action(self,b):
  with self.lock:
   op=b['op'];self.browser=time.monotonic()
   if op=='heartbeat':return
   if op=='voice_cancel':self.pending_voice=None;return
   if op=='voice_execute':
    result=confirmation(b.get('confirmation',''))
    if result is False:self.pending_voice=None;return
    if result is not True:raise ValueError('Di’ sì confermo oppure annulla.')
    pending=self.pending_voice;self.pending_voice=None
    if not pending or b.get('token')!=pending['token'] or time.monotonic()>pending['expires'] or self.voice_context()!=pending['context']:raise ValueError('Conferma vocale scaduta o stato cambiato: riconosci nuovamente il comando.')
    return self.action(pending['command'])
   if self.firmware_busy and op not in ('stop','axis_stop'):raise ValueError('Attendi il termine dell’operazione firmware.')
   if op=='axis_stop':
    axis=b.get('axis')
    if type(axis)!=int or not 0<=axis<AXES:raise ValueError('Asse non valido')
    active=self.motion.get('axes',[self.motion.get('axis')]) if self.motion else [self.preparing_axis]
    if axis in active:self.halt('STOP J%d: impulsi interrotti, tenuta mantenuta. Ristabilisci HOME.'%(axis+1))
    else:self.log('STOP J%d: giunto già fermo; nessun altro asse arrestato.'%(axis+1))
    return
   if op=='joint_enable':
    axis=b.get('axis');enabled=b.get('enabled')
    if type(axis)!=int or not 0<=axis<AXES or type(enabled)!=bool:raise ValueError('Abilitazione giunto non valida.')
    if enabled and (self.busy or self.playing):raise ValueError('Riabilita il giunto a movimento fermo.')
    if self.connected and self.mode=='robot':
     if not self.identified or not self.axis_control:raise ValueError('Per gestire ENABLE serve il nuovo firmware: scollega, aggiorna i comandi giunti, compila e carica il profilo. Nessuna corrente disattivata.')
     if enabled and self.pending_off:raise ValueError('Attendi la conferma di disabilitazione del driver.')
    mask=self.axes_enabled[:];mask[axis]=enabled
    tmp=DATA/'axes_enabled.tmp';tmp.write_text(json.dumps(mask));tmp.replace(DATA/'axes_enabled.json');self.axes_enabled=mask
    if self.connected and self.mode=='robot':
     if not enabled:
      moving=self.motion is not None
      self.halt('J%d escluso: sequenza interrotta; ristabilisci HOME.'%(axis+1),False)
      self.awaiting_halt=moving;self.pending_off[axis]=time.monotonic()
      self.write('~off %d\n'%(axis+1))
     else:
      self.home=False;self.write('~mask '+''.join('1' if v else '0' for v in mask)+'\n')
      self.log('J%d incluso: ENABLE verrà attivato alla conferma HOME.'%(axis+1))
    else:
     if not enabled and self.busy:self.halt('Giunto escluso: anteprima interrotta.',False)
     if self.mode=='demo':self.drive_state[axis]=enabled and self.home
     self.log('J%d: %s; %s.'%(axis+1,'incluso' if enabled else 'escluso','anteprima' if self.mode=='demo' else 'maschera salvata, driver non connesso'))
    return
   if op=='set_axis_speed':
    axis=b.get('axis');value=b.get('speed')
    if type(axis)!=int or not 0<=axis<AXES or type(value) not in (int,float) or not math.isfinite(value) or not 1<=value<=self.max_speed:raise ValueError('Velocità giunto non valida.')
    if self.busy or self.playing:raise ValueError('Modifica la velocità a movimento fermo.')
    values=self.axis_speeds[:];values[axis]=round(value,2)
    tmp=DATA/'axis_speeds.tmp';tmp.write_text(json.dumps(values));tmp.replace(DATA/'axis_speeds.json');self.axis_speeds=values
    self.log('J%d: velocità %.2f gradi/s, applicata al prossimo movimento.'%(axis+1,value));return
   if op=='stop':self.halt('STOP operatore: verifica e ristabilisci la home.');return
   if op=='pause':self.paused=not self.paused;return
   if op=='end_cycle':
    if not self.playing:raise ValueError('Nessuna sequenza in riproduzione')
    self.repeat_cycle=False;self.paused=False;self.log('Ultimo ciclo: rientro a HOME al termine.');return
   if op=='disconnect':
    if self.busy or self.playing:raise ValueError('Ferma prima il movimento.')
    if self.connected:self.halt('Controllo scollegato: HOME da ristabilire.')
    if self.fd is not None:os.close(self.fd);self.fd=None
    self.connected=False;self.home=False;self.identified=False;self.speed_confirmed=False
    return
   if op=='connect':
    if b.get('mode')=='robot' and os.environ.get('DOC_REGIA_NO_HARDWARE')=='1':raise ValueError('Questa anteprima isolata non può aprire la USB del robot.')
    if self.busy or self.playing:raise ValueError('Ferma prima il movimento')
    if self.fd is not None:os.close(self.fd);self.fd=None
    self.multi_axis=False;self.axis_control=False;self.drive_caps=[False]*AXES;self.drive_state=[None]*AXES;self.pending_off.clear();self.preparing_axis=None
    self.connected=False;self.home=False;self.trail=[];self.pos=[0.0]*AXES;self.error='';self.limits=[[0.0,0.0] for _ in range(AXES)];self.grip='non comandata'
    self.max_speed=min(20.0 if b.get('mode','demo')=='demo' else 10.0,self.profile_speed_limit);self.awaiting_halt=False;self.serial_lines=0;self.last_serial='';self.mode=b.get('mode','demo');self.reported_axes=5;self.identified=False;self.rx=b'';self.firmware='';self.speed=min(5.0,self.max_speed);self.requested_speed=self.speed;self.firmware_profile='';self.speed_confirmed=False;self.connected_at=time.monotonic();self.boot_ready_at=self.connected_at+USB_BOOT_QUIET;self.last_hello=self.connected_at-HELLO_RETRY
    if self.mode=='robot':
     port=b['port']
     if port not in glob.glob('/dev/cu.usbmodem*')+glob.glob('/dev/cu.usbserial*'):raise ValueError('Porta USB non valida')
     ensure_port_available(port)
     self.fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
     try:
      claim_exclusive(self.fd)
      ensure_port_available(port)
     except Exception:
      os.close(self.fd);self.fd=None;raise
     attr=termios.tcgetattr(self.fd);attr[0]=0;attr[1]=0;attr[2]=termios.CS8|termios.CREAD|termios.CLOCAL;attr[3]=0;attr[4]=attr[5]=termios.B115200;attr[6][termios.VMIN]=0;attr[6][termios.VTIME]=0
     try:
      termios.tcsetattr(self.fd,termios.TCSANOW,attr)
      # Restore modem-control lines after avrdude; no ARM or motion command.
      fcntl.ioctl(self.fd,termios.TIOCMBIS,struct.pack('I',termios.TIOCM_DTR|termios.TIOCM_RTS))
     except OSError:
      os.close(self.fd);self.fd=None;raise
     self.log('USB configurata: 115200 baud · 8N1 · DTR/RTS attivi; attendo identificazione.')
     self.connected=True
     # handshake is asynchronous; home is refused until the version is recognized
     self.log('Attesa avvio Mega: 3 secondi di silenzio USB, poi riconoscimento.')
    else:self.connected=True;self.identified=True;self.firmware='Anteprima';self.speed_confirmed=True;self.firmware_profile=getattr(self,'expected_profile','')
    self.log('Modalità '+self.mode+' connessa');return
   if op=='pose_undo':
    if self.busy or self.playing:raise ValueError('Attendi la fine della sequenza.')
    if b.get('revision')!=self.sequence_revision:raise ValueError('Sequenza aggiornata: ripeti la modifica.')
    if self.sequence_undo is None:raise ValueError('Nessuna modifica da annullare')
    self.sequence=self.sequence_undo;self.sequence_undo=None;self.save();return
   if op in ('pose_delete','pose_move','pose_grip','pose_update','pose_enable'):
    if self.busy or self.playing:raise ValueError('Attendi la fine della sequenza prima di modificarla.')
    if b.get('revision')!=self.sequence_revision:raise ValueError('Sequenza aggiornata: ripeti la modifica.')
    index=b.get('index')
    if type(index)!=int or not 0<=index<len(self.sequence):raise ValueError('Posa non valida')
    previous=json.loads(json.dumps(self.sequence))
    if op=='pose_delete':self.sequence.pop(index)
    elif op=='pose_move':
     target=b.get('target')
     if type(target)!=int or not 0<=target<len(self.sequence):raise ValueError('Posizione non valida')
     self.sequence.insert(target,self.sequence.pop(index))
    elif op=='pose_update':self.sequence[index]=self.edit_pose(self.sequence[index],b)
    elif op=='pose_enable':
     enabled=b.get('enabled')
     if type(enabled)!=bool:raise ValueError('Abilitazione posa non valida')
     self.sequence[index]['enabled']=enabled
    else:
     grip=b.get('grip')
     if grip not in ('apri','chiudi','non comandata'):raise ValueError('Stato pinza non valido')
     self.sequence[index]['grip']=grip
    self.sequence_undo=previous;self.save();return
   self.check_connection()
   if op=='set_speed':
    if self.busy or self.playing:raise ValueError('Modifica la velocità a movimento fermo.')
    value=b.get('speed')
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 1<=value<=self.max_speed:raise ValueError('Velocità da 1 a %.0f gradi/s; per 20 gradi/s carica il firmware incluso.'%self.max_speed)
    if not self.identified:raise ValueError('Prima carica e collega il firmware Regia 2.')
    self.axis_speeds=[round(value,2)]*AXES
    tmp=DATA/'axis_speeds.tmp';tmp.write_text(json.dumps(self.axis_speeds));tmp.replace(DATA/'axis_speeds.json')
    self.requested_speed=round(value,2)
    if self.mode=='demo':self.speed=self.requested_speed;self.speed_confirmed=True
    else:
     self.speed_confirmed=False;self.speed_sent=time.monotonic();self.write('~speed %.2f\n'%self.requested_speed)
    return
   if op=='home_set':
    if self.awaiting_halt:raise ValueError('Attendi la conferma STOP della Mega prima di confermare HOME.')
    if not self.hardware_ok():raise ValueError('Profilo firmware non corrispondente: HOME non abilitata.')
    if self.busy or self.playing:raise ValueError('Movimento in corso')
    if not self.identified:raise ValueError('Firmware Regia non riconosciuto: caricalo dalla sezione Firmware dell’app')
    if not self.speed_confirmed:raise ValueError('Attendi la conferma della velocità dalla Mega.')
    if self.pending_off:raise ValueError('Attendi la conferma di disabilitazione del driver.')
    if self.mode=='robot':
     if self.axis_control:self.write('~mask '+''.join('1' if v else '0' for v in self.axes_enabled)+'\n')
     elif not all(self.axes_enabled[:min(self.reported_axes,self.configured_axes)]):raise ValueError('Aggiorna il firmware per mantenere disabilitati i driver esclusi durante HOME.')
    self.write('~arm\n');self.home=True;self.pos=[0.0]*AXES;self.trail=[];self.error='';self.log('Zero virtuale confermato' if self.mode=='demo' else 'Home fisica confermata dall’operatore');return
   if op=='limits':
    if self.busy or self.playing:raise ValueError('Ferma prima la sequenza')
    v=b['limits'];v=v+[[0.,0.]] if isinstance(v,list) and len(v)==5 else v
    if len(v)!=AXES or any(len(x)!=2 or any(not isinstance(n,(int,float)) or not math.isfinite(n) for n in x) or not -360<=x[0]<=0<=x[1]<=360 or not x[0]<=p<=x[1] for x,p in zip(v,self.pos)):raise ValueError('Limiti non validi: devono contenere zero e la posizione attuale')
    self.limits=v;return
   self.check()
   if self.busy or self.playing:raise ValueError('Attendi il termine o usa STOP')
   if op=='pose_start':
    index=b.get('index')
    if type(index)!=int or not 0<=index<len(self.sequence):raise ValueError('Posa non presente.')
    pose=json.loads(json.dumps(self.sequence[index]));self.validate_pose(pose);self.validate_path(self.trail)
    def run_pose(g):
     self.follow_path(pose['path'],g)
     if pose.get('grip') in ('apri','chiudi'):self.servo(pose['grip'],g)
     end=time.monotonic()+pose['dwell']
     while time.monotonic()<end:
      self.wait_ready(g);time.sleep(.03)
     self.log('Posa raggiunta nel conteggio comandi: '+pose['name'])
    self.spawn(run_pose);return
   if op=='multi_jog':
    if 'context' in b and b['context']!=self.group_context():raise ValueError('Velocità o stato modificati: controlla nuovamente il riepilogo del gruppo.')
    deltas=self.group_plan(b.get('deltas'))[0];self.spawn(lambda g:self.move_group(deltas,g));return
   if op=='jog':
    a=int(b['axis']);d=round(float(b['delta']),2)
    self.validate(a,d);self.spawn(lambda g:self.move(a,d,g));return
   if op=='servo':
    cmd=b['command']
    if cmd not in ('apri','chiudi'):raise ValueError('Comando pinza non valido')
    self.spawn(lambda g:self.servo(cmd,g));return
   if op=='record':
    name=str(b.get('name','Posa'))[:60];dwell=float(b.get('dwell',1))
    if not math.isfinite(dwell) or not 0<=dwell<=60:raise ValueError('Pausa da 0 a 60 s')
    grip=b.get('grip','auto')
    if grip=='auto':grip=self.grip
    if grip not in ('apri','chiudi','non comandata'):raise ValueError('Stato pinza non valido')
    self.sequence_undo=None
    self.sequence.append(dict(name=name,mode=self.mode,pos=self.pos[:],path=[x.copy() for x in self.trail],grip=grip,dwell=dwell,enabled=True))
    self.save();return
   if op=='clear':self.sequence_undo=json.loads(json.dumps(self.sequence));self.sequence=[];self.save();return
   if op=='home':self.validate_path(self.trail);self.spawn(self.back);return
   if op=='play':
    active=[pose for pose in self.sequence if pose.get('enabled',True)]
    if not active:raise ValueError('Abilita almeno una posa per riprodurre la sequenza.')
    if self.trail or any(abs(x)>.01 for x in self.pos):raise ValueError('Torna a home prima della riproduzione')
    # Validate every stored path before starting; reordered transitions reuse its edges.
    for pose in active:
     self.validate_path(pose['path'])
     if pose.get('mode')!=self.mode:raise ValueError('Registra le pose nella modalità corrente: le anteprime non sono percorsi provati sul robot.')
     p=[0.0]*AXES
     for x in pose['path']:
      p[x['axis']]+=x['delta']
      if not self.limits[x['axis']][0]-.001<=p[x['axis']]<=self.limits[x['axis']][1]+.001:raise ValueError('Sequenza fuori dai limiti attuali')
     if any(abs(a-b)>.02 for a,b in zip(p,pose['pos'])):raise ValueError('Posa e percorso non coerenti')
     if pose.get('grip','non comandata') not in ('apri','chiudi','non comandata'):raise ValueError('Stato pinza della posa non valido')
    self.playing=True;self.paused=False;self.repeat_cycle=bool(b.get('repeat',False));sequence=json.loads(json.dumps(active))
    def play(g):
     while True:
      if g!=self.generation:raise ValueError('Interrotto')
      while self.paused:
       if g!=self.generation:raise ValueError('Interrotto')
       time.sleep(.05)
      time.sleep(.1)
      for pose in sequence:
       self.follow_path(pose['path'],g)
       if pose.get('grip') in ('apri','chiudi'):self.servo(pose['grip'],g)
       self.log('Posa: '+pose['name']);end=time.monotonic()+pose['dwell']
       while time.monotonic()<end:
        if g!=self.generation:raise ValueError('Interrotto')
        time.sleep(.05)
      self.back(g);self.cycle+=1;self.log('Ciclo completato: '+str(self.cycle))
      if not self.repeat_cycle:break
    self.spawn(play);return
   raise ValueError('Azione sconosciuta')
 def check_connection(self):
  if not self.connected:raise ValueError('Connetti prima la modalità scelta')
 def save(self):
  self.sequence_revision+=1
  path=DATA/'sequenza.json';tmp=DATA/'sequenza.tmp';tmp.write_text(json.dumps(dict(sequence=self.sequence,limits=self.limits),ensure_ascii=False,indent=2));tmp.replace(path)
c=Controller()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,code,data,kind='application/json'):
  raw=data if isinstance(data,bytes) else json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=='/api/state':self.send(200,c.state())
  elif self.path=='/':self.send(200,(ROOT/'index.html').read_bytes().replace(b'__TOKEN__',TOKEN.encode()),'text/html; charset=utf-8')
  else:self.send(404,{'error':'Not found'})
 def do_POST(self):
  if self.headers.get('X-Token')!=TOKEN:self.send(403,{'error':'Sessione non valida'});return
  try:
   n=int(self.headers.get('Content-Length',0))
   if n>20000:raise ValueError('Richiesta troppo grande')
   c.action(json.loads(self.rfile.read(n)));self.send(200,{'ok':True})
  except Exception as e:self.send(400,{'error':str(e)})
if __name__=='__main__':
 print('DOC Regia: http://127.0.0.1:8768',flush=True)
 ThreadingHTTPServer(('127.0.0.1',8768),Handler).serve_forever()
