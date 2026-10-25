# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import copy,json,unittest
from unittest.mock import patch
from test_sequence_edit import SequenceFixture
import server
class PoseEditorTests(SequenceFixture):
 def request(self,index=0,**changes):
  p=self.c.sequence[index]
  values=dict(index=index,name=p['name'],pos=p['pos'][:],dwell=p['dwell'],grip=p['grip'],enabled=p.get('enabled',True))
  values.update(changes);return values
 def test_metadata_save_does_not_move(self):
  path=[dict(axis=0,delta=10)];self.c.sequence=[self.pose('Old',path)]
  self.c.connected=False;self.c.write=lambda s:self.fail('Editing must never transmit')
  self.edit('pose_update',**self.request(name='New',dwell=2.5,grip='chiudi',enabled=False))
  p=self.c.sequence[0]
  self.assertEqual((p['name'],p['dwell'],p['grip'],p['enabled']),('New',2.5,'chiudi',False))
  self.assertEqual(p['path'],path);self.assertEqual(self.commands,[])
  with patch.object(server.Controller,'io',lambda s:None):loaded=server.Controller()
  self.assertEqual(loaded.sequence[0],p)
  self.edit('pose_undo');self.assertEqual(self.c.sequence[0]['name'],'Old')
 def test_angles_extend_then_replace(self):
  base=[dict(axis=0,delta=10)];self.c.sequence=[self.pose('A',base)]
  self.edit('pose_update',**self.request(pos=[15,20,0,0,0]))
  self.assertEqual(self.c.sequence[0]['path'],base+[dict(axis=0,delta=5),dict(axis=1,delta=20)])
  self.edit('pose_update',**self.request(pos=[12,0,0,0,0]))
  self.assertEqual(self.c.sequence[0]['path'],base+[dict(axis=0,delta=2)])
  self.c.action(dict(op='play'))
  self.assertEqual(self.commands,[(0,10),(0,2),(0,-2),(0,-10)])
  self.assertEqual(self.c.pos,[0]*5)
 def test_disabled_actions_and_all_disabled(self):
  a=[dict(axis=0,delta=10)];b=a+[dict(axis=1,delta=20)]
  self.c.sequence=[self.pose('A',a,'chiudi'),self.pose('B',b,'apri')]
  self.edit('pose_enable',index=0,enabled=False);self.c.action(dict(op='play'))
  self.assertNotIn('chiudi',self.commands);self.assertIn('apri',self.commands)
  self.c.playing=False;self.commands.clear();self.edit('pose_enable',index=1,enabled=False)
  with self.assertRaises(ValueError):self.c.action(dict(op='play'))
  self.assertEqual(self.commands,[])
  self.edit('pose_enable',index=0,enabled=True);self.c.action(dict(op='play'));self.assertIn('chiudi',self.commands)
 def test_reject_bad_or_stale_edits_atomically(self):
  self.c.sequence=[self.pose('A',[])];before=copy.deepcopy(self.c.sequence)
  for changes in [dict(name=''),dict(name='a'*61),dict(pos=[0]*4),dict(pos=[float('nan')]*5),dict(pos=[361]*5),dict(dwell=-1),dict(dwell=True),dict(grip='bad'),dict(enabled='yes')]:
   with self.assertRaises(ValueError):self.edit('pose_update',**self.request(**changes))
   self.assertEqual(self.c.sequence,before)
  self.c.busy=True
  with self.assertRaises(ValueError):self.edit('pose_enable',index=0,enabled=False)
  self.c.busy=False
  with self.assertRaises(ValueError):self.c.action(dict(op='pose_update',revision=-1,**self.request()))
 def test_new_angles_respect_limits_before_motion(self):
  self.c.sequence=[self.pose('A',[])]
  self.edit('pose_update',**self.request(pos=[100,0,0,0,0]))
  with self.assertRaises(ValueError):self.c.action(dict(op='play'))
  self.assertEqual(self.commands,[])
 def test_720_degree_change_split(self):
  self.c.limits=[[-360,360]]*5;self.c.sequence=[self.pose('A',[dict(axis=0,delta=-360)])]
  self.edit('pose_update',**self.request(pos=[360,0,0,0,0]))
  self.assertEqual([x['delta'] for x in self.c.sequence[0]['path']],[-360,360,360])
  self.assertTrue(all(abs(x['delta'])<=360 for x in self.c.sequence[0]['path']))
if __name__=='__main__':unittest.main()
