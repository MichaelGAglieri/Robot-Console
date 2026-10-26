#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Package the built app and exact Git sources, without local user data."""
import argparse,hashlib,plistlib,re,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=root/'build/release');args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
app=root/'Robot Console.app';info=plistlib.loads((app/'Contents/Info.plist').read_bytes());version=info['CFBundleShortVersionString'];assert re.fullmatch(r'\d+\.\d+\.\d+',version) and info['CFBundleIdentifier']=='it.doc.regia'
subprocess.run(['/usr/bin/codesign','--verify','--strict',str(app)],check=True)
app_zip=out/f'Robot-Console-{version}-macOS-AppleSilicon.zip';source_zip=out/f'Robot-Console-{version}-sources.zip'
subprocess.run(['/usr/bin/ditto','-c','-k','--keepParent',str(app),str(app_zip)],check=True)
subprocess.run(['git','archive','--format=zip',f'--prefix=Robot-Console-{version}/','-o',str(source_zip),'HEAD'],cwd=root,check=True)
(out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (app_zip,source_zip)))
print('Packaged version',version,'at',out)
