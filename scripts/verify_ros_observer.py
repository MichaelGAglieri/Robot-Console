#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Optional ROS 2 loopback probe. Run with a prepared RoboStack Python. No USB."""
import json,os,sys,tempfile,threading,time,queue,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
os.environ['ROS_DOMAIN_ID']='99';os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE']='LOCALHOST';os.environ.pop('ROS_LOCALHOST_ONLY',None)
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from tf2_msgs.msg import TFMessage
from robot_model import default_urdf,parse_urdf
with tempfile.TemporaryDirectory(prefix='robot-console-ros-check-') as directory:
 path=Path(directory)/'state.json';model=parse_urdf(default_urdf());values={j['name']:.1 for j in model['joints']}
 payload=dict(mode='demo',connected=False,pos=[0]*5)
 path.write_text(json.dumps(dict(console=payload,visualization=dict(model=model,positions=values,prefix='robot_console/',urdf=default_urdf().decode()))))
 process=subprocess.Popen([sys.executable,str(root/'native/ros_observer.py'),str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy())
 events=queue.Queue()
 def read():
  for line in process.stdout:
   try:events.put(json.loads(line))
   except ValueError:pass
 threading.Thread(target=read,daemon=True).start();rclpy.init();node=Node('robot_console_isolated_probe');received={};seen=set();health=False
 topics=('/laboratorio/stato','/laboratorio/esito','/laboratorio/risposta','/laboratorio/missione')
 subs=[node.create_subscription(String,'/doc_regia/stato',lambda m:received.update(console=json.loads(m.data)),10),node.create_subscription(JointState,'/robot_console/joint_states',lambda m:received.update(joints=m),10),node.create_subscription(TFMessage,'/tf',lambda m:received.update(tf=m),10),node.create_subscription(String,'/robot_console/robot_description',lambda m:received.update(urdf=m.data),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))]
 pubs=[node.create_publisher(String,t,10) for t in topics]
 try:
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   if process.poll() is not None:raise RuntimeError(process.stderr.read())
   for pub in pubs:pub.publish(String(data='isolated probe'))
   rclpy.spin_once(node,timeout_sec=.1)
   while not events.empty():
    event=events.get_nowait()
    if event.get('text')=='isolated probe':seen.add(event['topic'])
    if 'health' in event:health=not event['health']['error'] and 'robot_console_isolated_probe' in event['health']['nodes']
   if seen==set(topics) and len(received)==4 and health:break
  assert seen==set(topics),seen
  assert received.get('console')==payload,received
  assert received.get('urdf')==default_urdf().decode()
  assert len(received['joints'].name)==5 and all(abs(v-.1)<1e-8 for v in received['joints'].position)
  assert len(received['tf'].transforms)==5 and all(t.child_frame_id.startswith('robot_console/') for t in received['tf'].transforms)
  assert health
  print('PASS: four lab topics, console state, URDF, five JointState/TF transforms and health; domain 99, no hardware.')
 finally:
  node.destroy_node();rclpy.shutdown();process.terminate()
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:process.kill();process.wait()
  process.stdout.close();process.stderr.close()
