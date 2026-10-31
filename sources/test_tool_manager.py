"""Transactional registry tests. Mocked probes are not Android execution evidence."""
import importlib.util,json,hashlib,struct,tempfile,unittest,zipfile,os
from pathlib import Path
from unittest.mock import patch

SOURCE=Path(__file__).with_name('devkit-tools.py')
spec=importlib.util.spec_from_file_location('devkit_tools',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ManagerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.manager=m.Manager(self.base/'tools',self.base)
  self.env=patch.dict(os.environ,{'DEVKIT_TARGET_SDK':'28','DEVKIT_ANDROID_API':'36'});self.env.start()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def package(self,version='1',id='probe',extra=None):
  data=bytearray(64);data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',data,18,183);struct.pack_into('<H',data,54,56)
  data+=version.encode();archive=self.base/(id+'-'+version+'.zip')
  with zipfile.ZipFile(archive,'w')as z:z.writestr('bin/probe',data)
  info={'id':id,'version':version,'source':'https://example.org/source','title':'Probe','platform':'android','abi':'arm64-v8a','minAndroidApi':29,'commands':{'probe':{'path':'bin/probe','probe':['--version'],'expect':version}},'dependencies':{},'files':{'bin/probe':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'executable':True}},'archive':{'url':'https://example.org/probe.zip','bytes':archive.stat().st_size,'sha256':m.sha(archive)},'links':{}}
  if extra:info.update(extra)
  m.atomic(self.manager.bundled,{'schema':1,'components':{id:info}});return info,archive
 def passing(self,*a):return {'status':'ready','checkedAt':1,'checks':[{'mocked':True}]}
 def test_ready_only_after_functional_check(self):
  info,archive=self.package()
  with patch.object(self.manager,'probe',side_effect=m.ToolError('functional failure')):
   with self.assertRaises(m.ToolError):self.manager.install('probe',info,archive)
  self.assertEqual(self.manager.state()['components'],{})
  self.assertEqual(self.manager.listing()['components'][0]['status'],'broken')
  with patch.object(self.manager,'probe',side_effect=self.passing):self.manager.install('probe',info,archive)
  self.assertEqual(self.manager.state()['components']['probe']['version'],'1')
 def test_failed_update_retains_active_version(self):
  first,a=self.package()
  with patch.object(self.manager,'probe',side_effect=self.passing):self.manager.install('probe',first,a)
  second,b=self.package('2')
  with patch.object(self.manager,'probe',side_effect=m.ToolError('broken update')):
   with self.assertRaises(m.ToolError):self.manager.install('probe',second,b)
  self.assertEqual(self.manager.state()['components']['probe']['version'],'1')
  self.assertTrue(self.manager.version_path('probe','1').is_dir())
 def test_corrupt_archive_never_published(self):
  info,a=self.package();a.write_bytes(a.read_bytes()+b'corrupt')
  with self.assertRaises(m.ToolError):self.manager.install('probe',info,a)
  self.assertEqual(self.manager.state()['components'],{})
 def test_traversal_and_duplicate_entries_rejected(self):
  info,a=self.package()
  for name in ['../outside','/tmp/escape','bin/../escape','bin\\escape']:
   with self.assertRaises(m.ToolError):m.child(self.manager.root,name)
  with zipfile.ZipFile(a,'a')as z:z.writestr('../escape',b'bad')
  info['archive'].update(bytes=a.stat().st_size,sha256=m.sha(a))
  with self.assertRaises(m.ToolError):self.manager.install('probe',info,a)
  self.assertFalse((self.base/'escape').exists())
 def test_target35_and_wrong_abi_rejected(self):
  info,a=self.package()
  with patch.dict(os.environ,{'DEVKIT_TARGET_SDK':'35'}):
   with self.assertRaises(m.Incompatible):self.manager.install('probe',info,a)
  info['abi']='x86_64'
  with self.assertRaises(m.Incompatible):self.manager.install('probe',info,a)
 def test_builtins_cannot_be_replaced(self):
  info,a=self.package();m.atomic(self.manager.root/'builtin.json',{'binaries':{'probe':'protected.so'},'tools':{}})
  with self.assertRaises(m.ToolError):self.manager.install('probe',info,a)
 def test_restart_and_second_manager_share_registry(self):
  info,a=self.package()
  with patch.object(self.manager,'probe',side_effect=self.passing):self.manager.install('probe',info,a)
  peer=m.Manager(self.manager.root,self.base)
  self.assertEqual(peer.state(),self.manager.state())
  self.assertEqual(peer.listing()['components'][0]['status'],'ready')
  (peer.version_path('probe','1')/'bin/probe').chmod(0o600)
  (peer.version_path('probe','1')/'bin/probe').write_bytes(b'damaged')
  self.assertEqual(peer.listing()['components'][0]['status'],'broken')
 def test_builtin_receipt_is_bound_to_apk_binary_not_only_version(self):
  binary=self.base/'bin/probe';binary.parent.mkdir(exist_ok=True);binary.write_bytes(b'public fixture binary')
  expected=m.sha(binary);manifest={'binaries':{'probe':'probe.so'},'libraries':{'probe.so':{'sha256':expected}},'tools':{'probe':{'version':'same'}}};m.atomic(self.manager.root/'builtin.json',manifest)
  receipt=self.manager.root/'checks/builtin-probe'
  m.atomic(receipt,{'id':'probe','version':'same','status':'ready','binarySha256':expected,'binaryPath':str(binary.resolve())})
  self.assertEqual(self.manager.builtin()[0]['status'],'ready')
  manifest['libraries']['probe.so']['sha256']='0'*64;m.atomic(self.manager.root/'builtin.json',manifest)
  self.assertEqual(self.manager.builtin()[0]['status'],'downloaded')
  manifest['libraries']['probe.so']['sha256']=expected;m.atomic(self.manager.root/'builtin.json',manifest)
  m.atomic(receipt,{'id':'probe','version':'same','status':'ready'})
  self.assertEqual(self.manager.builtin()[0]['status'],'downloaded')
 def test_unregistered_directory_is_not_ready(self):
  (self.manager.root/'versions/made-up/1').mkdir(parents=True)
  self.package();self.assertEqual(self.manager.listing()['components'][0]['status'],'not_installed')
 def test_non_android_loader_is_incompatible(self):
  info,a=self.package();interpreter=b'/lib/ld-linux-aarch64.so.1\0';data=bytearray(120)+interpreter;data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',data,18,183);struct.pack_into('<Q',data,32,64);struct.pack_into('<HH',data,54,56,1);struct.pack_into('<I',data,64,3);struct.pack_into('<Q',data,72,120);struct.pack_into('<Q',data,96,len(interpreter))
  with zipfile.ZipFile(a,'w')as z:z.writestr('bin/probe',data)
  info['files']['bin/probe'].update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest());info['archive'].update(bytes=a.stat().st_size,sha256=m.sha(a))
  with self.assertRaises(m.Incompatible):self.manager.install('probe',info,a)

if __name__=='__main__':unittest.main()
