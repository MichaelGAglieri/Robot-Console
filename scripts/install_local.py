#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Install locally with verified rollback; retain current and previous app generations.
No network, serial access, firmware upload or app launch. Older backups go to Trash.
"""
import argparse,json,os,plistlib,shutil,subprocess,uuid,zipfile
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def info(app):
 if app.is_symlink() or not app.is_dir():raise ValueError('Expected a real application folder: '+str(app))
 data=plistlib.loads((app/'Contents/Info.plist').read_bytes())
 if data.get('CFBundleIdentifier')!='it.doc.regia':raise ValueError('Unexpected app identity: '+str(app))
 version=data['CFBundleShortVersionString'];build=data['CFBundleVersion']
 return tuple(int(v) for v in version.split('.'))+(int(build),),version,build

def verify(app):
 info(app);subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True,capture_output=True)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--source',type=Path,default=ROOT/'Robot Console.app')
 parser.add_argument('--target',type=Path,default=Path('/Applications/Robot Console.app'))
 parser.add_argument('--history',type=Path,default=ROOT/'build/local-history')
 parser.add_argument('--apply',action='store_true')
 args=parser.parse_args();source=args.source.absolute();target=args.target.absolute();history=args.history.absolute()
 if source==target or history==target or history.is_relative_to(target) or source.is_relative_to(history):raise ValueError('Invalid installation paths.')
 new=info(source);verify(source);old=info(target) if target.exists() else None
 if old and new[0]<old[0]:raise ValueError('Refusing an accidental downgrade.')
 plan=dict(current=str(target),version=new[1],build=new[2],history=str(history),retention='current + immediately previous app; data backups retained separately')
 print(json.dumps(plan,indent=2))
 if not args.apply:return
 # Refuse to replace a running app, including the development copy. Never stop hardware here.
 processes=subprocess.run(['/bin/ps','-axo','command='],check=True,capture_output=True,text=True).stdout
 for path in (source,target):
  if str(path/'Contents/MacOS/DOCRegia') in processes:raise ValueError('Quit Robot Console before installing.')
 history.mkdir(parents=True,exist_ok=True)
 backups=[]
 for app in history.glob('*.app'):
  record=info(app);verify(app);backups.append((record[0],app))
 previous=None
 if old and old[0]!=new[0]:
  previous=history/f'Robot Console {old[1]} build{old[2]}.app'
  if previous.exists():
   verify(previous)
   if info(previous)[0]!=old[0]:raise ValueError('Conflicting backup.')
  else:
   subprocess.run(['/usr/bin/ditto',str(target),str(previous)],check=True);verify(previous)
 elif backups:
  candidates=[entry for entry in backups if entry[0]<new[0]]
  if candidates:previous=max(candidates,key=lambda entry:entry[0])[1]
 # A local recovery snapshot precedes any application replacement. It is never published.
 data=Path.home()/'Library/Application Support/DOC Regia'
 stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
 if data.is_dir():
  archive=history/f'RobotConsole-dati-prima-build{new[2]}-{stamp}.zip'
  with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as zipped:
   for path in sorted(data.rglob('*')):
    if path.is_file() and not path.is_symlink():zipped.write(path,str(Path('DOC Regia')/path.relative_to(data)))
  with zipfile.ZipFile(archive) as zipped:
   if zipped.testzip():raise ValueError('Data recovery archive failed verification.')
 stage=target.with_name('.Robot Console staged-'+uuid.uuid4().hex+'.app')
 rollback=target.with_name('.Robot Console rollback-'+uuid.uuid4().hex+'.app')
 subprocess.run(['/usr/bin/ditto',str(source),str(stage)],check=True);verify(stage)
 if target.exists():target.rename(rollback)
 try:
  stage.rename(target);verify(target)
 except Exception:
  if target.exists():target.rename(stage)
  if rollback.exists():rollback.rename(target)
  raise
 trash=Path.home()/'.Trash'/('Robot Console versioni precedenti '+stamp+'-'+uuid.uuid4().hex[:6]);trash.mkdir(parents=True)
 moved=[]
 # All removals are recoverable, and only real Robot Console bundles are eligible.
 obsolete=[p for p in history.glob('*.app') if p!=previous]
 if rollback.exists():obsolete.append(rollback)
 for app in obsolete:
  verify(app);destination=trash/app.name;app.rename(destination);moved.append(dict(original=str(app),trash=str(destination)))
 plan.update(previous=str(previous) if previous else None,moved=moved,installed_at=stamp)
 (history/'last_install.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
 print('Installed and signature verified. Retained previous:',previous)
if __name__=='__main__':main()
