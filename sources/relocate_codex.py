"""Adapt the pinned Codex helper basename to Android's installed library naming.

Codex 0.164.0 resolves the helper beside /proc/self/exe, ignoring PATH. Android
extracts only lib*.so from jniLibs. Keep the replacement the same byte length so
ELF offsets and Rust string lengths stay valid. Do not alter execution policy.
"""
from pathlib import Path
import hashlib
import json
import shutil

ORIGINAL = b'codex-code-mode-host'
INSTALLED = b'libcode-mode-host.so'
EXPECTED_OCCURRENCES = 3  # Pinned upstream 0.164.0 aarch64-musl release.


def adapt_codex(blob):
    if len(ORIGINAL) != len(INSTALLED):
        raise ValueError('Helper basename must preserve Rust string lengths')
    if blob.count(ORIGINAL) != EXPECTED_OCCURRENCES or INSTALLED in blob:
        raise ValueError('Unexpected Codex build: re-audit upstream helper lookup')
    return blob.replace(ORIGINAL, INSTALLED)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    source = Path('/usr/local/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-arm64/vendor/aarch64-unknown-linux-musl/bin')
    native = root / 'app/src/main/jniLibs/arm64-v8a'
    manifest_path = root / 'app/src/main/assets/runtime-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest['tools']['codex']['version'] != '0.164.0':
        raise ValueError('Re-audit helper lookup before changing Codex version')
    code = adapt_codex((source / 'codex').read_bytes())
    (native / 'libtool_codex.so').write_bytes(code)
    (native / 'libtool_codex.so').chmod(0o755)
    host = INSTALLED.decode()
    shutil.copy2(source / ORIGINAL.decode(), native / host)
    old = manifest['binaries']['codex-code-mode-host']
    manifest['binaries']['codex-code-mode-host'] = host
    manifest['libraries'][host] = manifest['libraries'].pop(old)
    manifest['libraries']['libtool_codex.so']['sha256'] = hashlib.sha256(code).hexdigest()
    if old != host:
        (native / old).unlink()
    manifest['notes'].append('Codex 0.164.0 helper basename adapted in-place to libcode-mode-host.so; native helper remains installed read-only and pipe-owned by Codex.')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Adapted Codex helper discovery; installed helper:', host)
