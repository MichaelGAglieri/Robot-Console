#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Maintainer tool: reproduce the five-axis presentation geometry as local URDF/STL.
Usage: python3 scripts/import_doc_reference.py /path/to/presentazione-linuxday
No download, controller connection or physical calibration is performed.
"""
import argparse,base64,hashlib,json,math,struct,xml.etree.ElementTree as ET
from pathlib import Path

def main():
 parser=argparse.ArgumentParser();parser.add_argument('presentation',type=Path);args=parser.parse_args()
 source=args.presentation/'assets/models';packed=source/'ur3e-model.js';text=packed.read_text();data=json.loads(text[text.index('{'):text.rindex('}')+1])
 out=Path(__file__).resolve().parents[1]/'models/doc5';meshes=out/'meshes';meshes.mkdir(parents=True,exist_ok=True)
 root=ET.parse(source/'ur3e_doc.urdf').getroot();root.set('name','DOC · modello illustrativo 5 DOF')
 mapping={name:'joint_'+str(i+1) for i,name in enumerate(data['armJoints'])}
 def color(key,c):
  lime=[.40,.88,.012];black=[.018,.022,.018]
  if c[1]>.8 and c[2]<.05:return lime
  if '/base.dae' in key and c[0]>.1:return lime
  if '/visual/' in key:return lime if c[0]>.7 else black
  if key in ('doc_lab_gripper-0.stl','doc_lab_gripper-3.stl') or key.startswith('lab_finger_') and key.endswith('-2.stl'):return lime
  if key in ['doc_lab_gripper-'+str(i)+'.stl' for i in range(4,10)]:return c
  return black
 assets={}
 for index,(key,groups) in enumerate(data['meshes'].items()):
  assets[key]=[]
  for part,group in enumerate(groups):
   vb=base64.b64decode(group['vertices']);ib=base64.b64decode(group['indices']);vertices=struct.unpack('<'+'f'*(len(vb)//4),vb);kind='I' if group['index32'] else 'H';width=4 if group['index32'] else 2;indices=struct.unpack('<'+kind*(len(ib)//width),ib)
   name=f'mesh-{index:02d}-{part:02d}.stl';target=meshes/name
   with target.open('wb') as f:
    f.write(b'DOC presentation geometry; attribution in NOTICE.md'.ljust(80,b' '));f.write(struct.pack('<I',len(indices)//3))
    for i in range(0,len(indices),3):
     face=[vertices[indices[i+j]*6:indices[i+j]*6+3] for j in range(3)];u=[face[1][k]-face[0][k] for k in range(3)];v=[face[2][k]-face[0][k] for k in range(3)];n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];norm=math.sqrt(sum(x*x for x in n)) or 1
     f.write(struct.pack('<12fH',*[x/norm for x in n],*[x for p in face for x in p],0))
   assets[key].append((name,color(key,group['color'])))
 for link in root.findall('link'):
  # Visualization only: do not redistribute uncalibrated UR3e dynamics as DOC data.
  for old in list(link):
   if old.tag in ('visual','collision','inertial'):link.remove(old)
  for visual in data['links'].get(link.get('name'),[]):
   for name,c in assets[visual['mesh']]:
    v=ET.SubElement(link,'visual');ET.SubElement(v,'origin',xyz=' '.join(map(str,visual['origin']['xyz'])),rpy=' '.join(map(str,visual['origin']['rpy'])));g=ET.SubElement(v,'geometry');ET.SubElement(g,'mesh',filename='meshes/'+name,scale=' '.join(map(str,visual['scale'])));m=ET.SubElement(v,'material',name='doc_'+name);ET.SubElement(m,'color',rgba=' '.join(map(str,c+[1])))
 fingers=[]
 for joint in root.findall('joint'):
  name=joint.get('name')
  if name in mapping:joint.set('name',mapping[name])
  elif name.startswith('lab_finger_'):
   fingers.append(name);ET.SubElement(joint,'mimic',joint='joint_5',multiplier='0',offset='0')
 ET.SubElement(root,'robot_console',reference='doc5-presentation',tip='tcp_link',gripper_joints=' '.join(fingers),gripper_travel=str(data['gripper']['previewTravel']),nominal_home=' '.join(map(str,data['poses']['home'])))
 ET.indent(root,space='  ');ET.ElementTree(root).write(out/'doc5.urdf',encoding='utf-8',xml_declaration=True)
 manifest=dict(source='DOC presentation/Webots five-axis UR3e adaptation',source_sha256=hashlib.sha256(packed.read_bytes()).hexdigest(),upstream='https://github.com/UniversalRobots/Universal_Robots_ROS2_Description',license='UR3e geometry BSD-3-Clause; DOC gripper/integration GPL-3.0-only',note='Illustrative model; not calibrated physical EB-15 CAD.',arm_dof=5,meshes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in meshes.glob('*.stl')})
 (out/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Exported',len(manifest['meshes']),'STL assets; five arm DOF, gripper visual only.')
if __name__=='__main__':main()
