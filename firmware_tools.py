# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Arduino firmware workflow. Upload is possible only after explicit UI confirmation."""
import glob, hashlib, json, os, shutil, subprocess, tempfile, threading, time
from pathlib import Path

FQBN='arduino:avr:mega:cpu=atmega2560'
CORE='arduino:avr@1.8.8'
LIBRARY='AccelStepper@1.64'

class FirmwareTools:
 def __init__(self,folder,controller,journal=None):
  self.folder=Path(folder);self.controller=controller;self.journal=journal
  self.lock=threading.RLock();self.busy=False;self.phase='idle'
  self.status='Firmware incluso: Regia 4 · Mega 2560';self.error='';self.logs=[]
  self.cli=self.find_cli();self.boards=[];self.success=False;self.cancel=threading.Event()
  self.process=None;self.thread=None
 @staticmethod
 def find_cli():
  candidates=[Path(__file__).parent/'Tools/arduino-cli',Path('/opt/homebrew/bin/arduino-cli'),Path('/usr/local/bin/arduino-cli'),Path('/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli'),Path.home()/'Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli']
  found=shutil.which('arduino-cli')
  if found:candidates.append(Path(found))
  return next((str(p) for p in candidates if p.is_file() and os.access(p,os.X_OK)),'')
 def state(self):
  with self.lock:return dict(available=bool(self.cli),tool=self.cli,busy=self.busy,phase=self.phase,status=self.status,error=self.error,logs=self.logs[-100:],boards=self.boards[:],success=self.success)
 def log(self,text):
  with self.lock:self.logs=(self.logs+[str(text).rstrip()[:2000]])[-100:]
 def stage(self,phase,text):
  with self.lock:self.phase=phase;self.status=text
  self.log(text)
 def _check(self):
  if self.cancel.is_set():raise ValueError('Operazione annullata prima del caricamento.')
 def run(self,args,timeout=180,json_output=False):
  self._check()
  output=[]
  self.process=subprocess.Popen([self.cli,*args],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  p=self.process
  def read():
   for line in p.stdout:
    output.append(line)
    if len(output)>5000:del output[:1000]
    if not json_output:self.log(line)
  reader=threading.Thread(target=read,daemon=True);reader.start()
  deadline=time.monotonic()+timeout
  try:
   while p.poll() is None:
    if time.monotonic()>deadline:raise TimeoutError('Tempo massimo superato: '+args[0])
    if self.phase!='uploading':self._check()
    time.sleep(.08)
  except Exception:
   p.terminate()
   try:p.wait(timeout=2)
   except subprocess.TimeoutExpired:p.kill();p.wait()
   raise
  finally:
   reader.join(timeout=2);p.stdout.close();self.process=None
  result=''.join(output)
  if p.returncode:
   if json_output:self.log(result[-3000:])
   raise ValueError('Arduino CLI: '+args[0]+' non riuscito. Consulta il log.')
  return json.loads(result) if json_output else result
 @staticmethod
 def parse_boards(data):
  ports=data.get('detected_ports',[]) if isinstance(data,dict) else data
  boards=[]
  for item in ports:
   port=item.get('port',{})
   address=port.get('address','')
   if port.get('protocol')!='serial' or not address.startswith(('/dev/cu.usbmodem','/dev/cu.usbserial','/dev/cu.wchusbserial')):continue
   matches=item.get('matching_boards',[])
   known=[b.get('fqbn','') for b in matches]
   mega=any(b=='arduino:avr:mega' or b.startswith('arduino:avr:mega:') for b in known)
   compatible=mega or not known
   identity=json.dumps([address,item.get('hardware_id',''),port.get('properties',{}),sorted(known)],sort_keys=True)
   boards.append(dict(port=address,name='Mega 2560' if mega else ('Scheda non identificata: conferma Mega 2560' if not known else ', '.join(b.get('name','') for b in matches)),compatible=compatible,identity=hashlib.sha256(identity.encode()).hexdigest()))
  return boards
 def scan(self):
  boards=self.parse_boards(self.run(['board','list','--format','json'],timeout=25,json_output=True))
  with self.lock:self.boards=boards
  return boards
 def verify_port(self,port,identity):
  board=next((b for b in self.scan() if b['port']==port),None)
  if not board or board['identity']!=identity:raise ValueError('La scheda o la porta è cambiata. Aggiorna le porte e conferma di nuovo.')
  if not board['compatible']:raise ValueError('La scheda rilevata non è una Mega 2560.')
 def start(self,operation,port='',confirmed=False):
  if operation not in ('scan','compile','setup','upload'):raise ValueError('Operazione firmware non valida.')
  if operation=='upload' and os.environ.get('DOC_REGIA_NO_HARDWARE')=='1':raise ValueError('Il caricamento sulla Mega è disabilitato nell’anteprima isolata.')
  # Controller gate is shared with normal motion commands, avoiding a connect/upload race.
  with self.controller.lock,self.lock:
   if self.busy:raise ValueError('Operazione firmware già in corso.')
   if self.controller.connected or self.controller.busy or self.controller.playing:raise ValueError('Scollega prima il controllo del robot dall’app.')
   self.cli=self.find_cli()
   if not self.cli:raise ValueError('Arduino CLI non trovato. Installa Arduino CLI oppure Arduino IDE; l’editor non deve essere aperto.')
   board=None
   if operation=='upload':
    if confirmed is not True:raise ValueError('Conferma esplicitamente il caricamento sulla Mega.')
    board=next((b.copy() for b in self.boards if b['port']==port),None)
    if not board or not board['compatible']:raise ValueError('Aggiorna le porte e seleziona una Mega 2560.')
   self.busy=True;self.controller.firmware_busy=True;self.cancel.clear();self.error='';self.success=False;self.logs=[]
   self.phase='starting';self.status='Preparazione strumenti firmware…'
  self.thread=threading.Thread(target=self.work,args=(operation,board),daemon=True);self.thread.start()
 def work(self,operation,board):
  try:
   if operation=='scan':
    self.stage('scanning','Ricerca delle porte USB…');boards=self.scan()
    self.stage('done',str(len(boards))+' porte USB rilevate. Nessun firmware caricato.')
   elif operation=='setup':
    self.stage('setup','Preparazione dipendenze: è necessaria Internet.')
    self.run(['core','update-index'],timeout=180)
    self.run(['core','install',CORE],timeout=600)
    self.run(['lib','update-index'],timeout=180)
    self.run(['lib','install',LIBRARY],timeout=300)
    self.stage('done','Dipendenze pronte. Nessun firmware caricato.')
   else:
    if board:
     self.stage('checking','Verifica della scheda selezionata…')
     self.verify_port(board['port'],board['identity'])
    source=self.workspace.path if hasattr(self,'workspace') else Path(__file__).parent/'RegiaDemo'
    if not (source/'RegiaDemo.ino').is_file():raise ValueError('Firmware non incluso nell’app.')
    with tempfile.TemporaryDirectory(prefix='robot-console-firmware-') as temp:
     sketch=Path(temp)/'RegiaDemo';shutil.copytree(source,sketch)
     build=Path(temp)/'build'
     self.stage('compiling','Compilazione Regia 4 per Mega 2560…')
     self.run(['compile','--fqbn',FQBN,'--build-path',str(build),str(sketch)],timeout=180)
     if not board:self.stage('done','Compilazione riuscita. Nessuna scrittura sulla scheda.')
     else:
      self._check()
      self.stage('checking','Ricontrollo della porta prima della scrittura…')
      self.verify_port(board['port'],board['identity'])
      self._check()
      self.stage('uploading','Caricamento e verifica sulla Mega: non scollegare la USB.')
      self.run(['upload','--fqbn',FQBN,'--port',board['port'],'--input-dir',str(build),'--verify',str(sketch)],timeout=180)
      # No serial connection or ARM command after flashing.
      with self.controller.lock:
       self.controller.home=False;self.controller.identified=False;self.controller.speed_confirmed=False
      self.stage('done','Firmware caricato e verificato. Controllo scollegato: riconnetti e ristabilisci HOME.')
   with self.lock:self.success=True
  except Exception as e:
   with self.lock:self.phase='error';self.error=str(e);self.status='Operazione firmware non completata'
   self.log(str(e))
  finally:
   if self.journal:
    try:self.journal.add('firmware',operation,self.status+(' · '+self.error if self.error else ''))
    except Exception:pass
   with self.controller.lock,self.lock:self.busy=False;self.controller.firmware_busy=False
 def stop(self):
  with self.lock:
   if self.phase=='uploading':raise ValueError('Attendi la conclusione della scrittura sulla Mega.')
   self.cancel.set()
 def close(self):
  with self.lock:
   if self.phase!='uploading':self.cancel.set()
  if self.thread:self.thread.join(timeout=3)
