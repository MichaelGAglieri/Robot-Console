#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""CI-only release publication after tests/build, using the scoped Actions token.
No credentials are stored or printed. The release stays a draft until all assets
have uploaded successfully. Already published versions are never overwritten.
"""
import hashlib,json,os,plistlib,re,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1];version=plistlib.loads((root/'native/Info.plist').read_bytes())['CFBundleShortVersionString'];assert re.fullmatch(r'\d+\.\d+\.\d+',version)
repo=os.environ['GITHUB_REPOSITORY'];assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo)
token=os.environ['GH_TOKEN'];commit=os.environ['GITHUB_SHA'];assert re.fullmatch(r'[0-9a-f]{40}',commit)
base='https://api.github.com/repos/'+repo;headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Robot-Console-release'}
def request(method,url,data=None,content_type='application/json'):
 raw=data if isinstance(data,bytes) else (json.dumps(data).encode() if data is not None else None)
 req=urllib.request.Request(url,data=raw,headers={**headers,'Content-Type':content_type},method=method)
 with urllib.request.urlopen(req,timeout=180) as response:
  payload=response.read();return json.loads(payload) if payload else None
try:release=request('GET',base+'/releases/tags/v'+version)
except urllib.error.HTTPError as error:
 if error.code!=404:raise
 release=None
if release and not release['draft']:raise SystemExit('Version already published; refusing to overwrite it.')
notes=(root/'docs/RELEASE_2_0.md').read_text()
if not release:release=request('POST',base+'/releases',dict(tag_name='v'+version,target_commitish=commit,name='Robot Console '+version+' · Studio',body=notes,draft=True,prerelease=False))
assets=root/'build/release';expected=[f'Robot-Console-{version}-macOS-AppleSilicon.zip',f'Robot-Console-{version}-sources.zip','SHA256SUMS.txt'];assert all((assets/name).is_file() for name in expected)
for existing in release.get('assets',[]):
 if existing['name'] in expected:request('DELETE',base+'/releases/assets/'+str(existing['id']))
for name in expected:
 data=(assets/name).read_bytes();asset=request('POST',release['upload_url'].split('{')[0]+'?name='+name,data,'application/octet-stream')
 assert asset['size']==len(data)
 if asset.get('digest'):assert asset['digest']=='sha256:'+hashlib.sha256(data).hexdigest()
 print('Uploaded',name,len(data),'bytes',flush=True)
release=request('PATCH',base+'/releases/'+str(release['id']),dict(draft=False,make_latest='true'))
print('Published',release['html_url'],flush=True)
