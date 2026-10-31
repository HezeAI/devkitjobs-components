"""Reproduce the immutable Clang r2 package even after the obsolete r1 ZIP is removed.
Uses the unchanged base files retained inside r2, the public r1 descriptor and
hash-locked official .deb inputs. No compiler, Ubuntu or account files required.
"""
from pathlib import Path
import argparse,hashlib,json,zipfile,shutil,subprocess,sys,io,tarfile,urllib.request,tempfile
SOURCE=Path(__file__).resolve().parent
R2_SHA='368bfc822fb6be9e622e3b9b9213ca313804c7c3f5c98502ef2c484b741f38cd'
def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--inputs',type=Path,help='Optional cache of the locked .deb files');a=p.parse_args()
 assert sha(a.archive)==R2_SHA,'Published r2 archive mismatch';a.out.mkdir(parents=True,exist_ok=True)
 work=a.out/'build-tree';work.mkdir(exist_ok=True);out=work/'build/components';out.mkdir(parents=True,exist_ok=True)
 base=json.loads((SOURCE/'clang-base-r1.json').read_text());archive=out/base['archive']['url'].split('/')[-1]
 with zipfile.ZipFile(a.archive)as released,zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for name,meta in base['files'].items():
   data=released.read(name);assert len(data)==meta['bytes']and hashlib.sha256(data).hexdigest()==meta['sha256']
   info=zipfile.ZipInfo(name,date_time=(2026,10,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(0o100755 if meta.get('executable')else 0o100644)<<16;z.writestr(info,data)
 assert sha(archive)==base['archive']['sha256'],'Base input could not be reproduced exactly'
 inputs=json.loads((SOURCE/'clang-package-inputs.json').read_text());target=out/'adaptation-inputs';target.mkdir(exist_ok=True);(target/'package-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');raw=target/'sysroot-source';raw.mkdir(exist_ok=True)
 for row in inputs:
  name=Path(row['Filename']).name;package=target/name;cached=a.inputs/name if a.inputs else None
  if cached and cached.is_file():shutil.copyfile(cached,package)
  elif not package.is_file():
   with urllib.request.urlopen('https://packages.termux.dev/apt/termux-main/'+row['Filename'],timeout=45)as f,package.open('wb')as t:shutil.copyfileobj(f,t)
  assert sha(package)==row['SHA256'],'Official input hash mismatch'
  b=package.read_bytes();offset=8
  while offset<len(b):
   header=b[offset:offset+60];size=int(header[48:58]);part=b[offset+60:offset+60+size];offset+=60+size+size%2
   if header[:16].strip().startswith(b'data.tar'):
    with tarfile.open(fileobj=io.BytesIO(part))as t:
     for entry in t.getmembers():
      name=entry.name.removeprefix('./data/data/com.termux/files/usr/').removeprefix('data/data/com.termux/files/usr/')
      path=Path(name)
      if entry.isfile()and not path.is_absolute()and '..'not in path.parts and (name.startswith(('include/','lib/'))or name=='bin/lld'):
       dest=raw/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(t.extractfile(entry).read())
 for dest,src in [('build-support/prepare_clang_component.py','prepare_clang_component.py'),('build-support/prepare_components.py','prepare_components.py'),('.verification/components-github/sources/prepare_runtime.py','prepare_runtime.py')]:
  path=work/dest;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SOURCE/src,path)
 config=work/'source/app/src/main/assets/tools-catalog.json';config.parent.mkdir(parents=True,exist_ok=True);config.write_text(json.dumps({'components':{'clang':base}}))
 subprocess.run([sys.executable,work/'build-support/prepare_clang_component.py'],check=True)
 result=out/'clang-21-r2-android-arm64.zip';assert sha(result)==R2_SHA,'Rebuilt r2 differs'
 receipt={'status':'passed','publishedSha256':R2_SHA,'reproducedBaseSha256':sha(archive),'bytes':result.stat().st_size,'packageReproductionOnly':True,'upstreamLlvmRebuild':False};(a.out/'REPRODUCIBILITY.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
