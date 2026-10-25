#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Local-only DOC presentation controller. No third-party Python dependencies."""
import json, math, os, select, termios, threading, time, glob, secrets, fcntl, struct
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get("DOC_REGIA_DATA", str(ROOT)))
DATA.mkdir(parents=True,exist_ok=True)
from serial_transport import ensure_port_available, claim_exclusive
USB_BOOT_QUIET=3.0
HELLO_RETRY=4.0
TOKEN=secrets.token_urlsafe(24)
class Controller:
 def __init__(self):
  self.journal=None; self.firmware_busy=False; self.lock=threading.RLock(); self.fd=None; self.mode='demo'; self.connected=False
  self.home=False; self.pos=[0.0]*5; self.limits=[[0.0,0.0] for _ in range(5)]
  self.trail=[]; self.sequence=[]; self.events=[]; self.busy=False; self.playing=False
  self.repeat_cycle=False; self.paused=False; self.generation=0; self.done=threading.Event(); self.browser=time.monotonic()
  self.speed=5.0; self.requested_speed=5.0; self.speed_confirmed=False; self.speed_sent=0.0; self.firmware=''; self.connected_at=0.0; self.last_hello=0.0
  self.sequence_undo=None; self.max_speed=20.0; self.sequence_revision=0; self.awaiting_halt=False; self.boot_ready_at=0.0; self.serial_lines=0; self.last_serial=''; self.error=''; self.grip='non comandata'; self.cycle=0; self.identified=False; self.rx=b''
  if (DATA/'sequenza.json').exists():
   try:self.sequence=json.loads((DATA/'sequenza.json').read_text())['sequence']
   except (ValueError,KeyError):self.error='Sequenza salvata non leggibile'
  threading.Thread(target=self.io,daemon=True).start()
 def log(self,s):
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
   self.generation+=1; self.home=False; self.playing=False; self.paused=False; self.busy=False
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
    self.max_speed=20.0 if s=='DOC REGIA 4' else 10.0
    first=not self.identified;self.identified=True
    if first:
     self.error='';self.speed_confirmed=False;self.speed_sent=0.0
     self.log('Firmware riconosciuto; verifica velocità in corso.')
   elif s.startswith('Formato: j1 ') or s.startswith('TEST 5 STEPPER'):
    if not self.identified:self.error='Firmware di test rilevato: serve Regia dall’app. Apri Firmware, seleziona la Mega attuale e carica il firmware incluso.'
   elif s.startswith('SPEED '):
    try:value=float(s[6:])
    except ValueError:return
    if self.identified and math.isfinite(value) and 1<=value<=self.max_speed and abs(value-self.requested_speed)<.005:
     self.speed=value;self.speed_confirmed=True;self.error=''
     self.log('Velocità confermata: %.2f gradi/s'%value)
   elif ' DONE:' in s:self.done.set()
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
  if not self.home:return '2 · Conferma HOME: scegli la posizione iniziale del braccio. In Anteprima confermi solo uno zero virtuale.'
  if all(lo==hi for lo,hi in self.limits):return '3 · Imposta e applica i limiti. Ora sono tutti 0/0: ogni giunto è bloccato. Per esempio, in Anteprima prova J1 da -5 a +5.'
  return '4 · Muovi con +/−, osserva il risultato e premi Registra posa. Per riprodurre torna prima a HOME.'
 def state(self):
  with self.lock:return dict(mode=self.mode,connected=self.connected,home=self.home,pos=self.pos[:],limits=self.limits,trail=len(self.trail),sequence=self.sequence,sequence_revision=self.sequence_revision,can_undo=self.sequence_undo is not None,max_speed=self.max_speed,events=self.events,busy=self.busy,playing=self.playing,paused=self.paused,error=self.error,grip=self.grip,identified=self.identified,firmware=self.firmware,speed=self.speed,speed_confirmed=self.speed_confirmed,guidance=self.guide(),cycle=self.cycle,ports=glob.glob('/dev/cu.usbmodem*')+glob.glob('/dev/cu.usbserial*'))
 def check(self):
  if not self.connected:raise ValueError('Connetti prima la modalità scelta.')
  if not self.identified or not self.speed_confirmed:raise ValueError('Firmware o velocità non confermati: completa la connessione.')
  if not self.home:raise ValueError('Metti fisicamente il braccio nella home e confermala.')
 def validate(self,a,d):
  if not isinstance(a,int) or not 0<=a<5:raise ValueError('Asse non valido')
  if not isinstance(d,(int,float)) or not math.isfinite(d) or abs(d)>360:raise ValueError('Angolo non valido')
  target=round(self.pos[a]+d,2)
  if not self.limits[a][0]<=target<=self.limits[a][1]:raise ValueError('Il movimento supera i limiti impostati di J'+str(a+1))
  return target
 def move(self,a,d,gen,record=True):
  with self.lock:
   self.check()
   if gen!=self.generation:raise ValueError('Interrotto')
   target=self.validate(a,d); self.busy=True; self.done.clear()
   if abs(d)<.001:return
   self.write('j%d %.2f\n'%(a+1,d))
  duration=abs(d)/self.speed+.5
  if self.mode=='demo':
   end=time.monotonic()+duration
   while time.monotonic()<end:
    if gen!=self.generation:raise ValueError('Interrotto')
    time.sleep(.03)
  elif not self.done.wait(duration*2+4):
   self.halt('Timeout: posizione incerta, home da ristabilire.');raise ValueError('Timeout')
  with self.lock:
   if gen!=self.generation:raise ValueError('Interrotto')
   self.pos[a]=target
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
 def back(self,gen):
  while self.trail:
   while self.paused:
    if gen!=self.generation:raise ValueError('Interrotto')
    time.sleep(.05)
   step=self.trail[-1];self.move(step['axis'],-step['delta'],gen,False)
   with self.lock:self.trail.pop()
  self.log('Home raggiunta secondo il conteggio impulsi. Pinza mantenuta.')
 def follow_path(self,path,gen):
  common=0
  while common<min(len(self.trail),len(path)) and self.trail[common]==path[common]:common+=1
  def wait_ready():
   while self.paused:
    if gen!=self.generation:raise ValueError('Interrotto')
    time.sleep(.05)
   if gen!=self.generation:raise ValueError('Interrotto')
  while len(self.trail)>common:
   wait_ready();step=self.trail[-1]
   self.move(step['axis'],-step['delta'],gen,False)
   with self.lock:self.trail.pop()
  for step in path[common:]:
   wait_ready();self.move(step['axis'],step['delta'],gen)
  wait_ready()
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
  name=b.get('name');dwell=b.get('dwell');pos=b.get('pos');grip=b.get('grip');enabled=b.get('enabled')
  if not isinstance(name,str) or not name.strip() or len(name)>60:raise ValueError('Nome posa: da 1 a 60 caratteri.')
  if type(dwell) not in (int,float) or not math.isfinite(dwell) or not 0<=dwell<=60:raise ValueError('Pausa da 0 a 60 secondi.')
  if not isinstance(pos,list) or len(pos)!=5 or any(type(v) not in (int,float) or not math.isfinite(v) or not -360<=v<=360 for v in pos):raise ValueError('Inserisci cinque angoli assoluti da −360° a +360°.')
  if grip not in ('apri','chiudi','non comandata') or type(enabled)!=bool:raise ValueError('Stato pinza o abilitazione non validi.')
  result=json.loads(json.dumps(pose));target=[round(v,2) for v in pos]
  if target!=pose['pos']:
   # Keep the taught route as an anchor. Repeated edits replace only its extension.
   base=pose.get('edit_base_path',pose['path']);p=[0.0]*5
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
 def action(self,b):
  with self.lock:
   op=b['op'];self.browser=time.monotonic()
   if op=='heartbeat':return
   if self.firmware_busy and op!='stop':raise ValueError('Attendi il termine dell’operazione firmware.')
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
    if self.busy or self.playing:raise ValueError('Ferma prima il movimento')
    if self.fd is not None:os.close(self.fd);self.fd=None
    self.connected=False;self.home=False;self.trail=[];self.pos=[0.0]*5;self.error='';self.limits=[[0.0,0.0] for _ in range(5)];self.grip='non comandata'
    self.max_speed=20.0 if b.get('mode','demo')=='demo' else 10.0;self.awaiting_halt=False;self.serial_lines=0;self.last_serial='';self.mode=b.get('mode','demo');self.identified=False;self.rx=b'';self.firmware='';self.speed=5.0;self.requested_speed=5.0;self.speed_confirmed=False;self.connected_at=time.monotonic();self.boot_ready_at=self.connected_at+USB_BOOT_QUIET;self.last_hello=self.connected_at-HELLO_RETRY
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
    else:self.connected=True;self.identified=True;self.firmware='Anteprima';self.speed_confirmed=True
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
    self.requested_speed=round(value,2)
    if self.mode=='demo':self.speed=self.requested_speed;self.speed_confirmed=True
    else:
     self.speed_confirmed=False;self.speed_sent=time.monotonic();self.write('~speed %.2f\n'%self.requested_speed)
    return
   if op=='home_set':
    if self.busy or self.playing:raise ValueError('Movimento in corso')
    if not self.identified:raise ValueError('Firmware Regia non riconosciuto: caricalo dalla sezione Firmware dell’app')
    if not self.speed_confirmed:raise ValueError('Attendi la conferma della velocità dalla Mega.')
    self.write('~arm\n');self.home=True;self.pos=[0.0]*5;self.trail=[];self.error='';self.log('Zero virtuale confermato' if self.mode=='demo' else 'Home fisica confermata dall’operatore');return
   if op=='limits':
    if self.busy or self.playing:raise ValueError('Ferma prima la sequenza')
    v=b['limits']
    if len(v)!=5 or any(len(x)!=2 or any(not isinstance(n,(int,float)) or not math.isfinite(n) for n in x) or not -360<=x[0]<=0<=x[1]<=360 or not x[0]<=p<=x[1] for x,p in zip(v,self.pos)):raise ValueError('Limiti non validi: devono contenere zero e la posizione attuale')
    self.limits=v;return
   self.check()
   if self.busy or self.playing:raise ValueError('Attendi il termine o usa STOP')
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
   if op=='home':self.spawn(self.back);return
   if op=='play':
    active=[pose for pose in self.sequence if pose.get('enabled',True)]
    if not active:raise ValueError('Abilita almeno una posa per riprodurre la sequenza.')
    if self.trail or any(abs(x)>.01 for x in self.pos):raise ValueError('Torna a home prima della riproduzione')
    # Validate every stored path before starting; reordered transitions reuse its edges.
    for pose in active:
     if pose.get('mode')!=self.mode:raise ValueError('Registra le pose nella modalità corrente: le anteprime non sono percorsi provati sul robot.')
     p=[0.0]*5
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
