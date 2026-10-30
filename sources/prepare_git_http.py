"""Verified public Git HTTPS helper inputs, adapted like the original native payload."""
from pathlib import Path
import ast,struct,re,json,hashlib,urllib.request,tarfile,io,importlib.util
R=Path(__file__).resolve().parents[1];O=R.parent/'devkit-source/DevKitJobs-Source-0.1.5';B=R/'.tools/git-http';RAW=B/'raw';RAW.mkdir(exist_ok=True);OUT=R/'native-tools/arm64-v8a';OUT.mkdir(exist_ok=True)
source=ast.parse((O/'build-support/prepare_runtime.py').read_text());pure=ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef)and n.name in ['elf','text','android_name']],type_ignores=[]);scope={'struct':struct,'re':re};exec(compile(pure,'public_elf_helpers','exec'),scope)
catalog={}
for block in(B/'Packages').read_text().split('\n\n'):
 d=dict(line.split(': ',1)for line in block.splitlines()if ': 'in line and not line.startswith(' '))
 if d.get('Package'):catalog[d['Package']]=d
inputs=[]
for package in ['git','libcurl','libnghttp2','libnghttp3','libngtcp2','libssh2']:
 d=catalog[package];p=B/Path(d['Filename']).name
 if not p.is_file():
  with urllib.request.urlopen('https://packages.termux.dev/apt/termux-main/'+d['Filename'],timeout=30)as f:p.write_bytes(f.read())
 assert hashlib.sha256(p.read_bytes()).hexdigest()==d['SHA256'];inputs.append({k:d.get(k)for k in ['Package','Version','Filename','SHA256','Size']})
 b=p.read_bytes();off=8
 while off<len(b):
  header=b[off:off+60];size=int(header[48:58]);name=header[:16].decode().strip().rstrip('/');part=b[off+60:off+60+size];off+=60+size+size%2
  if name.startswith('data.tar'):
   with tarfile.open(fileobj=io.BytesIO(part))as t:
    for entry in t.getmembers():
     if entry.isfile()and ('/lib/lib' in entry.name or entry.name.endswith('/git-remote-http')):
      f=t.extractfile(entry);blob=f.read()
      if blob[:4]==b'\x7fELF':(RAW/Path(entry.name).name).write_bytes(blob)
old=O/'app/src/main/jniLibs/arm64-v8a';done={}
system={'libc.so','libm.so','libdl.so','liblog.so','libandroid.so','libz.so'}
def adapt(raw,name):
 if name in done:return
 if (old/name).is_file():return
 b=bytearray(raw.read_bytes());strings,tags=scope['elf'](b);deps=[]
 for tag,value,_ in tags:
  if tag==1:deps.append(scope['text'](b,strings+value))
  if tag in [1,14]:
   text=scope['text'](b,strings+value);new=scope['android_name'](text);b[strings+value:strings+value+len(text)]=new.encode()
  if tag in [15,29]:
   text=scope['text'](b,strings+value)
   if len(text)<7:raise ValueError('RUNPATH capacity')
   b[strings+value:strings+value+len(text)]=b'$ORIGIN'+b'\0'*(len(text)-7)
 p=OUT/name;p.write_bytes(b);p.chmod(0o755);done[name]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'sourceSha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'needed':[scope['android_name'](x)if x not in system else x for x in deps]}
 for dep in deps:
  if dep in system:continue
  target=scope['android_name'](dep)
  if(old/target).is_file():continue
  candidate=RAW/dep
  if not candidate.is_file():raise ValueError('Missing public native dependency '+dep)
  adapt(candidate,target)
adapt(RAW/'git-remote-http','libtool_git_remote_http.so')
(B/'native-additions.json').write_text(json.dumps({'binaries':{'git-remote-http':'libtool_git_remote_http.so','git-remote-https':'libtool_git_remote_http.so'},'libraries':done,'tools':{n:{'version':'2.56.0','state':'bundled','abi':'arm64-v8a'}for n in ['git-remote-http','git-remote-https']},'inputs':inputs},indent=2)+'\n')
print('Prepared Git HTTP/HTTPS helper and',len(done)-1,'additional Android ARM64 libraries; phone execution pending')
