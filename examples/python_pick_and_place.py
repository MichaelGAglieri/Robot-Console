#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The same blocks as the native Program panel. No hardware connection/limits/HOME setup.
Run from the repository: PYTHONPATH=. python3 examples/python_pick_and_place.py --url URL
Read the session token from ROBOT_CONSOLE_TOKEN (or hidden prompt), not command history.
"""
import argparse, getpass, os
from robot_console_client import RobotConsole

def program(targets, output=None):
    piece, drop=targets['Pezzo'],targets['Deposito']
    blocks=[dict(kind='movej',name='Sopra il pezzo',to='target',target=piece,offset=[0,0,60]),
            dict(kind='movel',name='Scendi',to='target',target=piece,speed=50),
            dict(kind='grip',name='Chiudi',command='chiudi'),
            dict(kind='movel',name='Risali',to='target',target=piece,offset=[0,0,60],speed=50),
            dict(kind='movej',name='Sopra il deposito',to='target',target=drop,offset=[0,0,60]),
            dict(kind='movel',name='Appoggia',to='target',target=drop,speed=50),
            dict(kind='grip',name='Apri',command='apri'),
            dict(kind='movel',name='Allontanati',to='target',target=drop,offset=[0,0,60])]
    if output:blocks.append(dict(kind='output',name='Deposito completato',output=output,output_value=True,timeout=2))
    blocks.append(dict(kind='movej',name='HOME',to='home'))
    return blocks

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--url',required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--output');args=parser.parse_args()
    client=RobotConsole(args.url,os.environ.get('ROBOT_CONSOLE_TOKEN') or getpass.getpass('Token API: '))
    state=client.state();targets={t['name']:t['id'] for t in state['studio']['cartesian_targets']}
    if any(n not in targets for n in ('Pezzo','Deposito')):parser.error('Crea nell’app i target Pezzo e Deposito prima dello script.')
    plan=client.plan(program(targets,args.output));print('Piano:',plan['id'],'rami:',plan['program']['branches'],'stimati:',round(plan['duration'],2),'s; massimo con I/O:',round(plan['duration_max'],2),'s')
    if not args.execute:return
    run=client.execute(plan,'Presa e deposito da Python')
    if run['status']=='awaiting_operator':print('Conferma il piano nell’app per procedere sul robot reale.')
    try:
        result=client.wait(run,timeout=600);print('Completato:',round(result['measured_seconds'],2),'s misurati contro',round(plan['duration'],2),'s stimati.')
    except Exception:
        client.stop();raise
if __name__=='__main__':main()
