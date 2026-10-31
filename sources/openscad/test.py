"""Real Android ARM64 package/manager validation, no account or running-chat access.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,tempfile,zipfile,re
from build import build,LOCK

def run(out,manager_script,upstream,download=False):
 out.mkdir(parents=True,exist_ok=True);first=build(upstream,out/'first');second=build(upstream,out/'second path')
 assert first==second and (out/'first'/first['archive']['url'].split('/')[-1]).read_bytes()==(out/'second path'/first['archive']['url'].split('/')[-1]).read_bytes(),'Non-reproducible archive'
 archive=out/'first'/first['archive']['url'].split('/')[-1]
 with zipfile.ZipFile(archive)as z:
  assert 'runtime/openscad.js' in z.namelist() and 'sources/download_engine.py' not in z.namelist()
  assert z.testzip()is None and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(first['files'])
  for name,data in first['files'].items():
   b=z.read(name);assert len(b)==data['bytes'] and hashlib.sha256(b).hexdigest()==data['sha256'];assert (b'/data/'+b'user/')not in b and (b'/data/'+b'data/')not in b,'Private runtime path in package'
 spec=importlib.util.spec_from_file_location('devkit_manager',manager_script);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 base=Path(os.environ['DEVKIT_BIN']).parent;fixture=Path(os.environ['DEVKIT_TOOLS'])/'.verification';fixture.mkdir(exist_ok=True)
 root=Path(tempfile.mkdtemp(prefix='openscad-',dir=fixture));catalog={'schema':1,'components':{'openscad':first}}
 (root/'catalog-bundled.json').write_text(json.dumps(catalog));manager=mod.Manager(root,base=base)
 receipt=manager.install('openscad',local_archive=None if download else archive);assert receipt['status']=='ready'
 binary=root/'versions/openscad'/LOCK['version']/'bin/openscad';env=manager.environment(first,binary.parent.parent);env.update(HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9',ALL_PROXY='http://127.0.0.1:9',NODE_USE_ENV_PROXY='1')
 def command(args):
  p=subprocess.run([str(binary),*args],env=env,capture_output=True,text=True,timeout=90);assert p.returncode==0,p.stderr[-1000:];return p.stdout+p.stderr
 assert 'OpenSCAD functional checks passed' in command(['--devkit-self-test'])
 # Two independent callers and a fresh Manager object; no running app chats are touched.
 a=subprocess.Popen([str(binary),'--version'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE);b=subprocess.Popen([str(binary),'--version'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 for p in [a,b]:
  stdout,stderr=p.communicate(timeout=30);assert p.returncode==0 and b'OpenSCAD'in stdout+stderr
 assert mod.Manager(root,base=base).check('openscad')['status']=='ready'
 before=(root/'active.json').read_bytes();bad=json.loads(json.dumps(first));bad['version']='2026.10.29-wasm-node-bad-test';bad['files']['runtime/run.cjs']['sha256']='0'*64
 try:manager.install('openscad',info=bad,local_archive=archive);raise AssertionError('Corrupt update activated')
 except mod.ToolError:pass
 assert (root/'active.json').read_bytes()==before;command(['--version'])
 with tempfile.TemporaryDirectory(prefix='openscad-syntax-',dir=fixture)as tmp:
  p=Path(tmp)/'bad.scad';p.write_text('this is not valid SCAD syntax !');result=subprocess.run([str(binary),'-o',str(Path(tmp)/'bad.stl'),str(p)],env=env,capture_output=True,timeout=30);assert result.returncode!=0 and not(Path(tmp)/'bad.stl').exists()
 report={'status':'passed','version':LOCK['version'],'archiveSha256':first['archive']['sha256'],'archiveBytes':first['archive']['bytes'],'platform':'Android ARM64 native Node + official WASM','reproduciblePackage':True,'archiveAndFileIntegrity':True,'coldNetworkInstall':download,'archiveIncludesEngine':True,'runtimeNetworkRequired':False,'geometryWithUnreachableProxies':True,'managerActivation':receipt,'functionalProbe':manager.check('openscad'),'independentCliCallers':2,'managerReload':True,'failedUpdateRetainedActive':True,'invalidScadRejected':True,'privatePathsInPackage':False,'cppEmscriptenRebuild':'not performed','installedAppGuiAndTwoChatUi':'not tested'}
 report=json.loads(re.sub(r'/data/'+r'(?:user|data)/[^\s\"\x27]+','<app-private>',json.dumps(report)))
 (out/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--manager',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);p.add_argument('--download',action='store_true');a=p.parse_args();run(a.out,a.manager,a.upstream,a.download)
