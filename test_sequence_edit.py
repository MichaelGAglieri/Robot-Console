# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import os,tempfile,unittest
from unittest.mock import patch
os.environ['DOC_REGIA_DATA']=tempfile.mkdtemp(prefix='robot175-tests-')
import server
class SequenceFixture(unittest.TestCase):
 def setUp(self):
  with patch.object(server.Controller,'io',lambda s:None):self.c=server.Controller()
  self.c.sequence=[];self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='home_set'));self.c.limits=[[-90,90]]*5;self.commands=[]
  def move(a,d,g,record=True):
   self.c.pos[a]=self.c.validate(a,d);self.commands.append((a,d))
   if record:self.c.trail.append(dict(axis=a,delta=d))
  self.c.move=move;self.c.servo=lambda cmd,g:self.commands.append(cmd);self.c.spawn=lambda fn:fn(self.c.generation)
 def pose(self,name,path,grip='non comandata'):
  pos=[0]*6
  for x in path:pos[x['axis']]+=x['delta']
  return dict(name=name,path=path,pos=pos,grip=grip,mode='demo',dwell=0)
 def edit(self,op,**kw):self.c.action(dict(op=op,revision=self.c.sequence_revision,**kw))
class Tests(SequenceFixture):
 def test_reorder_grip(self):
  a=[dict(axis=0,delta=10)];b=a+[dict(axis=1,delta=20)]
  self.c.sequence=[self.pose('A',a,'apri'),self.pose('B',b,'chiudi')]
  self.edit('pose_move',index=1,target=0);self.c.action(dict(op='play'))
  self.assertEqual(self.commands,[(0,10),(1,20),'chiudi',(1,-20),'apri',(0,-10)])
  self.assertEqual(self.c.pos,[0]*6);self.assertEqual(self.c.trail,[])
 def test_delete_preserves_path(self):
  a=[dict(axis=0,delta=10)];b=a+[dict(axis=1,delta=20)]
  self.c.sequence=[self.pose('A',a),self.pose('B',b)]
  self.edit('pose_delete',index=0);self.assertEqual(self.c.sequence[0]['path'],b)
  self.c.action(dict(op='play'));self.assertEqual(self.c.pos,[0]*6)
 def test_grip_record_edit_persist(self):
  self.c.grip='chiudi';self.c.action(dict(op='record',name='presa'))
  self.assertEqual(self.c.sequence[0]['grip'],'chiudi')
  self.c.action(dict(op='record',name='aperta',grip='apri'));self.edit('pose_grip',index=0,grip='apri')
  with patch.object(server.Controller,'io',lambda s:None):loaded=server.Controller()
  self.assertEqual([p['grip'] for p in loaded.sequence],['apri','apri'])
  self.c.action(dict(op='play'));self.assertEqual(self.commands,['apri','apri'])
 def test_busy_stale_invalid(self):
  self.c.sequence=[self.pose('A',[])];self.c.busy=True
  with self.assertRaises(ValueError):self.edit('pose_delete',index=0)
  self.c.busy=False
  with self.assertRaises(ValueError):self.c.action(dict(op='pose_delete',index=0,revision=-1))
  with self.assertRaises(ValueError):self.edit('pose_grip',index=0,grip='invalid')
  self.assertEqual(len(self.c.sequence),1)
 def test_undo(self):
  self.c.sequence=[self.pose('A',[])];self.edit('pose_delete',index=0)
  self.assertEqual(self.c.sequence,[])
  self.edit('pose_undo');self.assertEqual(self.c.sequence[0]['name'],'A')
  self.assertIsNone(self.c.sequence_undo)
 def test_branch_routes(self):
  a=[dict(axis=0,delta=10)];b=[dict(axis=1,delta=20)]
  self.c.sequence=[self.pose('A',a),self.pose('B',b)]
  self.c.action(dict(op='play'))
  self.assertEqual(self.commands,[(0,10),(0,-10),(1,20),(1,-20)])
 def test_limits(self):
  self.c.sequence=[self.pose('A',[dict(axis=0,delta=91)])]
  with self.assertRaises(ValueError):self.c.action(dict(op='play'))
  self.assertEqual(self.commands,[])
 def test_firmware_speed(self):
  self.c.mode='robot';self.c.home=False;self.c.receive('DOC REGIA 2');self.assertEqual(self.c.max_speed,10)
  with self.assertRaises(ValueError):self.c.action(dict(op='set_speed',speed=20))
  self.c.receive('DOC REGIA 4');self.assertEqual(self.c.max_speed,20)
  self.c.action(dict(op='set_speed',speed=20));self.assertFalse(self.c.speed_confirmed)
  self.c.receive('SPEED 20.00');self.assertTrue(self.c.speed_confirmed)
  for v in [20.1,30,0,True,float('nan')]:
   with self.assertRaises(ValueError):self.c.action(dict(op='set_speed',speed=v))
if __name__=='__main__':unittest.main()
