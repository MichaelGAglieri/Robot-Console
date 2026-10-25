# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Local-only Ollama lifecycle. No serial, ROS or external network access."""
import json, os, shutil, subprocess, threading, time, urllib.request, urllib.error
from pathlib import Path

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):
  raise ValueError('Redirect rifiutato: il servizio IA deve restare su questo Mac.')

class OllamaLocal:
 def __init__(self,folder,monitor=True):
  self.folder=Path(folder);self.lock=threading.RLock();self.operation=threading.Lock()
  self.stop_event=threading.Event();self.process=None;self.log_file=None
  self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
  self.models=[];self.loaded=[];self.selected='';self.running=False
  self.busy=False;self.status='Verifica Ollama…';self.error='';self.version=''
  self.binary=self.find_binary();self.cache={}
  try:self.selected=json.loads((self.folder/'ia_settings.json').read_text()).get('model','')
  except (OSError,ValueError,TypeError):pass
  if monitor:threading.Thread(target=self.watch,daemon=True).start()
 @staticmethod
 def find_binary():
  candidates=[Path('/Applications/Ollama.app/Contents/Resources/ollama'),Path.home()/'Applications/Ollama.app/Contents/Resources/ollama',Path('/opt/homebrew/bin/ollama'),Path('/usr/local/bin/ollama')]
  located=shutil.which('ollama')
  if located:candidates.append(Path(located))
  return next((str(p) for p in candidates if p.is_file() and os.access(p,os.X_OK)),'')
 def api(self,path,payload=None,timeout=2):
  if path not in ('version','tags','ps','show','generate','chat'):raise ValueError('API non consentita')
  req=urllib.request.Request('http://127.0.0.1:11434/api/'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  try:
   with self.opener.open(req,timeout=timeout) as r:return json.load(r)
  except urllib.error.HTTPError as e:
   try:detail=json.loads(e.read().decode()).get('error',str(e))
   except (ValueError,UnicodeError):detail=str(e)
   raise ValueError(str(detail)[:500]) from e
 @staticmethod
 def offline_model(name,info):
  return (isinstance(name,str) and bool(name) and ':cloud' not in name.casefold() and not name.casefold().endswith('-cloud') and not info.get('remote_host') and not info.get('remote_model'))
 def refresh(self):
  binary=self.find_binary()
  try:
   version=self.api('version',timeout=.8).get('version','')
   tags=self.api('tags',timeout=1).get('models',[])
   loaded=self.api('ps',timeout=1).get('models',[])
  except Exception:
   with self.lock:
    self.binary=binary;self.running=False;self.loaded=[]
    if not self.busy:self.status='Ollama presente · servizio spento' if binary else 'Ollama non presente su questo Mac · scaricalo dal sito ufficiale'
   return False
  models=[dict(name=m['name'],size=m.get('size',0)) for m in tags if self.offline_model(m.get('name'),m)]
  models.sort(key=lambda m:(m['size'],m['name']))
  with self.lock:
   self.binary=binary;self.running=True;self.version=str(version);self.models=models
   self.loaded=[m['name'] for m in loaded if self.offline_model(m.get('name'),m)]
   names=[m['name'] for m in models]
   if not self.selected and names:self.selected='llama3.2:latest' if 'llama3.2:latest' in names else names[0]
   if not self.busy:
    if not names:self.status='Ollama avviato · nessun modello locale installato'
    elif self.selected in self.loaded:self.status='Pronto · '+self.selected
    elif self.selected and self.selected not in names:self.status='Il modello scelto non è installato: selezionane un altro'
    else:self.status='Ollama avviato · modello da caricare'
  return True
 def watch(self):
  while not self.stop_event.is_set():
   try:self.refresh()
   except Exception:pass
   self.stop_event.wait(4)
 def state(self):
  with self.lock:return dict(installed=bool(self.binary) or self.running,running=self.running,busy=self.busy,status=self.status,error=self.error,version=self.version,models=self.models[:],loaded=self.loaded[:],selected=self.selected)
 def select(self,name):
  with self.lock:
   if self.busy:raise ValueError('Attendi il completamento dell’operazione IA.')
   if name not in [m['name'] for m in self.models]:raise ValueError('Seleziona un modello locale installato.')
   tmp=self.folder/'ia_settings.tmp';tmp.write_text(json.dumps(dict(model=name)));tmp.replace(self.folder/'ia_settings.json')
   self.selected=name;self.error=''
   self.status='Pronto · '+name if name in self.loaded else 'Modello selezionato · verrà caricato alla prossima domanda'
 def launch(self):
  if self.refresh():return
  binary=self.find_binary()
  if not binary:raise ValueError('Ollama non è presente su questo Mac. Scaricalo da ollama.com/download/mac.')
  with self.lock:self.status='Ollama presente · lo sto avviando…'
  env={**os.environ,'OLLAMA_HOST':'127.0.0.1:11434','OLLAMA_NO_CLOUD':'1'}
  self.log_file=open(self.folder/'ollama.log','a')
  self.process=subprocess.Popen([binary,'serve'],stdin=subprocess.DEVNULL,stdout=self.log_file,stderr=self.log_file,env=env)
  deadline=time.monotonic()+25
  while time.monotonic()<deadline:
   if self.stop_event.wait(.3):raise ValueError('Avvio interrotto.')
   if self.refresh():return
   if self.process.poll() is not None:break
  raise ValueError('Ollama non risponde. Consulta ollama.log nella cartella dei dati dell’app.')
 def ensure_ready(self):
  """Runs on a worker thread, never on the heartbeat/control thread."""
  with self.operation:
   with self.lock:self.busy=True;self.error='';self.status='Preparazione IA locale…'
   try:
    if self.stop_event.is_set():raise ValueError('Assistente in chiusura.')
    self.launch()
    with self.lock:
     model=self.selected
     if not model or model not in [m['name'] for m in self.models]:raise ValueError('Nessun modello locale selezionato. Scarica prima un modello in Ollama e aggiorna l’elenco.')
     self.status='Verifica modello locale · '+model
    # Reject cloud aliases even if they do not have a :cloud suffix.
    info=self.api('show',dict(model=model),timeout=10)
    if not self.offline_model(model,info):raise ValueError('Questo modello usa un servizio remoto. Scegli un modello locale per lavorare offline.')
    if info.get('capabilities') is not None and 'completion' not in info['capabilities']:raise ValueError('Il modello scelto non supporta la conversazione.')
    with self.lock:self.status='Caricamento in memoria · '+model
    self.api('generate',dict(model=model,stream=False,keep_alive='10m'),timeout=120)
    self.refresh()
    with self.lock:
     if model not in self.loaded:raise ValueError('Caricamento non confermato da Ollama. Premi Aggiorna o riprova.')
     self.status='Pronto · '+model
    return model
   except Exception as e:
    with self.lock:self.error=str(e);self.status='IA locale non pronta'
    raise
   finally:
    with self.lock:self.busy=False
 def start(self):
  with self.lock:
   if self.busy:return
   self.busy=True;self.error='';self.status='Preparazione IA locale…'
  def work():
   try:self.ensure_ready()
   except Exception:pass
  threading.Thread(target=work,daemon=True).start()
 def refresh_async(self):
  threading.Thread(target=self.refresh,daemon=True).start()
 def chat(self,messages):
  model=self.ensure_ready()
  with self.lock:self.busy=True;self.status='Risposta in corso · '+model
  try:
   response=self.api('chat',dict(model=model,stream=False,think=False,keep_alive='10m',messages=messages,options={'num_predict':350}),timeout=120)
   text=response['message']['content'].strip()
   if not text:raise ValueError('Ollama ha restituito una risposta vuota.')
   with self.lock:self.status='Pronto · '+model;self.error=''
   return '[Ollama locale · '+model+']\n'+text
  except Exception as e:
   with self.lock:self.error=str(e);self.status='Errore durante la risposta'
   raise
  finally:
   with self.lock:self.busy=False
 def stop(self):
  """Unload the selected model; stop only the server owned by this instance."""
  with self.lock:
   if self.busy:raise ValueError('Attendi la fine della risposta o del caricamento prima di liberare la memoria.')
   self.busy=True;self.error='';self.status='Arresto IA e rilascio memoria…'
  def work():
   with self.operation:
    try:
     self.refresh()
     with self.lock:model=self.selected;running=self.running
     if running and model and model in self.loaded:
      self.api('generate',dict(model=model,stream=False,keep_alive=0),timeout=30)
     owned=self.process is not None and self.process.poll() is None
     if owned:self.terminate_owned()
     self.refresh()
     with self.lock:
      if model and model in self.loaded:raise ValueError('Ollama non ha confermato il rilascio del modello. Riprova tra poco.')
      self.status='Ollama fermato · memoria del modello rilasciata' if owned else ('Modello scaricato dalla memoria · servizio Ollama esterno ancora avviato' if self.running else 'Ollama spento · nessun modello caricato')
      self.error=''
    except Exception as e:
     with self.lock:self.error=str(e);self.status='Rilascio memoria non confermato'
    finally:
     with self.lock:self.busy=False
  worker=threading.Thread(target=work,daemon=True);worker.start()
  return worker
 def terminate_owned(self):
  process=self.process
  if process is not None and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=3)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
  self.process=None
  if self.log_file:self.log_file.close();self.log_file=None
 def close(self):
  self.stop_event.set()
  # Never stop a server that another application launched.
  self.terminate_owned()
