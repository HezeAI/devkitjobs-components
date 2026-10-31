# Native component update

Clang 21-r2 fixes Android C headers, compiler runtime, linker and resource paths. The full OpenSCAD 2026.10.29-wasm-node-r3 archive includes the official unchanged engine; no official-site engine download is required at installation or launch. Catalog URLs and SHA-256 values are pinned. Existing unchanged components retain their immutable versions and archive URLs.

Native installation, update and functional checks run under the actual DevKit Android UID in disposable directories; app GUI, two chat windows and full Activity restart remain separate device acceptance. Clang links to current-device Bionic and does not promise cross-API NDK compatibility or C++ headers. Upstream licenses and public source access are retained. See README and validation assets.

Clang r2 requires DevKitJob’s 0.2.20-preview/versionCode 33 or a newer compatible manager. Byte-identical package reproduction and all six components in two real native Codex test processes passed; installed-app UI remains separate. [README](https://github.com/HezeAI/devkitjobs-components/blob/main/README.md) describes sources, licenses and validation limits.

AI development assistance: OpenAI Codex
