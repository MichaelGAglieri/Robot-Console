# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import json,tempfile,unittest,threading,time
from pathlib import Path
from unittest.mock import patch,Mock
from ollama_local import OllamaLocal

class FakeOllama(OllamaLocal):
 def __init__(self,folder):
  self.calls=[];self.available=True;self.loaded_names=[];self.remote=False
  super().__init__(folder,monitor=False)
 def api(self,path,payload=None,timeout=2):
  self.calls.append((path,payload))
  if not self.available:raise OSError('spento')
  if path=='version':return dict(version='test')
  if path=='tags':return dict(models=[dict(name='local:latest',size=42),dict(name='remote:cloud',size=1,remote_host='ollama.com')])
  if path=='ps':return dict(models=[dict(name=n) for n in self.loaded_names])
  if path=='show':return dict(capabilities=['completion'],remote_host='ollama.com' if self.remote else '')
  if path=='generate':
   if payload.get('keep_alive')==0:self.loaded_names=[n for n in self.loaded_names if n!=payload['model']]
   else:self.loaded_names=[payload['model']]
   return dict(done=True)
  if path=='chat':return dict(message=dict(content='Risposta locale di prova'))
  raise AssertionError(path)

class OllamaTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.ai=FakeOllama(self.tmp.name)
 def tearDown(self):self.ai.close();self.tmp.cleanup()
 def test_running_is_not_loaded(self):
  self.ai.refresh();s=self.ai.state()
  self.assertTrue(s['running']);self.assertEqual(s['loaded'],[]);self.assertEqual(len(s['models']),1)
  self.assertNotIn('Pronto',s['status'])
 def test_preload_and_chat_uses_selected(self):
  self.ai.refresh();self.ai.select('local:latest')
  self.assertIn('Risposta locale',self.ai.chat([dict(role='user',content='ciao')]))
  self.assertEqual(self.ai.state()['loaded'],['local:latest'])
  self.assertEqual(next(p for name,p in self.ai.calls if name=='chat')['model'],'local:latest')
  self.assertNotIn('pull',[name for name,p in self.ai.calls])
  again=OllamaLocal(self.tmp.name,monitor=False)
  self.assertEqual(again.selected,'local:latest');again.close()
 def test_cloud_alias_rejected_before_prompt(self):
  self.ai.refresh();self.ai.remote=True
  with self.assertRaisesRegex(ValueError,'remoto'):self.ai.chat([dict(role='user',content='privato')])
  self.assertFalse(any(n in ('chat','generate') for n,p in self.ai.calls))
 def test_no_installation_message(self):
  self.ai.available=False
  with patch.object(self.ai,'find_binary',return_value=''):
   self.ai.refresh()
   self.assertFalse(self.ai.state()['installed'])
   with self.assertRaisesRegex(ValueError,'Scaricalo'):self.ai.ensure_ready()
  self.assertFalse(self.ai.busy)
 def test_stopped_service_launched_on_demand(self):
  self.ai.available=False
  def launch():self.ai.available=True;self.ai.refresh()
  with patch.object(self.ai,'launch',side_effect=launch) as start:
   self.ai.chat([dict(role='user',content='ciao')])
   start.assert_called_once()
 def test_failure_visible_and_busy_clears(self):
  self.ai.refresh()
  original=self.ai.api
  def api(path,*args,**kwargs):
   if path=='generate':raise TimeoutError('caricamento scaduto')
   return original(path,*args,**kwargs)
  with patch.object(self.ai,'api',side_effect=api):
   with self.assertRaises(TimeoutError):self.ai.ensure_ready()
  self.assertFalse(self.ai.busy);self.assertIn('scaduto',self.ai.state()['error'])
 def test_launch_loopback_and_no_cloud(self):
  self.ai.available=False
  process=Mock()
  def spawn(args,**kwargs):
   self.assertEqual(args,['/test/ollama','serve'])
   self.assertEqual(kwargs['env']['OLLAMA_HOST'],'127.0.0.1:11434')
   self.assertEqual(kwargs['env']['OLLAMA_NO_CLOUD'],'1')
   self.ai.available=True
   return process
  with patch.object(self.ai,'find_binary',return_value='/test/ollama'),patch('ollama_local.subprocess.Popen',side_effect=spawn):
   self.ai.ensure_ready()
  self.ai.process=None
 def test_unknown_selection_refused(self):
  self.ai.refresh()
  with self.assertRaises(ValueError):self.ai.select('not-installed')
 def test_stop_unloads_selected_without_stopping_external_server(self):
  self.ai.refresh();self.ai.loaded_names=['local:latest','other:latest']
  worker=self.ai.stop();worker.join(timeout=2)
  self.assertFalse(self.ai.busy);self.assertFalse(self.ai.error)
  self.assertEqual(self.ai.loaded_names,['other:latest'])
  self.assertIsNone(self.ai.process)
  request=next(p for name,p in self.ai.calls if name=='generate')
  self.assertEqual(request['keep_alive'],0)
 def test_stop_when_offline_does_not_launch(self):
  self.ai.available=False
  with patch.object(self.ai,'launch') as launch:
   worker=self.ai.stop();worker.join(timeout=2)
   launch.assert_not_called()
  self.assertFalse(self.ai.busy);self.assertFalse(self.ai.error)
 def test_stop_owned_service(self):
  self.ai.refresh();self.ai.loaded_names=['local:latest']
  process=Mock();process.poll.return_value=None
  process.terminate.side_effect=lambda:setattr(self.ai,'available',False)
  self.ai.process=process
  worker=self.ai.stop();worker.join(timeout=2)
  process.terminate.assert_called_once()
  self.assertIsNone(self.ai.process);self.assertFalse(self.ai.running);self.assertFalse(self.ai.error)
 def test_stop_busy_is_refused(self):
  self.ai.busy=True
  with self.assertRaisesRegex(ValueError,'Attendi'):self.ai.stop()
  self.ai.busy=False
 def test_external_server_is_not_stopped(self):
  self.ai.refresh();self.ai.close()
  self.assertIsNone(self.ai.process)
if __name__=='__main__':unittest.main()
