"""Copy public installed tool binaries into a relocatable, app-owned runtime.

Never copy configuration, credentials, caches, site-packages or existing projects.
Android executables and extension modules go in APK jniLibs, not writable assets.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = Path('/data/data/com.termux/files/usr')
PACKAGE = ROOT / '.tools/package-root/data/data/com.termux/files/usr'
INPUTS = json.loads((ROOT/'.verification/package-inputs.json').read_text())['packages'] if (ROOT/'.verification/package-inputs.json').exists() else {}

def pick(relative):
    candidate=PACKAGE/relative
    return candidate if candidate.exists() else PREFIX/relative
OUT = ROOT / 'app/src/main/jniLibs/arm64-v8a'
DATA = ROOT / '.tools/runtime-data'
ASSETS = ROOT / 'app/src/main/assets'
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)
manifest = {'schema': 1, 'binaries': {}, 'pythonExtensions': {}, 'javaLibraries': {}, 'libraries': {},
            'tools': {}, 'sources': [], 'notes': []}


def elf(blob):
    if blob[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', blob, 18)[0] != 183:
        raise ValueError('Expected a little-endian ARM64 ELF')
    start = struct.unpack_from('<Q', blob, 32)[0]
    width, count = struct.unpack_from('<HH', blob, 54)
    loads = []
    dynamic = None
    for i in range(count):
        offset = start + i * width
        kind = struct.unpack_from('<I', blob, offset)[0]
        file_offset, address = struct.unpack_from('<QQ', blob, offset + 8)
        file_size = struct.unpack_from('<Q', blob, offset + 32)[0]
        if kind == 1:
            loads.append((address, file_offset, file_size))
        if kind == 2:
            dynamic = (file_offset, file_size)
    tags = []
    strings = None
    if dynamic:
        for offset in range(dynamic[0], sum(dynamic), 16):
            tag, value = struct.unpack_from('<QQ', blob, offset)
            if not tag:
                break
            tags.append((tag, value, offset))
            if tag == 5:
                strings = next(pos + value - addr for addr, pos, size in loads
                               if addr <= value < addr + size)
    return strings, tags


def text(blob, offset):
    return bytes(blob[offset:blob.index(0, offset)]).decode()


def android_name(name):
    if name.endswith('.so'):
        return name
    result = re.sub(r'\.so\.([0-9.]+)$', lambda m: '_' + m.group(1) + '.so', name)
    if len(result) != len(name) or not result.endswith('.so'):
        raise ValueError('Cannot rename dependency: ' + name)
    return result


copied = {}
system = {'libc.so', 'libdl.so', 'libm.so', 'liblog.so', 'libandroid.so',
          'libz.so', 'libEGL.so', 'libGLESv2.so', 'libvulkan.so'}


def copy_elf(source, output_name):
    source = source.resolve()
    if output_name in copied:
        if copied[output_name] != source:
            raise ValueError('Library name collision: ' + output_name)
        return
    original = source.read_bytes()
    blob = bytearray(original)
    strings, tags = elf(blob)
    if output_name=='libjvm.so' and strings is not None:
        size=next(value for tag,value,_ in tags if tag==10)
        position=blob.find(b'dladdr\0',strings,strings+size)
        if position<0:raise ValueError('JVM relocation import is missing')
        blob[position:position+6]=b'dkaddr'
    if output_name=='libtool_codex.so':
        from relocate_codex import adapt_codex
        blob = bytearray(adapt_codex(bytes(blob)))
    dependencies = []
    if strings is not None:
        for tag, value, _ in tags:
            if tag == 1:
                dependencies.append(text(blob, strings + value))
        for tag, value, _ in tags:
            if tag in (1, 14):
                old = text(blob, strings + value)
                new = android_name(old)
                if old != new:
                    blob[strings + value:strings + value + len(old)] = new.encode()
            elif tag in (15, 29):
                old = text(blob, strings + value)
                if len(old) < len('$ORIGIN'):
                    raise ValueError('Insufficient RPATH string space')
                blob[strings + value:strings + value + len(old)] = b'$ORIGIN' + b'\0' * (len(old) - 7)
    destination = OUT / output_name
    destination.write_bytes(blob)
    destination.chmod(0o755)
    copied[output_name] = source
    manifest['libraries'][output_name] = {
        'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
        'sourceSha256': hashlib.sha256(original).hexdigest(),
        'needed': [android_name(name) for name in dependencies]}
    for name in dependencies:
        if name in system:
            continue
        candidates = [PACKAGE / 'lib' / name,PREFIX / 'lib' / name]
        candidates += list((PACKAGE / 'lib/jvm/java-25-openjdk/lib').glob('**/' + name))
        candidates += list((PREFIX / 'lib/jvm/java-21-openjdk/lib').glob('**/' + name))
        candidate = next((p for p in candidates if p.exists()), None)
        if not candidate:
            raise ValueError('Missing dependency: ' + name)
        copy_elf(candidate, android_name(name))


def tool(name, source, version):
    target = 'libcode-mode-host.so' if name == 'codex-code-mode-host' else 'libtool_' + name.replace('-', '_').replace('.', '_') + '.so'
    copy_elf(source, target)
    manifest['binaries'][name] = target
    manifest['tools'][name] = {'version': version, 'state': 'bundled', 'abi': 'arm64-v8a'}

if len(sys.argv)==3 and sys.argv[1]=='--tool':
    name=sys.argv[2]
    if not re.fullmatch('[a-z0-9_.+-]+',name):raise SystemExit('Invalid tool name')
    manifest=json.loads((ASSETS/'runtime-manifest.json').read_text())
    tool(name,pick('bin/'+name),INPUTS.get(name,{}).get('version','installed build'))
    (ASSETS/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Updated native tool and dependency closure:',name)
    raise SystemExit(0)


tools = [('python3', PREFIX / 'bin/python3.14', '3.14.8'),
         ('git', PREFIX / 'bin/git', '2.56.0'),
         ('clang', PREFIX / 'bin/clang', '21'),
         ('node', pick('bin/node'), INPUTS.get('nodejs',{}).get('version','installed build')),
         ('bash', PREFIX / 'bin/bash', 'installed build'),
         ('ssh', PREFIX / 'bin/ssh', '10.6p1'),
         ('ssh-keygen', PREFIX / 'bin/ssh-keygen', '10.6p1')]
rg = pick('bin/rg') if pick('bin/rg').exists() else ROOT / '.tools/ripgrep/data/data/com.termux/files/usr/bin/rg'
if rg.exists():
    tools.append(('rg', rg, '15.2.0'))
for name, source, version in tools:
    tool(name, source, version)

# A headless OpenJDK uses only app-owned libraries and a separately compiled JNI
# launcher, avoiding the original prefix-relative desktop Java launcher.
jdk=pick('lib/jvm/java-25-openjdk')
if jdk.exists():
    for source in jdk.rglob('*'):
        relative=source.relative_to(jdk)
        if not source.is_file() or relative.parts[0]=='bin':continue
        if source.suffix=='.so':
            if source.name in {'libawt_xawt.so','libjawt.so','libsplashscreen.so','libfontmanager.so'}:continue
            if source.name=='libjsig.so' and relative.parts[0:2]==('lib','server'):continue
            copy_elf(source,source.name)
            manifest['javaLibraries'][str(relative)]=source.name
        else:
            destination=DATA/'jdk'/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    for name in ['java','javac','jar','javap','keytool','gradle','apksigner','d8']:
        manifest['binaries'][name]='libtool_java.so'
        manifest['tools'][name]={'version':INPUTS.get('openjdk-25',{}).get('version','25') if name in ['java','javac','jar','javap','keytool'] else '9.5.0' if name=='gradle' else '36.0.0', 'state':'bundled','abi':'arm64-v8a'}
    gradle=Path('/data/data/com.termux/files/home/.gradle/wrapper/dists/gradle-9.5.0-bin/bvnork1r7n8i6kp5cnkibsc9q/gradle-9.5.0')
    shutil.copytree(gradle,DATA/'gradle',dirs_exist_ok=True)
    sdk=DATA/'android-sdk'
    installed_sdk=Path('/data/data/com.termux/files/home/Android/Sdk')
    (sdk/'platforms/android-35').mkdir(parents=True,exist_ok=True)
    shutil.copy2(installed_sdk/'platforms/android-35/android.jar',sdk/'platforms/android-35/android.jar')
    (sdk/'build-tools/36.0.0/lib').mkdir(parents=True,exist_ok=True)
    for name in ['d8.jar','apksigner.jar']:
        shutil.copy2(installed_sdk/'build-tools/36.0.0/lib'/name,sdk/'build-tools/36.0.0/lib'/name)
    shutil.copy2(installed_sdk/'build-tools/36.0.0/core-lambda-stubs.jar',sdk/'build-tools/36.0.0/core-lambda-stubs.jar')
    tool('aapt2',pick('bin/aapt2'),INPUTS.get('aapt2',{}).get('version','installed ARM64 build'))
    manifest['binaries']['devkit-build-apk']='libtool_buildapk.so'
    manifest['tools']['devkit-build-apk']={'version':'0.1.0','state':'bundled','abi':'arm64-v8a'}

codex = Path('/usr/local/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-arm64/vendor/aarch64-unknown-linux-musl/bin')
package = Path('/usr/local/lib/node_modules/@openai/codex/package.json')
version = json.loads(package.read_text())['version']
for name in ['codex', 'codex-code-mode-host']:
    tool(name, codex / name, version)

python = PREFIX / 'lib/python3.14'
for source in python.rglob('*'):
    relative = source.relative_to(python)
    if any(part in {'site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo'}
           for part in relative.parts):
        continue
    if source.is_file() and source.suffix not in {'.pyc', '.pyo'}:
        if source.suffix == '.so':
            target = 'libpyext_' + source.name.split('.')[0].lstrip('_') + '.so'
            copy_elf(source, target)
            manifest['pythonExtensions'][str(relative)] = target
        else:
            destination = DATA / 'python/lib/python3.14' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

headers = PREFIX / 'lib/clang/21/include'
if headers.exists():
    shutil.copytree(headers, DATA / 'clang/include', dirs_exist_ok=True)

certificates = Path('/etc/ssl/certs/ca-certificates.crt')
shutil.copy2(certificates, ASSETS / 'cacert.pem')
manifest['sources'] = [
    {'name': 'Codex', 'url': 'https://github.com/openai/codex', 'license': 'Apache-2.0'},
    {'name': 'Termux package builds', 'url': 'https://github.com/termux/termux-packages',
     'note': 'Public tool binaries, adapted RPATH/SONAME; upstream licenses apply'}]
with zipfile.ZipFile(ASSETS / 'runtime.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for source in sorted(DATA.rglob('*')):
        if source.is_file():
            archive.write(source, str(source.relative_to(DATA)))
(ASSETS / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('ARM64 executable/library count:', len(copied))
print('Uncompressed native bytes:', sum(p.stat().st_size for p in OUT.iterdir()))
print('Runtime data archive bytes:', (ASSETS / 'runtime.zip').stat().st_size)
