"""Reproducible Android component packaging, not a C++/Emscripten rebuild.
SPDX-License-Identifier: GPL-3.0-or-later
Only hash-locked public inputs and files inside this source directory are read.
"""
from pathlib import Path
import argparse,hashlib,json,struct,urllib.request,zipfile
R=Path(__file__).resolve().parent
LOCK=json.loads((R/'upstream.lock.json').read_text())
def sha(data):return hashlib.sha256(data).hexdigest()
def launcher():
 strings=[b'/system/bin/sh\0',b'-c\0',b': "${DEVKIT_BIN:?DevKit native runtime required}"; exec "$DEVKIT_BIN/node" "${0%/*}/../runtime/run.cjs" "$@"\0']
 words=[0xf94003e4,0x910043e2,0x8b040c42,0,0,0,0xd10043ff,0xf90003e0,0xf90007e5,0xf9000be6,0x910003e1,0xd2801ba8,0xd4000001,0xd2800fe0,0xd2800ba8,0xd4000001]
 offset=4096+4*len(words)
 for i,reg in enumerate([0,5,6]):
  delta=offset-(4096+4*(i+3));assert -(1<<20)<=delta<(1<<20)
  words[i+3]=0x10000000|((delta&3)<<29)|(((delta>>2)&0x7ffff)<<5)|reg;offset+=len(strings[i])
 code=struct.pack('<'+'I'*len(words),*words)+b''.join(strings);size=4096+len(code);base=0x400000
 header=struct.pack('<16sHHIQQQIHHHHHH',b'\x7fELF\x02\x01\x01'+b'\0'*9,2,183,1,base+4096,64,0,0,64,56,2,0,0,0)
 load=struct.pack('<IIQQQQQQ',1,5,0,base,base,size,size,4096);stack=struct.pack('<IIQQQQQQ',0x6474e551,6,0,0,0,0,0,16)
 return (header+load+stack).ljust(4096,b'\0')+code

def build(upstream,out):
 data=upstream.read_bytes();expected=LOCK['upstream'];assert len(data)==expected['bytes'] and sha(data)==expected['sha256'],'Upstream integrity mismatch'
 with zipfile.ZipFile(upstream) as z:
  assert z.testzip() is None and z.namelist()==['openscad.js'],'Unexpected upstream archive'
  js=z.read('openscad.js');assert sha(js)==expected['jsSha256']
 payload={'bin/openscad':launcher(),'runtime/openscad.js':js,'runtime/run.cjs':(R/'run.cjs').read_bytes()}
 for p in sorted(R.iterdir()):
  if p.suffix in ['.py','.S','.json','.md'] or p.name=='run.cjs':payload['sources/'+p.name]=p.read_bytes()
 for p in sorted((R/'licenses').glob('*')):
  content=p.read_bytes();assert len(content)>100,'Empty/truncated license: '+p.name
  payload['licenses/'+p.name]=content
 assert 'licenses/GPL-3.0.txt' in payload and 'sources/SOURCE-OFFER.md' in payload,'Missing license/source information'
 provenance={**LOCK,'engine':'Official unmodified OpenSCAD JS/WASM included in package','launcher':'Portable static Android ARM64 syscall launcher → system sh → builtin Node','gui':False,'reproducibleScope':'DevKit package and launcher; upstream WASM SHA-pinned, not rebuilt locally'}
 payload['PROVENANCE.json']=(json.dumps(provenance,sort_keys=True,indent=2)+'\n').encode()
 files={n:{'sha256':sha(b),'bytes':len(b),'executable':n=='bin/openscad'}for n,b in sorted(payload.items())}
 out.mkdir(parents=True,exist_ok=True);name='openscad-'+LOCK['version']+'-android-arm64.zip';archive=out/name
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,b in sorted(payload.items()):
   info=zipfile.ZipInfo(n,date_time=(2026,10,31,0,0,0));info.create_system=3;info.external_attr=(0o100755 if n=='bin/openscad' else 0o100644)<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,b,compresslevel=9)
 descriptor={'id':'openscad','version':LOCK['version'],'title':'OpenSCAD CLI (official WASM, native ARM64 Node)','platform':'android','abi':'arm64-v8a','minAndroidApi':29,'source':'https://openscad.org/downloads.html','license':LOCK['distributionLicense'],'commands':{'openscad':{'path':'bin/openscad','probe':['--devkit-self-test'],'expect':'OpenSCAD functional checks passed'}},'dependencies':{},'runtimeRequirements':{'builtinNode':'26.12.1','architecture':'arm64','environment':['DEVKIT_BIN']},'archive':{'url':'https://github.com/HezeAI/devkitjobs-components/releases/download/'+LOCK['releaseTag']+'/'+name,'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes())},'files':files,'links':{},'provenance':provenance}
 (out/'openscad.json').write_text(json.dumps(descriptor,indent=2)+'\n');print(json.dumps({'archive':name,'sha256':descriptor['archive']['sha256'],'bytes':descriptor['archive']['bytes']}));return descriptor
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--upstream',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 upstream=a.upstream
 if upstream is None:
  a.out.mkdir(parents=True,exist_ok=True);upstream=a.out/'upstream.zip'
  with urllib.request.urlopen(LOCK['upstream']['url'],timeout=40)as f:upstream.write_bytes(f.read(LOCK['upstream']['bytes']+1))
 build(upstream,a.out)
