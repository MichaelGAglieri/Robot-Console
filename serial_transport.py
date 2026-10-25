# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Exclusive access to a user-selected macOS serial port; never selects a port."""
import fcntl, os, subprocess, termios

def ensure_port_available(port):
 # Check both names of the same macOS tty device, before opening/resetting it.
 aliases=[port]
 if port.startswith('/dev/cu.'):aliases.append('/dev/tty.'+port[8:])
 aliases=[p for p in aliases if os.path.exists(p)]
 if not aliases:raise ValueError('Porta USB non più presente: seleziona la porta attuale della Mega.')
 try:
  result=subprocess.run(['/usr/sbin/lsof','-Fpc','--',*aliases],capture_output=True,text=True,timeout=3)
 except (OSError,subprocess.TimeoutExpired) as e:raise ValueError('Impossibile verificare se la porta USB è libera.') from e
 if result.returncode not in (0,1) or (result.returncode==1 and result.stderr.strip()):raise ValueError('Impossibile verificare l’accesso alla porta USB: '+result.stderr.strip()[:200])
 pid=None;owners=[]
 for line in result.stdout.splitlines():
  if line.startswith('p'):
   try:pid=int(line[1:])
   except ValueError:pid=None
  elif line.startswith('c') and pid is not None and pid!=os.getpid():owners.append(line[1:]+' (PID '+str(pid)+')')
 if owners:raise ValueError('Porta USB occupata da '+', '.join(owners)+'. Chiudi il monitor seriale di Arduino o l’altro programma, poi riprova.')

def claim_exclusive(fd):
 try:fcntl.ioctl(fd,termios.TIOCEXCL)
 except OSError as e:raise ValueError('Impossibile ottenere l’accesso esclusivo alla porta USB.') from e
