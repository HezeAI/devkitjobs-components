"""Shared, transactional native component manager. Standard library only.

Public CLI: devkit-tools list|catalog|install ID|check ID|updates|run COMMAND ...
Install/import never activates a version whose functional tests fail.
"""
from pathlib import Path,PurePosixPath
import argparse,contextlib,fcntl,hashlib,json,os,platform,re,shutil,stat,struct,subprocess,sys,tempfile,time,urllib.request,urllib.parse,uuid,zipfile

DEFAULT_CATALOG='https://github.com/HezeAI/devkitjobs-components/releases/latest/download/tools.json'
ID=re.compile(r'^[a-z0-9][a-z0-9.+_-]{0,79}$')
COMMAND=re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9.+_-]{0,79}$')
MAX_CATALOG=8*1024*1024
class ToolError(Exception):pass
class Incompatible(ToolError):pass

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read_json(p):return json.loads(Path(p).read_text())
def atomic(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temp.open('w') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  temp.replace(p)
 finally:temp.unlink(missing_ok=True)
def child(root,name):
 if not isinstance(name,str) or not name or '\\'in name or '\x00'in name or any(p in ('','..','.')for p in name.split('/')) or PurePosixPath(name).is_absolute():raise ToolError('Unsafe component path')
 p=Path(root)/name
 if not p.resolve().is_relative_to(Path(root).resolve()):raise ToolError('Component path escapes tools directory')
 return p
class HttpsRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):
  if urllib.parse.urlsplit(newurl).scheme!='https':raise ToolError('HTTPS redirect required')
  return super().redirect_request(request,fp,code,msg,headers,newurl)
def fetch(url,destination,limit,expected=None):
 if urllib.parse.urlsplit(url).scheme!='https':raise ToolError('HTTPS source required')
 opener=urllib.request.build_opener(HttpsRedirect())
 size=0;h=hashlib.sha256()
 with opener.open(urllib.request.Request(url,headers={'User-Agent':'DevKitJobs-tools/1'}),timeout=30)as source,Path(destination).open('wb')as out:
  while True:
   b=source.read(1024*1024)
   if not b:break
   size+=len(b)
   if size>limit:raise ToolError('Download exceeds declared size')
   h.update(b);out.write(b)
 if expected and(size!=expected['bytes']or h.hexdigest()!=expected['sha256']):raise ToolError('Archive size or SHA-256 mismatch')
 return size

class Manager:
 def __init__(self,root,base=None,bundled_catalog=None):
  self.root=Path(root).resolve();self.base=Path(base or self.root.parent).resolve()
  self.bundled=Path(bundled_catalog or self.root/'catalog-bundled.json')
  self.python=str(self.base/'bin/python3');self.script=str(self.root/'devkit-tools.py')
  for n in ['bin','versions','.staging','.locks','checks','cache']:(self.root/n).mkdir(parents=True,exist_ok=True)
 def key(self,id):
  if not isinstance(id,str) or not ID.fullmatch(id):raise ToolError('Invalid component ID/version')
  return id
 @contextlib.contextmanager
 def lock(self,name):
  with (self.root/'.locks'/self.key(name)).open('a')as f:
   fcntl.flock(f,fcntl.LOCK_EX)
   try:yield
   finally:fcntl.flock(f,fcntl.LOCK_UN)
 def catalog(self,refresh=False):
  if refresh:
   p=self.root/'cache'/('catalog-'+uuid.uuid4().hex+'.tmp')
   try:
    fetch(DEFAULT_CATALOG,p,MAX_CATALOG);data=read_json(p);self.validate_catalog(data)
    # Archives cannot be silently replaced under the same component version.
    old=self.catalog(False)
    for id,info in data['components'].items():
     prior=old['components'].get(id)
     if prior and prior['version']==info['version'] and prior['archive']['sha256']!=info['archive']['sha256']:raise ToolError('Published component version changed: '+id)
    atomic(self.root/'catalog.json',data);return data
   finally:p.unlink(missing_ok=True)
  p=self.root/'catalog.json'
  data=read_json(p if p.is_file()else self.bundled);self.validate_catalog(data)
  imported=self.root/'imports.json'
  if imported.is_file():
   for id,info in read_json(imported).items():
    if id not in data['components']:data['components'][id]={**info,'origin':'adapted'}
  # Recover completed external imports after a crash before registry/index publication.
  for p in (self.root/'versions').glob('*/*/component.json'):
   if p.stat().st_size>MAX_CATALOG:continue
   try:
    info=read_json(p);self.validate(info)
    if p.parent!=self.version_path(info['id'],info['version']):continue
    if info['id']not in data['components']:data['components'][info['id']]={**info,'origin':'adapted'}
   except (ValueError,KeyError,ToolError):continue
  return data
 def validate_catalog(self,data):
  if data.get('schema')!=1 or not isinstance(data.get('components'),dict):raise ToolError('Unsupported catalog')
  for id,info in data['components'].items():
   if id!=info.get('id'):raise ToolError('Catalog ID mismatch')
   self.validate(info)
 def validate(self,info):
  self.key(info['id']);self.key(info['version'])
  if not isinstance(info.get('source'),str)or not info['source'].startswith('https://'):raise ToolError('Official source/provenance URL required')
  if not isinstance(info.get('platform'),str)or not isinstance(info.get('abi'),str)or not isinstance(info.get('minAndroidApi'),int):raise ToolError('Missing platform compatibility metadata')
  if not isinstance(info.get('files'),dict)or not info['files']:raise ToolError('Missing file integrity manifest')
  if not isinstance(info.get('commands'),dict)or not info['commands']:raise ToolError('Missing functional checks')
  a=info['archive']
  if not isinstance(a.get('bytes'),int)or not 0<a['bytes']<=1024**3 or not re.fullmatch('[0-9a-f]{64}',a.get('sha256','')):raise ToolError('Invalid archive integrity metadata')
  if urllib.parse.urlsplit(a['url']).scheme!='https':raise ToolError('HTTPS source required')
  for name,meta in info['files'].items():
   child(self.root/'validation',name)
   if not isinstance(meta.get('bytes'),int)or not 0<=meta['bytes']<=1024**3 or not re.fullmatch('[0-9a-f]{64}',meta.get('sha256','')):raise ToolError('Invalid file integrity metadata')
  for name,command in info['commands'].items():
   if not COMMAND.fullmatch(name):raise ToolError('Invalid command')
   if command['path']not in info['files']or not info['files'][command['path']].get('executable'):raise ToolError('Missing executable')
   if not isinstance(command.get('probe'),list)or not all(isinstance(x,str)and len(x)<4096 for x in command['probe']):raise ToolError('Functional probe must use argv')
   builtin=self.root/'builtin.json'
   if builtin.is_file()and name in read_json(builtin)['binaries']:raise ToolError('Cannot replace a protected built-in command: '+name)
  for dep,version in info.get('dependencies',{}).items():self.key(dep);self.key(version)
  for name,target in info.get('links',{}).items():
   link=child(self.root/'validation',name)
   if not isinstance(target,str)or Path(target).is_absolute()or not (link.parent/target).resolve().is_relative_to((self.root/'validation').resolve()):raise ToolError('Unsafe component link')
 def compatible(self,info):
  self.validate(info)
  if info['platform']!='android' or info['abi']!='arm64-v8a':raise Incompatible('Android ARM64 component required')
  if platform.machine().lower() not in ['aarch64','arm64']:raise Incompatible('Phone architecture is not ARM64')
  api=int(os.environ.get('DEVKIT_ANDROID_API','0'))
  if api and api<info['minAndroidApi']:raise Incompatible('Android API too old')
  target=int(os.environ.get('DEVKIT_TARGET_SDK','0'))
  if target>=29:raise Incompatible('Downloaded executables require the targetSdk 28 DevKit test build')
 def state(self):
  p=self.root/'active.json'
  return read_json(p)if p.is_file()else {'schema':1,'components':{}}
 def version_path(self,id,version):return self.root/'versions'/self.key(id)/self.key(version)
 def selected(self,id,state=None):
  row=(state or self.state())['components'].get(id)
  if not row:raise ToolError('Component is not ready: '+id+'; run devkit-tools install '+id)
  return self.version_path(id,row['version']),row
 def verify_files(self,directory,info):
  expected=set(info['files'])|set(info.get('links',{}))|{'component.json','.check.json'}
  for p in Path(directory).rglob('*'):
   if (p.is_file()or p.is_symlink())and p.relative_to(directory).as_posix()not in expected:raise ToolError('Unexpected component file')
  for name,meta in info['files'].items():
   p=child(directory,name)
   if p.is_symlink()or not p.is_file()or p.stat().st_size!=meta['bytes']or sha(p)!=meta['sha256']:raise ToolError('Corrupt or missing file: '+name)
   if meta.get('executable'):
    with p.open('rb')as f:b=f.read(64)
    if b[:6]!=b'\x7fELF\x02\x01'or len(b)<20 or struct.unpack_from('<H',b,18)[0]!=183:raise Incompatible('Executable is not Android ARM64 ELF: '+name)
    offset=struct.unpack_from('<Q',b,32)[0];width,count=struct.unpack_from('<HH',b,54)
    if width<56 or count>512:raise Incompatible('Invalid ELF program headers')
    with p.open('rb')as f:
     for i in range(count):
      f.seek(offset+i*width);header=f.read(width)
      if len(header)!=width:raise Incompatible('Truncated ELF program headers')
      if struct.unpack_from('<I',header)[0]==3:
       start=struct.unpack_from('<Q',header,8)[0];length=struct.unpack_from('<Q',header,32)[0]
       if length>256:raise Incompatible('Invalid ELF interpreter')
       f.seek(start);interpreter=f.read(length).rstrip(b'\0')
       if interpreter!=b'/system/bin/linker64':raise Incompatible('Executable requires a non-Android loader')
  for name,target in info.get('links',{}).items():
   p=child(directory,name)
   if not p.is_symlink()or os.readlink(p)!=target:raise ToolError('Component link changed: '+name)
  return True
 def extract(self,archive,destination,info):
  destination.mkdir(parents=True,exist_ok=True);names=set();total=0
  with zipfile.ZipFile(archive)as z:
   for entry in z.infolist():
    if entry.is_dir():continue
    name=entry.filename;p=child(destination,name)
    if name in names or name not in info['files']or stat.S_ISLNK(entry.external_attr>>16):raise ToolError('Unexpected, duplicate or linked archive entry')
    names.add(name);meta=info['files'][name];total+=entry.file_size
    if entry.file_size!=meta['bytes']or total>2*1024**3:raise ToolError('Expanded size mismatch')
    p.parent.mkdir(parents=True,exist_ok=True)
    with z.open(entry)as source,p.open('xb')as target:shutil.copyfileobj(source,target,1024*1024)
    p.chmod(0o500 if meta.get('executable')else 0o400)
  if names!=set(info['files']):raise ToolError('Archive omits required files')
  for name,target in info.get('links',{}).items():
   p=child(destination,name);p.parent.mkdir(parents=True,exist_ok=True);p.symlink_to(target)
  atomic(destination/'component.json',info);self.verify_files(destination,info)
 def environment(self,info,directory,state=None):
  state=state or self.state();env=os.environ.copy();env['DEVKIT_TOOLS']=str(self.root)
  env['PATH']=str(self.root/'bin')+':'+str(self.base/'bin')+':/system/bin'
  roots={info['id']:Path(directory)}
  for dep,version in info.get('dependencies',{}).items():
   path,row=self.selected(dep,state)
   if row['version']!=version:raise ToolError('Dependency version mismatch: '+dep)
   roots[dep]=path
  libraries=[str(p/'lib')for p in roots.values()]
  env['LD_LIBRARY_PATH']=':'.join([*libraries,os.environ.get('DEVKIT_LIBDIR','')])
  if 'jdk'in roots:
   p=roots['jdk'];env['JAVA_HOME']=str(p/'runtime/jdk');env['DEVKIT_LIBDIR']=str(p/'lib');env['DEVKIT_RUNTIME']=str(p/'runtime')
  if info['id']=='gradle':env['GRADLE_HOME']=str(Path(directory)/'runtime/gradle')
  if info['id']=='android-sdk':
   env['ANDROID_HOME']=env['ANDROID_SDK_ROOT']=str(Path(directory)/'runtime/android-sdk')
   # Java tools need the JDK launcher.jar; the Python builder is launched explicitly.
  if info['id']=='clang':env['CLANG_RESOURCE_DIR']=str(Path(directory)/'runtime/clang')
  return env
 def argv(self,command,info,directory,args):
  # This tiny ELF launcher invokes Python at DEVKIT_BIN; use the component's own builder script instead.
  if command=='devkit-build-apk':return [self.python,'-B',str(Path(directory)/'runtime/build-apk.py'),*args]
  return [str(child(directory,info['commands'][command]['path'])),*args]
 def probe(self,info,directory):
  env=self.environment(info,directory);checks=[]
  with tempfile.TemporaryDirectory(prefix='probe-',dir=self.root/'.staging')as temp:
   for name,command in info['commands'].items():
    # Probe output must not contain account state or secrets.
    isolated=env.copy();isolated['GH_CONFIG_DIR']=temp;isolated.pop('GH_TOKEN',None);isolated.pop('GITHUB_TOKEN',None)
    argv=self.argv(name,info,directory,command['probe'])
    try:
     with tempfile.TemporaryFile()as log:
      p=subprocess.Popen(argv,env=isolated,cwd=temp,stdout=log,stderr=subprocess.STDOUT)
      try:code=p.wait(timeout=90)
      except BaseException:p.kill();p.wait();raise
      log.seek(0);output=log.read(65537)
     text=output[:65536].decode(errors='replace')
     if code or len(output)>65536 or command.get('expect','')not in text:raise ToolError('Functional test failed: '+name+' (exit '+str(code)+')')
    except OSError as e:raise ToolError('Cannot execute '+name+': '+str(e.errno))from e
    checks.append({'command':name,'exit':code,'probe':command['probe'],'output':text[:1000]})
   if info['id']=='jdk':
    p=Path(temp);(p/'Hello.java').write_text('class Hello { public static void main(String[] a) { System.out.print("DEVKIT_JAVA_OK"); } }')
    subprocess.run(self.argv('javac',info,directory,[str(p/'Hello.java')]),env=env,cwd=temp,check=True,capture_output=True,timeout=90)
    result=subprocess.run(self.argv('java',info,directory,['-cp',temp,'Hello']),env=env,cwd=temp,check=True,capture_output=True,timeout=90)
    if result.stdout!=b'DEVKIT_JAVA_OK':raise ToolError('Java compile/run test failed')
    checks.append({'functional':'compile-and-run-java','status':'passed'})
   if info['id']=='clang':
    p=Path(temp);(p/'probe.c').write_text('int devkit_probe(void) { return 42; }')
    subprocess.run(self.argv('clang',info,directory,['-c',str(p/'probe.c'),'-o',str(p/'probe.o')]),env=env,cwd=temp,check=True,capture_output=True,timeout=90)
    if not(p/'probe.o').is_file():raise ToolError('Clang compile test failed')
    checks.append({'functional':'compile-c-object','status':'passed'})
  return {'status':'ready','checkedAt':int(time.time()),'checks':checks,'platform':platform.machine(),'androidApi':os.environ.get('DEVKIT_ANDROID_API'),'targetSdk':os.environ.get('DEVKIT_TARGET_SDK')}
 def wrappers(self,info):
  for name in info['commands']:
   self.wrapper(name)
 def wrapper(self,name):
  if not COMMAND.fullmatch(name):raise ToolError('Invalid command')
  def q(s):return "'"+s.replace("'","'\\''")+"'"
  text='#!/system/bin/sh\nexec '+q(self.python)+' -B '+q(self.script)+' run '+q(name)+' "$@"\n'
  p=self.root/'bin'/name;temp=p.with_name('.'+name+'.'+uuid.uuid4().hex)
  temp.write_text(text);temp.chmod(0o500);temp.replace(p)
 def install(self,id,info=None,local_archive=None,visiting=None):
  id=self.key(id);catalog=self.catalog();info=info or catalog['components'].get(id)
  if not info:raise ToolError('Component not found in catalog')
  self.compatible(info);visiting=set(visiting or())
  if id in visiting:raise ToolError('Dependency cycle')
  visiting.add(id)
  for dep,version in info.get('dependencies',{}).items():
   active=self.state()['components'].get(dep)
   if not active or active['version']!=version:
    candidate=catalog['components'].get(dep)
    if not candidate or candidate['version']!=version:raise ToolError('Required dependency not available: '+dep)
    self.install(dep,candidate,visiting=visiting)
   else:self.check(dep)
  with self.lock(id):
   directory=self.version_path(id,info['version']);directory.parent.mkdir(parents=True,exist_ok=True)
   if directory.exists():
    installed=read_json(directory/'component.json')
    if installed['archive']['sha256']!=info['archive']['sha256']:raise ToolError('Installed immutable version differs')
    self.verify_files(directory,info);checked=self.probe(info,directory)
   else:
    stage=self.root/'.staging'/(id+'-'+uuid.uuid4().hex);archive=self.root/'cache'/(info['archive']['sha256']+'.zip')
    try:
     if local_archive:
      if Path(local_archive).stat().st_size!=info['archive']['bytes']or sha(local_archive)!=info['archive']['sha256']:raise ToolError('Local archive checksum mismatch')
      source=Path(local_archive)
     else:
      if not archive.is_file()or archive.stat().st_size!=info['archive']['bytes']or sha(archive)!=info['archive']['sha256']:
       temp=archive.with_suffix('.'+uuid.uuid4().hex+'.part')
       try:fetch(info['archive']['url'],temp,info['archive']['bytes'],info['archive']);temp.replace(archive)
       finally:temp.unlink(missing_ok=True)
      source=archive
     self.extract(source,stage,info)
     # Native JVMs derive paths from their install location. Move to the final immutable location before testing; not yet active.
     stage.replace(directory)
     checked=self.probe(info,directory)
    except BaseException as error:
     shutil.rmtree(stage,ignore_errors=True)
     atomic(self.root/'checks'/id,{'status':'incompatible'if isinstance(error,Incompatible)else 'broken','version':info['version'],'reason':str(error),'checkedAt':int(time.time())})
     raise
   atomic(directory/'.check.json',checked)
   # Global registry activation is one atomic replace, independently locked across components/chats.
   with self.lock('registry'):
    state=self.state()
    for dep,version in info.get('dependencies',{}).items():
     if state['components'].get(dep,{}).get('version')!=version:raise ToolError('Dependency changed during installation')
    for other,row in state['components'].items():
     if other==id:continue
     other_info=read_json(self.version_path(other,row['version'])/'component.json')
     if id in other_info.get('dependencies',{})and other_info['dependencies'][id]!=info['version']:raise ToolError('Update conflicts with active dependency: '+other)
     if set(other_info['commands'])&set(info['commands']):raise ToolError('Command already owned by another component')
    self.wrappers(info)
    state['components'][id]={'version':info['version'],'archiveSha256':info['archive']['sha256'],'checkedAt':checked['checkedAt']}
    atomic(self.root/'active.json',state)
   atomic(self.root/'checks'/id,checked)
   return {'id':id,'version':info['version'],'status':'ready'}
 def check(self,id):
  with self.lock(id):
   directory,row=self.selected(id);info=read_json(directory/'component.json')
   try:self.compatible(info);self.verify_files(directory,info);result=self.probe(info,directory);atomic(directory/'.check.json',result)
   except Exception as error:
    result={'status':'incompatible'if isinstance(error,Incompatible)else 'broken','reason':str(error),'checkedAt':int(time.time())};atomic(self.root/'checks'/id,result);raise
   atomic(self.root/'checks'/id,result);return result
 def listing(self):
  catalog=self.catalog();state=self.state();rows=[]
  for id,info in catalog['components'].items():
   row={'id':id,'name':info.get('title',id),'version':info['version'],'latestVersion':info['version'],'origin':info.get('origin','catalog'),'source':info['source'],'abi':info['abi'],'commands':list(info['commands']),'downloadBytes':info['archive']['bytes'],'status':'not_installed'}
   try:self.compatible(info)
   except Incompatible as e:row.update(status='incompatible',reason=str(e))
   installed=state['components'].get(id)
   if installed:
    directory=self.version_path(id,installed['version']);current=read_json(directory/'component.json')
    try:
     self.verify_files(directory,current);check=read_json(directory/'.check.json')
     row.update(version=installed['version'],path=str(directory),status='ready'if check.get('status')=='ready'else 'downloaded',checkedAt=check.get('checkedAt'))
    except Exception as e:row.update(status='broken',reason=str(e))
   p=self.root/'checks'/id
   if p.is_file():
    check=read_json(p)
    if check.get('status')!='ready':row['lastAttempt']=check
   if not installed and self.version_path(id,info['version']).exists():
    row['status']=check.get('status','downloaded')if p.is_file()else 'downloaded'
   rows.append(row)
  return {'components':rows,'builtin':self.builtin()}
 def builtin(self,name=None):
  p=self.root/'builtin.json'
  if not p.is_file():return []
  manifest=read_json(p);rows=[]
  for command,meta in manifest['tools'].items():
   row={'id':command,'name':command,'version':meta['version'],'origin':'builtin','status':'downloaded','source':'APK','commands':[command]}
   executable=self.base/'bin'/command;receipt=self.root/'checks'/('builtin-'+command)
   if not executable.is_file():row.update(status='broken',reason='Встроенный файл отсутствует')
   elif name==command:
    if command in ['codex-code-mode-host','ssh-keygen']:
     row.update(status='downloaded',reason='Требуется проверка через Codex или генерацию тестового ключа')
    else:
     expected=manifest.get('libraries',{}).get(manifest['binaries'][command],{}).get('sha256')
     if expected and sha(executable)!=expected:raise ToolError('Built-in checksum mismatch')
     argv=[str(executable),'-V'if command=='ssh'else '--version']
     try:
      result=subprocess.run(argv,capture_output=True,timeout=15)
      if result.returncode:raise ToolError('Built-in functional check failed')
      row.update(status='ready',checkedAt=int(time.time()))
     except Exception:row.update(status='broken',reason='Функциональный тест не пройден')
     atomic(receipt,row)
   elif receipt.is_file():
    checked=read_json(receipt)
    if checked.get('version')==row['version']:row.update(checked)
   rows.append(row)
  return rows
 def run(self,command,args):
  state=self.state();found=None
  for id,row in state['components'].items():
   directory=self.version_path(id,row['version']);info=read_json(directory/'component.json')
   if command in info['commands']:found=(info,directory);break
  if not found:raise ToolError('Command is not ready: '+command+'. Use devkit-tools catalog / install COMPONENT.')
  info,directory=found;self.compatible(info)
  # Exact executable hash and dependency receipts are checked on each launch.
  for name in [info['commands'][command]['path']]:
   if sha(child(directory,name))!=info['files'][name]['sha256']:raise ToolError('Executable integrity changed; run devkit-tools check '+info['id'])
  env=self.environment(info,directory,state);argv=self.argv(command,info,directory,args)
  os.execve(argv[0],argv,env)

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['list','catalog','install','import','check','builtin','updates','run']);parser.add_argument('rest',nargs=argparse.REMAINDER);args=parser.parse_args(argv)
 root=os.environ.get('DEVKIT_TOOLS')
 if not root:raise ToolError('DEVKIT_TOOLS not configured')
 m=Manager(root)
 if args.action=='list':result=m.listing()
 elif args.action=='catalog':result=m.catalog()
 elif args.action=='updates':result=m.catalog(True)
 elif args.action=='install':result=m.install(args.rest[0])
 elif args.action=='import':
  # A researched official-source package may supply a locally adapted, fully hashed descriptor.
  info=read_json(args.rest[0]);result=m.install(info['id'],info,args.rest[1])
  with m.lock('registry'):
   p=m.root/'imports.json';imports=read_json(p)if p.is_file()else {};imports[info['id']]=info;atomic(p,imports)
 elif args.action=='check':result=m.check(args.rest[0])
 elif args.action=='builtin':result={'builtin':m.builtin(args.rest[0]if args.rest else None)}
 else:m.run(args.rest[0],args.rest[1:]);return
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except KeyboardInterrupt:print('Installation cancelled; active versions retained',file=sys.stderr);raise SystemExit(130)
 except Exception as e:print(json.dumps({'status':'failed','reason':str(e)},ensure_ascii=False),file=sys.stderr);raise SystemExit(1)
