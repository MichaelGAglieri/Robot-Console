# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import copy,json,math,os,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch,Mock
import server
from robot_model import parse_urdf,default_urdf,frames,tcp,position_ik
from studio import Studio
from firmware_workspace import FirmwareWorkspace,DEFAULT,identity,validate,speed_limit

SIMPLE=b'''<robot name="two"><link name="base"/><link name="arm"/><link name="tip"/>
<joint name="yaw" type="revolute"><parent link="base"/><child link="arm"/><axis xyz="0 0 1"/><limit lower="-3.14" upper="3.14"/></joint>
<joint name="end" type="fixed"><parent link="arm"/><child link="tip"/><origin xyz="1 0 0"/></joint></robot>'''
class ModelTests(unittest.TestCase):
 def test_fk_rotates_offset_not_joint_origin(self):
  m=parse_urdf(SIMPLE);p=tcp(m,{'yaw':math.pi/2});self.assertAlmostEqual(p[0],0,places=10);self.assertAlmostEqual(p[1],1,places=10)
 def test_default_has_five_axes(self):self.assertEqual(sum(j['kind']!='fixed' for j in parse_urdf(default_urdf())['joints']),5)
 def test_rejects_entities_and_xacro(self):
  for raw in [b'<!DOCTYPE robot [<!ENTITY x "bad">]><robot name="x"/>',b'<robot xmlns:xacro="abc"><xacro:include/></robot>']:
   with self.assertRaises(ValueError):parse_urdf(raw)
 def test_rejects_duplicate_parent_and_cycles(self):
  for raw in [SIMPLE.replace(b'<link name="arm"/>',b'<link name="base"/>'),SIMPLE.replace(b'<child link="tip"/>',b'<child link="base"/>')]:
   with self.assertRaises(ValueError):parse_urdf(raw)
 def test_rejects_nan_and_zero_axis(self):
  for axis in [b'nan 0 1',b'0 0 0']:
   with self.assertRaises(ValueError):parse_urdf(SIMPLE.replace(b'0 0 1',axis))
 def test_mimic_cycle_rejected(self):
  with self.assertRaises(ValueError):parse_urdf(SIMPLE.replace(b'<axis xyz="0 0 1"/>',b'<mimic joint="yaw"/>'))
 def test_position_ik_and_disabled(self):
  m=parse_urdf(SIMPLE);result=position_ik(m,{'yaw':.2},[0,1,0],{'yaw':True});self.assertTrue(result['converged']);self.assertLess(result['error_m'],.001)
  result=position_ik(m,{'yaw':0},[0,1,0],{'yaw':False});self.assertFalse(result['converged']);self.assertEqual(result['positions']['yaw'],0)
 def test_mesh_escape_never_copied(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder)/'package'/'urdf';base.mkdir(parents=True);assets=Path(folder)/'assets';assets.mkdir()
   secret=Path(folder)/'outside.stl';secret.write_text('not a mesh')
   raw=SIMPLE.replace(b'<link name="arm"/>',b'<link name="arm"><visual><geometry><mesh filename="../../outside.stl"/></geometry></visual></link>')
   m=parse_urdf(raw,base,assets);self.assertTrue(m['warnings']);self.assertEqual(list(assets.iterdir()),[])

class StudioFixture(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.data=patch.object(server,'DATA',self.folder);self.data.start()
  with patch.object(server.Controller,'io',lambda c:None):self.c=server.Controller()
  self.s=Studio(self.folder,self.c,builtin=False);self.c.write=Mock()
 def tearDown(self):self.data.stop();self.temp.cleanup()
class StudioTests(StudioFixture):
 def test_import_does_not_open_or_write_serial(self):
  path=self.folder/'arm.urdf';path.write_bytes(SIMPLE)
  with patch.object(os,'open',side_effect=AssertionError('serial forbidden')):self.s.import_urdf(path)
  self.assertEqual(self.s.mapping,{'yaw':-1});self.c.write.assert_not_called();self.assertFalse(self.c.connected)
 def test_import_fails_without_losing_old_model(self):
  old=self.s.model['source_hash'];p=self.folder/'bad.urdf';p.write_text('<robot>')
  with self.assertRaises(ValueError):self.s.import_urdf(p)
  self.assertEqual(self.s.model['source_hash'],old)
 def test_project_roundtrip_resets_physical_authorization(self):
  self.s.verified=True;self.s.preview['joint_1']=.3;archive=self.folder/'robot.zip';self.s.export_project(archive)
  self.s.import_project(archive);self.assertFalse(self.s.verified);self.assertEqual(self.s.preview['joint_1'],.3)
  self.assertNotIn('token',zipfile.ZipFile(archive).read('project.json').decode())
 def test_malformed_project_is_transactional(self):
  old=self.s.model['source_hash'];data=self.s.data();data['urdf']=SIMPLE.decode();data['tool']=[1]
  with self.assertRaises(ValueError):self.s.load_data(data)
  self.assertEqual(self.s.model['source_hash'],old)
 def test_zip_path_traversal(self):
  archive=self.folder/'bad.zip'
  with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.txt','bad')
  with self.assertRaises(ValueError):self.s.import_project(archive)
  self.assertFalse((self.folder.parent/'escape.txt').exists())
 def test_joint_exclusion_blocks_jog_home_and_sequence(self):
  self.c.action({'op':'connect','mode':'demo'});self.c.action({'op':'home_set'});self.c.limits=[[-90,90]]*5
  self.c.action({'op':'joint_enable','axis':0,'enabled':False})
  self.c.spawn=Mock()
  with self.assertRaises(ValueError):self.c.action({'op':'jog','axis':0,'delta':1})
  self.c.trail=[{'axis':0,'delta':1}]
  with self.assertRaises(ValueError):self.c.action({'op':'home'})
  self.c.trail=[];self.c.sequence=[dict(name='x',mode='demo',path=[dict(axis=0,delta=1)],pos=[1,0,0,0,0],grip='non comandata',enabled=True,dwell=0)]
  with self.assertRaises(ValueError):self.c.action({'op':'play'})
  self.c.spawn.assert_not_called()
 def test_no_partial_home_before_disabled_joint(self):
  self.c.action({'op':'connect','mode':'demo'});self.c.action({'op':'home_set'});self.c.trail=[dict(axis=0,delta=1),dict(axis=1,delta=1)]
  self.c.axes_enabled[0]=False;self.c.move=Mock()
  with self.assertRaises(ValueError):self.c.back(self.c.generation)
  self.c.move.assert_not_called()
 def test_preview_is_visual_only(self):
  self.s.action({'op':'studio_preview','joint':'joint_1','value':.5});self.assertFalse(self.s.follow);self.assertEqual(self.c.pos,[0]*6);self.c.write.assert_not_called()
 def test_collision_detects_intermediate_link(self):
  self.s.model=parse_urdf(SIMPLE);self.s.tip='tip';self.s.reset_joints();self.s.calibration={'yaw':{'sign':1,'offset':0}}
  self.s.obstacles=[dict(name='box',center=[.5,0,0],size=[.1,.1,.1])]
  self.assertTrue(self.s.collision_report({'yaw':0}));self.assertFalse(self.s.collision_report({'yaw':math.pi/2}))
 def test_program_rejects_missing_sensor_before_motion(self):
  self.c.action({'op':'connect','mode':'demo'});self.c.action({'op':'home_set'})
  self.s.blocks=self.s.validate_blocks([dict(kind='sensor',name='x',sensor='missing',expected=1,timeout=.1)]);self.c.write.reset_mock()
  with self.assertRaises(ValueError):self.s.run_program()
  self.c.write.assert_not_called()
 def test_program_has_bounded_non_nested_loops(self):
  with self.assertRaises(ValueError):self.s.validate_blocks([dict(kind='repeat',start=0,count=2)])
  blocks=self.s.validate_blocks([dict(kind='wait',seconds=0),dict(kind='repeat',start=0,count=3)])
  self.s.blocks=blocks;self.assertEqual(len(self.s.expanded_program()),3)
 def test_sensor_samples_marked_simulated(self):
  self.s.define_sensor('contact','digital');self.s.action(dict(op='studio_sensor_value',name='contact',value=1));self.assertEqual(self.s.sensors['contact']['source'],'simulato')
  self.c.mode='robot'
  with self.assertRaises(ValueError):self.s.action(dict(op='studio_sensor_value',name='contact',value=1))
 def test_recorder_and_csv(self):
  self.s.recording=True;self.s.state();path=self.folder/'record.csv';self.s.export_recording(path);self.assertIn('j5_deg',path.read_text());self.assertEqual(len(self.s.samples),1)

class WorkspaceTests(StudioFixture):
 def test_defaults_preserved_and_edit_backed_up(self):
  w=FirmwareWorkspace(self.folder,self.c);original=w.file('RegiaDemo.ino').read_text();w.save_file('RegiaDemo.ino',original+'\n// edit\n')
  self.assertTrue(list((w.folder/'revisions').iterdir()));self.c.write.assert_not_called()
 def test_generation_uses_both_microstep_and_ratio(self):
  w=FirmwareWorkspace(self.folder,self.c);p=copy.deepcopy(DEFAULT);p['axes'][0].update(microstep=16,reduction=10);w.generate(p)
  code=w.file('RegiaDemo.ino').read_text();self.assertIn('{3200, 1600',code);self.assertIn('{10.0f, 38.4f',code);self.assertIn('CONFIG '+identity(p),code);self.assertFalse(self.c.hardware_ok());self.c.receive('CONFIG '+identity(p));self.assertTrue(self.c.hardware_ok());self.c.write.assert_not_called()
 def test_saving_and_generating_require_disconnection(self):
  w=FirmwareWorkspace(self.folder,self.c);self.c.connected=True
  with self.assertRaises(ValueError):w.generate(DEFAULT)
  with self.assertRaises(ValueError):w.save_file('RegiaDemo.ino','bad')
 def test_free_editor_cannot_escape_workspace(self):
  w=FirmwareWorkspace(self.folder,self.c)
  with self.assertRaises(ValueError):w.save_file('../server.py','bad')
 def test_budget_caps_speed_and_rejects_invalid_switches(self):
  p=copy.deepcopy(DEFAULT);p['axes'][0]['reduction']=100;self.assertLess(speed_limit(p),20)
  p['axes'][0]['microstep']=3
  with self.assertRaises(ValueError):validate(p)
 def test_legacy_firmware_only_with_default_profile(self):
  w=FirmwareWorkspace(self.folder,self.c);self.assertTrue(self.c.hardware_ok());p=copy.deepcopy(DEFAULT);p['axes'][0]['reduction']=10;w.generate(p)
  self.assertFalse(self.c.hardware_ok());self.c.receive('DOC REGIA 4');self.assertFalse(self.c.hardware_ok());self.c.receive('CONFIG '+identity(p));self.assertTrue(self.c.hardware_ok())

class ProgramExecutionTests(StudioFixture):
 def wait_program(self):
  import time
  deadline=time.monotonic()+3
  while self.s.program_running and time.monotonic()<deadline:self.c.browser=time.monotonic();time.sleep(.02)
  self.assertFalse(self.s.program_running)
 def test_wait_note_completes_and_returns_home(self):
  self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='home_set'));self.c.write.reset_mock()
  self.s.blocks=self.s.validate_blocks([dict(kind='note',name='test note'),dict(kind='wait',seconds=.01)])
  self.s.run_program();self.wait_program();self.assertEqual(self.c.cycle,1);self.assertFalse(self.s.program_error);self.c.write.assert_not_called()
 def test_missing_fresh_data_times_out(self):
  self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='home_set'));self.s.define_sensor('contact','digital')
  self.s.blocks=self.s.validate_blocks([dict(kind='sensor',sensor='contact',timeout=.1,expected=1)])
  self.s.run_program();self.wait_program();self.assertIn('Timeout sensore',self.s.program_error);self.assertFalse(self.c.home)
 def test_recorded_path_preview_reverses_old_branch_first(self):
  self.c.sequence=[dict(name='a',pos=[10,0,0,0,0],path=[dict(axis=0,delta=10)],mode='demo',enabled=True),dict(name='b',pos=[0,10,0,0,0],path=[dict(axis=1,delta=10)],mode='demo',enabled=True)]
  self.s.preview_sequence(1,.25);self.assertAlmostEqual(math.degrees(self.s.preview['joint_1']),5);self.assertEqual(self.s.preview['joint_2'],0);self.c.write.assert_not_called()

class IntegrationGuardTests(StudioFixture):
 def test_isolated_preview_blocks_usb_and_upload_before_any_operation(self):
  from firmware_tools import FirmwareTools
  with patch.dict(os.environ,{'DOC_REGIA_NO_HARDWARE':'1'}),patch.object(os,'open',side_effect=AssertionError('forbidden')):
   with self.assertRaisesRegex(ValueError,'anteprima isolata'):self.c.action(dict(op='connect',mode='robot',port='/dev/cu.usbmodem1'))
   tool=FirmwareTools(self.folder,self.c)
   with self.assertRaisesRegex(ValueError,'anteprima isolata'):tool.start('upload','/dev/cu.usbmodem1',True)
 def test_intermediate_collision_uses_actual_start_not_virtual_target(self):
  self.s.model=parse_urdf(SIMPLE);self.s.reset_joints();self.s.mapping={'yaw':0};self.s.preview={'yaw':math.pi/2};self.s.follow=False
  self.c.pos[0]=-90;self.c.limits=[[-180,180]]*5
  self.s.obstacles=[dict(name='middle',center=[.5,0,0],size=[.1,.1,.1])]
  self.assertFalse(self.s.collision_report({'yaw':math.pi/2}));self.assertFalse(self.s.collision_report({'yaw':-math.pi/2}))
  with self.assertRaisesRegex(ValueError,'lungo il percorso'):self.s.target_path(self.s.preview)
  self.c.write.assert_not_called()
 def test_calibrated_project_accepts_valid_input_outside_raw_interval(self):
  self.s.model=parse_urdf(SIMPLE);self.s.raw=SIMPLE.decode();self.s.reset_joints();self.s.tip='tip';self.s.calibration['yaw']={'sign':-1,'offset':1};self.s.preview['yaw']=4
  self.s.load_data(self.s.data());self.assertEqual(self.s.preview['yaw'],4)
 def test_hardware_disabled_joint_cannot_preview_or_ik(self):
  self.c.axes_enabled[0]=False
  with self.assertRaisesRegex(ValueError,'escluso'):self.s.action(dict(op='studio_preview',joint='joint_1',value=.5))
 def test_ik_rejects_wrong_target_dimensions(self):
  with self.assertRaises(ValueError):position_ik(self.s.model,self.s.preview,[1,2],self.s.enabled)
 def test_project_mesh_survives_portable_roundtrip(self):
  package=self.folder/'input';package.mkdir();(package/'part.obj').write_text('mtllib secret.mtl\nv 0 0 0\nv 0 0 1\nv 0 1 0\nf 1 2 3\n')
  raw=SIMPLE.replace(b'<link name="arm"/>',b'<link name="arm"><visual><geometry><mesh filename="part.obj"/></geometry></visual></link>')
  path=package/'robot.urdf';path.write_bytes(raw);self.s.import_urdf(path);archive=self.folder/'project.zip';self.s.export_project(archive)
  with zipfile.ZipFile(archive) as z:
   self.assertIn('meshes/asset-',z.read('robot.urdf').decode());self.assertNotIn('mtllib',z.read(next(n for n in z.namelist() if n.endswith('.obj'))).decode())
  self.s.import_project(archive);self.assertIn('file://',self.s.visualization_urdf());self.assertTrue(Path(self.s.model['links'][1]['visuals'][0]['mesh']).is_file())


class SixthAxisTests(StudioFixture):
 def test_virtual_j6_move_exclude_and_replay_gate(self):
  self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='home_set'));self.c.action(dict(op='limits',limits=[[-5,5]]*6))
  self.assertTrue(self.c.state()['axes_available'][5]);self.assertEqual(self.c.validate(5,2),2)
  self.c.action(dict(op='joint_enable',axis=5,enabled=False))
  with self.assertRaisesRegex(ValueError,'disabilitato'):self.c.validate(5,1)
  with self.assertRaises(ValueError):self.c.validate_path([dict(axis=5,delta=1)])
 def test_real_j6_requires_profile_and_firmware_capabilities(self):
  self.c.mode='robot';self.c.limits=[[-5,5]]*6
  with self.assertRaisesRegex(ValueError,'driver esterno'):self.c.validate(5,1)
  self.c.configured_axes=6
  with self.assertRaises(ValueError):self.c.validate(5,1)
  self.c.receive('CAPS 6');self.assertEqual(self.c.validate(5,1),1);self.c.write.assert_not_called()
 def test_legacy_five_axis_limits_and_poses_migrate(self):
  self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='limits',limits=[[-5,5]]*5));self.assertEqual(self.c.limits[5],[0,0])
  (self.folder/'axes_enabled.json').write_text(json.dumps([True]*5))
  (self.folder/'sequenza.json').write_text(json.dumps(dict(sequence=[dict(name='legacy',pos=[0]*5,path=[])])))
  with patch.object(server.Controller,'io',lambda c:None):other=server.Controller()
  self.assertEqual(other.sequence[0]['pos'],[0]*6);self.assertTrue(other.axes_enabled[5])
 def test_j6_profile_requires_distinct_available_pins(self):
  p=copy.deepcopy(DEFAULT);p['axes'][5]['active']=True
  with self.assertRaises(ValueError):validate(p)
  p['axes'][5].update(step_pin=42,dir_pin=42)
  with self.assertRaises(ValueError):validate(p)
  p['axes'][5]['dir_pin']=44;self.assertTrue(validate(p)['axes'][5]['active'])
  w=FirmwareWorkspace(self.folder,self.c);w.generate(p);code=w.file('RegiaDemo.ino').read_text();self.assertIn('J6_CONFIGURED = true',code);self.assertIn('J6_STEP_PIN = 42',code);self.assertEqual(self.c.configured_axes,6);self.c.write.assert_not_called()


class EditorProjectTests(StudioFixture):
 def test_manual_actuator_constants_invalidate_matching_profile_until_regenerated(self):
  w=FirmwareWorkspace(self.folder,self.c);source=w.file('RegiaDemo.ino').read_text();source=source.replace('{1600, 1600,','{3200, 1600,',1)
  w.save_file('RegiaDemo.ino',source);self.assertIn('Costanti',w.error);self.assertFalse(self.c.hardware_ok())
  w.generate(DEFAULT);self.assertFalse(w.error);self.assertTrue(self.c.hardware_ok());self.c.write.assert_not_called()
 def test_project_preserves_sequence_and_joint_exclusion(self):
  self.c.sequence=[dict(name='sample',mode='demo',pos=[1,0,0,0,0,2],path=[dict(axis=0,delta=1),dict(axis=5,delta=2)],grip='chiudi',enabled=True,dwell=.5)]
  self.c.axes_enabled[5]=False;archive=self.folder/'project.zip';self.s.export_project(archive)
  self.c.sequence=[];self.c.axes_enabled[5]=True;self.s.import_project(archive)
  self.assertEqual(self.c.sequence[0]['grip'],'chiudi');self.assertEqual(self.c.sequence[0]['pos'][5],2);self.assertFalse(self.c.axes_enabled[5]);self.c.write.assert_not_called()
 def test_excluded_pose_does_not_run_in_block_program(self):
  self.c.action(dict(op='connect',mode='demo'));self.c.action(dict(op='home_set'))
  self.c.sequence=[dict(name='excluded',mode='demo',pos=[1,0,0,0,0,0],path=[dict(axis=0,delta=1)],enabled=False,grip='chiudi',dwell=0)]
  self.s.blocks=self.s.validate_blocks([dict(kind='pose',index=0)])
  with self.assertRaisesRegex(ValueError,'escluse'):self.s.run_program()


class ReferenceModelTests(StudioFixture):
 def test_bundled_model_has_five_arm_axes_all_meshes_and_no_serial_access(self):
  reference=Studio(self.folder,self.c,builtin=True)
  self.assertEqual(len(reference.independent()),5);self.assertEqual(len(reference.mapping),5)
  self.assertEqual(reference.model['reference'],'doc5-presentation');self.assertFalse(reference.model['schematic'])
  self.assertEqual(reference.model['warnings'],[]);self.assertEqual(reference.tip,'tcp_link')
  self.assertTrue(all(Path(v['mesh']).is_file() for link in reference.model['links'] for v in link['visuals']));self.assertFalse(reference.verified);self.c.write.assert_not_called()
 def test_gripper_visual_does_not_consume_j6(self):
  reference=Studio(self.folder,self.c,builtin=True);self.assertNotIn(5,reference.mapping.values());self.c.grip='chiudi';closed=reference.state();self.c.grip='apri';opened=reference.state()
  def matrix(s,name):return next(f['matrix'] for f in s['frames'] if f['name']==name)
  self.assertNotEqual(matrix(closed,'lab_finger_1'),matrix(opened,'lab_finger_1'));self.assertEqual(self.c.pos,[0]*6);self.c.write.assert_not_called()
 def test_reference_portable_roundtrip_keeps_home_calibration(self):
  reference=Studio(self.folder,self.c,builtin=True);archive=self.folder/'reference.zip';reference.export_project(archive);offset=reference.calibration['joint_1']['offset'];reference.import_project(archive)
  self.assertEqual(reference.calibration['joint_1']['offset'],offset);self.assertTrue(all(Path(v['mesh']).is_file() for link in reference.model['links'] for v in link['visuals']));self.assertFalse(reference.verified)

if __name__=='__main__':unittest.main()
