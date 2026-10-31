"""Package a complete Android C toolchain from hash-locked public inputs.
No credentials or installed Termux files are read. Native LLVM is reused from
our immutable r1 package, with NDK headers, compiler-rt and Android LLD added.
"""
from pathlib import Path
import ast,hashlib,json,zipfile,struct,re,tarfile,io
from prepare_components import elf_needed
R=Path(__file__).resolve().parents[1];OUT=R/'build/components';INPUT=OUT/'adaptation-inputs';RAW=INPUT/'sysroot-source'
VERSION='21-r2';TAG='native-2026-10-31-r2'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 old=json.loads((R/'source/app/src/main/assets/tools-catalog.json').read_text())['components']['clang']
 source=OUT/old['archive']['url'].split('/')[-1];assert sha(source.read_bytes())==old['archive']['sha256']
 inputs=json.loads((INPUT/'package-inputs.json').read_text())
 for item in inputs:assert sha((INPUT/Path(item['Filename']).name).read_bytes())==item['SHA256']
 with zipfile.ZipFile(source)as z:files={n:z.read(n)for n in z.namelist()}
 executable={n for n,v in old['files'].items()if v.get('executable')}
 # Same length SONAME/RUNPATH adaptation used by the existing public payload.
 module=ast.parse((R/'.verification/components-github/sources/prepare_runtime.py').read_text())
 pure=ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef)and n.name in ['elf','text','android_name']],type_ignores=[]);scope={'struct':struct,'re':re};exec(compile(pure,'elf_helpers','exec'),scope)
 data=bytearray((RAW/'bin/lld').read_bytes());strings,tags=scope['elf'](data)
 for tag,offset,_ in tags:
  if tag in [1,14]:
   text=scope['text'](data,strings+offset);new=scope['android_name'](text)
   data[strings+offset:strings+offset+len(text)]=new.encode()
  if tag in [15,29]:
   text=scope['text'](data,strings+offset);data[strings+offset:strings+offset+len(text)]=b'$ORIGIN'+b'\0'*(len(text)-7)
 files['bin/ld.lld']=bytes(data);executable.add('bin/ld.lld')
 # Only C headers/libraries: no unused LLD development archives or sanitizer scripts.
 for p in sorted((RAW/'include').rglob('*')):
  if p.is_file():files['runtime/sysroot/usr/include/'+p.relative_to(RAW/'include').as_posix()]=p.read_bytes()
 for p in sorted((RAW/'lib').glob('*')):
  if p.is_file()and p.suffix in ['.o','.so','.a']and not p.name.startswith('liblld'):files['runtime/sysroot/usr/lib/'+p.name]=p.read_bytes()
 for p in sorted((RAW/'lib/clang/21/lib/linux').glob('*')):
  if p.is_file()and p.name=='libclang_rt.builtins-aarch64-android.a':files['runtime/clang/lib/linux/'+p.name]=p.read_bytes()
 for item in inputs:
  blob=(INPUT/Path(item['Filename']).name).read_bytes();offset=8
  while offset<len(blob):
   header=blob[offset:offset+60];size=int(header[48:58]);part=blob[offset+60:offset+60+size];offset+=60+size+size%2
   if header[:16].strip().startswith(b'data.tar'):
    with tarfile.open(fileobj=io.BytesIO(part))as t:
     for entry in t.getmembers():
      if entry.isfile()and '/share/doc/'in entry.name and entry.name.endswith(('/copyright','/LICENSE','/NOTICE')):files['licenses/'+item['Package']+'-'+Path(entry.name).name]=t.extractfile(entry).read()
 files['sources/package-inputs.json']=(json.dumps(inputs,indent=2)+'\n').encode();files['sources/prepare_clang_component.py']=Path(__file__).read_bytes()
 files['PROVENANCE.json']=(json.dumps({'upstream':'https://github.com/termux/termux-packages','baseArchive':old['archive'],'target':'aarch64-linux-android29','systemLibraries':'Android /system/lib64; device Bionic; no foreign Termux directories','limitations':['C++ standard-library headers not included; C toolchain only','not an NDK cross-API compatibility guarantee; linked against current Android system libraries'],'sourceRecipes':['packages/ndk-sysroot/build.sh','packages/lld/build.sh','packages/libcompiler-rt/build.sh']},indent=2)+'\n').encode()
 archive=OUT/f'clang-{VERSION}-android-arm64.zip';meta={}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for name,data in sorted(files.items()):
   i=zipfile.ZipInfo(name,date_time=(2026,10,31,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100755 if name in executable else 0o100644)<<16;z.writestr(i,data)
   meta[name]={'bytes':len(data),'sha256':sha(data),'executable':name in executable}
 info={**old,'version':VERSION,'title':'Clang / LLVM (Android C toolchain)','functionalProfile':'android-c-link-v1','files':meta,'archive':{'url':f'https://github.com/HezeAI/devkitjobs-components/releases/download/{TAG}/'+archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes())}}
 (OUT/'clang-r2.json').write_text(json.dumps(info,indent=2)+'\n');print(archive.name,info['archive'],flush=True)
if __name__=='__main__':main()
