"""Repackage ONLY public, already adapted payloads; never walk installed app data."""
from pathlib import Path
import hashlib,json,zipfile,shutil,struct

R=Path(__file__).resolve().parents[1]
O=R.parent/'devkit-source/DevKitJobs-Source-0.1.5'
OUT=R/'build/components';REPO=R.parent/'devkitjobs-components'
TAG='native-2026-10-30-r1'
URL='https://github.com/HezeAI/devkitjobs-components/releases/download/'+TAG+'/'
SYSTEM={'libc.so','libm.so','libdl.so','liblog.so','libz.so','libandroid.so'}

def digest(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def elf_needed(p):
 b=p.read_bytes()
 if b[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',b,18)[0]!=183:raise ValueError('Not ARM64: '+p.name)
 offset=struct.unpack_from('<Q',b,32)[0];width,count=struct.unpack_from('<HH',b,54);loads=[];dyn=None
 for i in range(count):
  kind=struct.unpack_from('<I',b,offset+i*width)[0];f,v=struct.unpack_from('<QQ',b,offset+i*width+8);size=struct.unpack_from('<Q',b,offset+i*width+32)[0]
  if kind==1:loads.append((v,f,size))
  if kind==2:dyn=(f,size)
 if not dyn:return []
 tags=[struct.unpack_from('<QQ',b,i) for i in range(dyn[0],sum(dyn),16)]
 table=next((v for k,v in tags if k==5),None)
 if table is None:return []
 strings=next(f+table-v for v,f,s in loads if v<=table<v+s)
 return [b[strings+v:b.index(b'\0',strings+v)].decode() for k,v in tags if k==1]

def prepare():
 OUT.mkdir(parents=True,exist_ok=True);REPO.mkdir(exist_ok=True)
 native={p.name:p for p in (O/'app/src/main/jniLibs/arm64-v8a').glob('*.so')}
 native.update({p.name:p for p in (R/'native-tools/arm64-v8a').glob('*.so')})
 original=json.loads((O/'app/src/main/assets/runtime-manifest.json').read_text())
 additions=json.loads((R/'native-runtime-additions.json').read_text())
 for section in ['binaries','libraries','tools']:original[section].update(additions[section])
 extra=json.loads((R/'source/app/src/main/assets/devkit-native-tools.json').read_text())
 needed={n:elf_needed(p) for n,p in native.items()}
 def closure(names):
  seen=set();pending=list(names)
  while pending:
   n=pending.pop()
   if n in SYSTEM or n in seen:continue
   if n not in native:raise ValueError('Missing native dependency '+n)
   seen.add(n);pending+=needed[n]
  return seen
 optional={'clang','java','javac','jar','javap','keytool','gradle','apksigner','d8','aapt2','devkit-build-apk','gh'}
 base=json.loads(json.dumps(original));base['binaries']={k:v for k,v in original['binaries'].items() if k not in optional};base['tools']={k:v for k,v in original['tools'].items() if k not in optional};base['javaLibraries']={}
 core=closure([*base['binaries'].values(),*base['pythonExtensions'].values(),'libdevkit_runner.so'])
 base['libraries']={k:v for k,v in original['libraries'].items() if k in core}
 save(OUT/'runtime-manifest.json',base)
 with zipfile.ZipFile(O/'app/src/main/assets/runtime.zip') as runtime:
  with zipfile.ZipFile(OUT/'runtime.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for item in runtime.infolist():
    if item.filename.startswith('python/'):z.writestr(item,runtime.read(item))
  specs={
   'gh':{'version':'2.103.3-r1','title':'GitHub CLI','native':closure(['libtool_gh.so']),'roots':[], 'commands':{'gh':{'path':'bin/gh','native':'libtool_gh.so','probe':['--version'],'expect':'gh version 2.103.3'}},'dependencies':{},'source':'https://github.com/cli/cli','license':'MIT'},
   'jdk':{'version':'25.0.5-r1','title':'OpenJDK 25','native':closure([*original['javaLibraries'].values(),'libtool_java.so']),'roots':['jdk/','launcher.jar'],'commands':{n:{'path':'bin/'+n,'native':'libtool_java.so','probe':['--version'] if n not in ['keytool'] else ['-help'],'expect':'25' if n not in ['keytool'] else ''} for n in ['java','javac','jar','javap','keytool']},'dependencies':{},'source':'https://github.com/termux/termux-packages/tree/master/packages/openjdk-25','license':'GPL-2.0-with-classpath-exception'},
   'gradle':{'version':'9.5.0-r1','title':'Gradle','native':set(),'roots':['gradle/'],'commands':{'gradle':{'path':'bin/gradle','native':'libtool_java.so','probe':['--version'],'expect':'Gradle 9.5.0'}},'dependencies':{'jdk':'25.0.5-r1'},'source':'https://gradle.org/releases/','license':'Apache-2.0'},
   'android-sdk':{'version':'35-36.0.0-r1','title':'Android SDK + APK builder','native':closure(['libtool_aapt2.so','libtool_buildapk.so']),'roots':['android-sdk/','build-apk.py'],'commands':{'aapt2':{'path':'bin/aapt2','native':'libtool_aapt2.so','probe':['version'],'expect':'Android Asset Packaging Tool'},'d8':{'path':'bin/d8','native':'libtool_java.so','probe':['--version'],'expect':'D8'},'apksigner':{'path':'bin/apksigner','native':'libtool_java.so','probe':['version'],'expect':''},'devkit-build-apk':{'path':'bin/devkit-build-apk','native':'libtool_buildapk.so','probe':['--help'],'expect':'Build a small Java Android project'}},'dependencies':{'jdk':'25.0.5-r1'},'source':'https://developer.android.com/tools','license':'Apache-2.0'},
   'clang':{'version':'21-r1','title':'Clang / LLVM','native':closure(['libtool_clang.so']),'roots':['clang/'],'commands':{'clang':{'path':'bin/clang','native':'libtool_clang.so','probe':['--version'],'expect':'clang version 21'}},'dependencies':{},'source':'https://github.com/termux/termux-packages/tree/master/packages/clang','license':'Apache-2.0-with-LLVM-exception'},
  }
  catalog={'schema':1,'set':TAG,'platform':'android','abi':'arm64-v8a','minAndroidApi':29,'requiredTargetMax':28,'components':{},'tools':{}}
  for id,spec in specs.items():
   version=spec['version'];name=id+'-'+version+'-android-arm64.zip';archive=OUT/name
   files={}
   def add(z,name,data,executable=False):
    if name in files:raise ValueError('Duplicate component file '+name)
    if Path(name).name in {'auth.json','hosts.yml','known_hosts','id_ed25519','id_rsa','signing.pass','password'} or name.endswith(('.jks','.keystore')):raise ValueError('Private filename')
    i=zipfile.ZipInfo(name,date_time=(2026,10,30,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100755 if executable else 0o100644)<<16
    z.writestr(i,data);files[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'executable':executable}
   with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
    command_native={c['native']for c in spec['commands'].values()}
    for n in sorted(spec['native']-command_native):add(z,'lib/'+n,native[n].read_bytes(),True)
    for command,info in spec['commands'].items():add(z,info['path'],native[info['native']].read_bytes(),True)
    for item in runtime.infolist():
     if not item.is_dir() and any(item.filename.startswith(p) if p.endswith('/') else item.filename==p for p in spec['roots']):
      data=runtime.read(item)
      if item.filename=='build-apk.py':
       data=data.replace(b'binary=Path(os.environ[\'DEVKIT_BIN\'])',b'binary=Path(os.environ[\'DEVKIT_TOOLS\'])/\'bin\'')
      add(z,'runtime/'+item.filename,data)
    if id=='jdk':
     # Relative symlinks are created by the installer after integrity validation.
     links={('runtime/jdk/'+name):('../../../lib/'+target if name.count('/')==1 else '../../../../lib/'+target) for name,target in original['javaLibraries'].items()}
     links.update({'runtime/jdk/bin/'+n:'../../../bin/'+n for n in ['java','javac','jar','javap','keytool']})
    else:links={}
    for p in sorted((O/'app/src/main/assets/licenses').glob('*.txt')):add(z,'licenses/'+p.name,p.read_bytes())
    add(z,'THIRD_PARTY_NOTICES.txt',(O/'app/src/main/assets/THIRD_PARTY_NOTICES.txt').read_bytes())
    if id=='gh':add(z,'licenses/gh-NOTICE.txt',(R/'source/app/src/main/assets/gh-NOTICE.txt').read_bytes())
   info={k:v for k,v in spec.items() if k not in ['native','roots']};info.update({'id':id,'platform':'android','abi':'arm64-v8a','minAndroidApi':29,'archive':{'url':URL+name,'sha256':digest(archive),'bytes':archive.stat().st_size},'files':files,'links':links})
   for cmd in info['commands'].values():cmd.pop('native')
   catalog['components'][id]=info
   for cmd in info['commands']:catalog['tools'][cmd]={'component':id,'version':version}
   print(id,archive.stat().st_size,info['archive']['sha256'],flush=True)
  backup=OUT/'core-backup-0.2.9-android-arm64.zip'
  if not backup.is_file():
   with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
    for name in sorted(core):
     entry=zipfile.ZipInfo('lib/'+name,date_time=(2026,10,30,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
     with native[name].open('rb')as source,z.open(entry,'w')as target:shutil.copyfileobj(source,target,1024*1024)
    z.write(OUT/'runtime.zip','runtime.zip');z.writestr('runtime-manifest.json',json.dumps(base,indent=2))
    for p in sorted((O/'app/src/main/assets/licenses').glob('*.txt')):z.write(p,'licenses/'+p.name)
    z.write(O/'app/src/main/assets/THIRD_PARTY_NOTICES.txt','THIRD_PARTY_NOTICES.txt')
  catalog['bootstrapBackup']={'url':URL+backup.name,'bytes':backup.stat().st_size,'sha256':digest(backup),'activation':'APK only; archive is a backup, not an automatically installable component'}
  save(OUT/'tools.json',catalog);save(REPO/'tools.json',catalog);save(REPO/'components.json',catalog)
  save(OUT/'payload.json',{'coreNative':sorted(core),'optionalCommands':sorted(optional),'catalogSha256':digest(OUT/'tools.json')})
  assets=R/'source/app/src/main/assets';shutil.copyfile(OUT/'tools.json',assets/'tools-catalog.json')
  shutil.copyfile(OUT/'runtime-manifest.json',assets/'runtime-manifest-light.json')
  save(assets/'devkit-native-tools.json',{'binaries':{},'tools':{},'downloadableCatalog':'tools-catalog.json'})
  save(OUT/'release-inputs.json',{'tag':TAG,'catalogSha256':digest(OUT/'tools.json'),'coreNativeFiles':len(core),'archives':{k:v['archive']for k,v in catalog['components'].items()}})
 return catalog
if __name__=='__main__':prepare()
