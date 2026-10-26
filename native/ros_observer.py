# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Read-only observer plus namespaced visualization. Never publishes commands."""
import json, math, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage
from robot_model import frames

def quaternion(r):
 trace=r[0][0]+r[1][1]+r[2][2]
 if trace>0:
  s=math.sqrt(trace+1)*2;return [(r[2][1]-r[1][2])/s,(r[0][2]-r[2][0])/s,(r[1][0]-r[0][1])/s,s/4]
 i=max(range(3),key=lambda k:r[k][k]);j=(i+1)%3;k=(i+2)%3;s=math.sqrt(max(1e-15,1+r[i][i]-r[j][j]-r[k][k]))*2
 q=[0.,0.,0.,0.];q[i]=s/4;q[j]=(r[j][i]+r[i][j])/s;q[k]=(r[k][i]+r[i][k])/s;q[3]=(r[k][j]-r[j][k])/s;return q

class Observer(Node):
 def __init__(self,path):
  super().__init__('robot_console_observer');self.path=Path(path);self.seen={};self.description='';self.last_error=''
  self.subs=[self.create_subscription(String,topic,lambda msg,t=topic:self.event(t,msg.data),10) for topic in ('/laboratorio/stato','/laboratorio/esito','/laboratorio/risposta','/laboratorio/missione')]
  self.pub=self.create_publisher(String,'/doc_regia/stato',10)
  self.joints=self.create_publisher(JointState,'/robot_console/joint_states',10);self.transforms=self.create_publisher(TFMessage,'/tf',10)
  self.robot_description=self.create_publisher(String,'/robot_console/robot_description',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
  self.create_timer(.1,self.publish);self.create_timer(1,self.health)
  self.event('bridge','Osservatore avviato; in attesa dei dati del laboratorio.')
 def event(self,topic,text):
  self.seen[topic]=time.time();print(json.dumps(dict(topic=topic,text=text[:12000])),flush=True)
 def health(self):
  try:nodes=sorted(name for name,_ in self.get_node_names_and_namespaces())
  except Exception:nodes=[]
  print(json.dumps(dict(health=dict(time=time.time(),topics=self.seen,nodes=nodes,error=self.last_error))),flush=True)
 def publish(self):
  try:
   data=json.loads(self.path.read_text());self.pub.publish(String(data=json.dumps(data.get('console',data))))
   preview=data.get('visualization')
   if not preview:return
   model=preview['model'];positions=preview['positions'];prefix=preview.get('prefix','robot_console/');stamp=self.get_clock().now().to_msg()
   if preview['urdf']!=self.description:self.description=preview['urdf'];self.robot_description.publish(String(data=self.description))
   msg=JointState();msg.header.stamp=stamp;msg.header.frame_id=prefix+model['root'];msg.name=list(positions);msg.position=[float(positions[name]) for name in msg.name];self.joints.publish(msg)
   world=frames(model,{**positions,'__gripper':preview.get('gripper',0)});transforms=[]
   for joint in model['joints']:
    a=world[joint['parent']];b=world[joint['child']]
    rotation=[[sum(a[k][i]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    xyz=[sum(a[k][i]*(b[k][3]-a[k][3]) for k in range(3)) for i in range(3)]
    q=quaternion(rotation);t=TransformStamped();t.header.stamp=stamp;t.header.frame_id=prefix+joint['parent'];t.child_frame_id=prefix+joint['child']
    t.transform.translation.x,t.transform.translation.y,t.transform.translation.z=xyz
    t.transform.rotation.x,t.transform.rotation.y,t.transform.rotation.z,t.transform.rotation.w=q;transforms.append(t)
   self.transforms.publish(TFMessage(transforms=transforms));self.last_error=''
  except (OSError,ValueError,KeyError,TypeError) as error:self.last_error=str(error)[:300]

def main():
 rclpy.init();node=Observer(sys.argv[1])
 try:rclpy.spin(node)
 finally:node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
