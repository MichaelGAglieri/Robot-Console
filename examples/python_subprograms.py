#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Reusable pick/place functions. Plans only unless --execute is explicitly supplied.
Create Pezzo and Deposito targets in the native app first. No USB/HOME/limit setup here.
PYTHONPATH=. python3 examples/python_subprograms.py --url URL [--execute]
"""
import argparse
import getpass
import os
from robot_console_client import RobotConsole


def program(targets):
    def approach(name, target, command):
        return [dict(kind='function', name='Funzione '+name, function=name, parameters=['quota']),
                dict(kind='movej', name='Avvicinati', to='target', target=target, offset_expr=['','','quota']),
                dict(kind='movel', name='Scendi', to='target', target=target, speed=50),
                dict(kind='grip', name=command, command=command),
                dict(kind='movel', name='Risali', to='target', target=target, offset_expr=['','','quota'], speed=50),
                dict(kind='end', name='Fine funzione')]
    return (approach('prendi', targets['Pezzo'], 'chiudi')+
            approach('deposita', targets['Deposito'], 'apri')+
            [dict(kind='call', name='Prendi a 60 mm', function='prendi', arguments={'quota':'60'}),
             dict(kind='call', name='Deposita a 60 mm', function='deposita', arguments={'quota':'60'}),
             dict(kind='movej', name='HOME', to='home')])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    client=RobotConsole(args.url, os.environ.get('ROBOT_CONSOLE_TOKEN') or getpass.getpass('Token API: '))
    targets={t['name']:t['id'] for t in client.state()['studio']['cartesian_targets']}
    if any(n not in targets for n in ('Pezzo','Deposito')):parser.error('Crea prima i target Pezzo e Deposito nell’app.')
    plan=client.plan(program(targets))
    print('Piano con funzioni:',plan['id'],'rami:',plan['program']['branches'],'stimati:',round(plan['duration'],2),'s')
    if not args.execute:return
    run=client.execute(plan,'Presa e deposito con sottoprogrammi')
    if run['status']=='awaiting_operator':print('Conferma il piano nell’app per procedere sul robot reale.')
    try:
        result=client.wait(run,timeout=600)
        print('Completato:',round(result['measured_seconds'],2),'s misurati.')
    except Exception:
        client.stop();raise
if __name__=='__main__':main()
