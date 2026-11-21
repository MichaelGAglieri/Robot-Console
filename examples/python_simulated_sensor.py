#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Publish a simulated input for Anteprima only. Never claims measured hardware data."""
import argparse,getpass,os,time
from robot_console_client import RobotConsole,Adapter
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',required=True);p.add_argument('--name',default='presente');args=p.parse_args()
c=RobotConsole(args.url,os.environ.get('ROBOT_CONSOLE_TOKEN') or getpass.getpass('Token API: '))
with Adapter(c,'Esempio simulato',inputs=[args.name],simulated=True) as adapter:
    try:
        while True:adapter.publish(args.name,1);time.sleep(.2)
    except KeyboardInterrupt:pass
