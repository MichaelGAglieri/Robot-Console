# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import json,re,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from assistant_local import Assistant,Journal
class LocalizationTests(unittest.TestCase):
 def test_catalog_placeholders_match_and_key_controls_are_translated(self):
  root=Path(__file__).parent;catalog=json.loads((root/'native/Localization/English.json').read_text());token=re.compile(r'%(?:\d+\$)?(?:@|lld|ld|d|g|(?:\.\d+)?f)|%%')
  for key,value in catalog.items():self.assertEqual(token.findall(key),token.findall(value),key)
  for key in ('Guida','Lingua','Muovi e osserva','Conferma HOME','Carica sulla Mega…','Microstepping, riduttori e sorgenti','J%lld massimo','Scollega controllo'):self.assertNotEqual(catalog[key],key)
  for language in ('it','en'):self.assertTrue((root/f'native/Localization/{language}.lproj/Localizable.strings').is_file())
 def test_english_assistant_only_reads_state_and_stores_explicit_notes(self):
  with tempfile.TemporaryDirectory() as folder:
   journal=Journal(folder);c=Mock();c.state.return_value=dict(mode='demo',connected=False,home=False,busy=False,pos=[0]*6,speed=5,sequence=[],cycle=0);a=Assistant(c,journal);a.language='en'
   self.assertIn('Mode: demo',a.answer('What is the status?'));self.assertIn('Saved in local memory',a.answer('Remember: Bench note'));self.assertIn('Bench note',a.answer('Show notes'));c.action.assert_not_called()
   journal.db.close()
