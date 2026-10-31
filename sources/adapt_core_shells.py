"""Deterministic, same-size ELF patches for confirmed Android shell defaults.

Never modify installed executables. Fail closed if upstream bytes change.
Python source is patched separately while repacking the public runtime archive.
"""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1]
O=R.parent/'devkit-source/DevKitJobs-Source-0.1.5'
OLD=b'/data/data/com.termux/files/usr/bin/sh'
NEW=b'/system/bin/sh'

def patch(name,old,new):
 source=O/'app/src/main/jniLibs/arm64-v8a'/name
 data=source.read_bytes();count=data.count(old)
 if count!=1:raise ValueError(f'{name}: expected exactly one shell default, got {count}')
 if len(new)>len(old):raise ValueError('ELF patch must not grow')
 result=data.replace(old,new)
 if len(result)!=len(data):raise ValueError('ELF size changed')
 target=R/'native-tools/arm64-v8a'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
 target.chmod(0o755)
 return {'sourceSha256':hashlib.sha256(data).hexdigest(),'sha256':hashlib.sha256(result).hexdigest(),'bytes':len(result),'patches':count}

def main():
 manifest=R/'native-runtime-additions.json';value=json.loads(manifest.read_text())
 original=json.loads((O/'app/src/main/assets/runtime-manifest.json').read_text())
 # C string: retain trailing bytes as NUL padding, including the terminator.
 git=patch('libtool_git.so',OLD+b'\0',NEW+b'\0'*(len(OLD)-len(NEW)+1))
 # Embedded JavaScript: pad outside the literal, never insert NUL into JS.
 old=b"file = '"+OLD+b"';";new=b"file = '"+NEW+b"';"
 node=patch('libtool_node.so',old,new+b' '*(len(old)-len(new)))
 for name,info in [('libtool_git.so',git),('libtool_node.so',node)]:
  value['libraries'][name]={**original['libraries'][name],**info,'adaptation':'Android system shell; fixed-length patch; build-support/adapt_core_shells.py'}
 manifest.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'git':git,'node':node},indent=2))
if __name__=='__main__':main()
