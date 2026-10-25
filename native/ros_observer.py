# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Read-only lab observer; publishes Regia telemetry, never robot commands."""
import json, sys
from pathlib import Path
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class Observer(Node):
 def __init__(self,path):
  super().__init__('doc_regia_observer')
  self.path=Path(path)
  self.subs=[self.create_subscription(String,topic,lambda msg,t=topic:self.event(t,msg.data),10) for topic in ('/laboratorio/stato','/laboratorio/esito','/laboratorio/risposta','/laboratorio/missione')]
  self.pub=self.create_publisher(String,'/doc_regia/stato',10)
  self.create_timer(1,self.publish)
  self.event('bridge','ROS 2 connesso · osservazione laboratorio')
 def event(self,topic,text):
  print(json.dumps(dict(topic=topic,text=text[:12000])),flush=True)
 def publish(self):
  try:
   data=self.path.read_text()
   json.loads(data)
   self.pub.publish(String(data=data))
  except (OSError,ValueError):pass

def main():
 rclpy.init()
 node=Observer(sys.argv[1])
 try:rclpy.spin(node)
 finally:node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
