# DevKitJob’s native components

Android ARM64 components for DevKitJob’s, maintained by HezeAI. Native execution uses Android/Bionic; Ubuntu, PRoot and X11 are not required.

## Experimental compatibility

Downloaded executables require the experimental DevKit targetSdk 28 build. The app continues to compile against Android SDK 35. Package compatibility and archive integrity do not establish device execution: native component activation is tested under the real DevKit Android UID in isolated app-like directories. Two actual chat windows and full app restart remain separate phone UI checks. The original APK-embedded toolchain is retained in the previous full release and the core backup below.

## Components

| Component | Version | Download bytes | Dependencies |
|---|---|---:|---|
| GitHub CLI | 2.103.3-r1 | 14016689 | Android system libraries |
| OpenJDK 25 | 25.0.5-r1 | 147091352 | Android system libraries |
| Gradle | 9.5.0-r1 | 140362158 | jdk |
| Android SDK + APK builder | 35-36.0.0-r1 | 43449668 | jdk |
| Clang / LLVM (Android C) | 21-r2 | 73483071 | Android system libraries |
| [OpenSCAD CLI](sources/openscad) | 2026.10.29-wasm-node-r3 | 4824609 | APK Node/Python; Android system shell |

Exact URLs, SHA-256 values, expanded file hashes, ABI, minimum Android API, commands and functional probes are recorded in [tools.json](tools.json) and [components.json](components.json). Published versioned assets are never overwritten with different bytes. The stable `releases/latest/download/tools.json` endpoint is the app’s update catalog.

## Storage and activation

The app creates `files/tools` in its private storage. Known catalog packages appear in **Basic**; externally researched/adapted imports appear in **Downloaded**. Both use the same versioned storage and registry. Each install downloads to a cache, verifies the archive, rejects unsafe paths and links, verifies ELF/ABI and dependencies, and executes functional probes before atomic activation. Failed updates retain the previous active version. Active dependencies and local old version directories are retained during verification; no working chats are restarted. Superseded release archives are removed only after clean installation and upgrade checks pass; still-referenced archives remain available.

A folder name never implies readiness. Status values distinguish downloaded, ready, broken and incompatible. The app observes registry changes and refreshes the open tools screen. Catalog updates are explicit, and a new catalog entry alone never executes or installs a binary.

```sh
devkit-tools list
devkit-tools catalog
devkit-tools install gh
devkit-tools check gh
devkit-tools updates
```

Extra official-source adaptations may be registered through `devkit-tools import DESCRIPTOR.json ARCHIVE.zip`; the descriptor must include provenance, Android ARM64 compatibility, dependencies, complete file hashes and executable functional probes. Existing APK core commands cannot be replaced by an import.

## Sources and licenses

These archives redistribute the public, already adapted tool payloads from DevKitJob’s. Upstream licenses apply per file; this repository does not relicense third-party binaries. See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt), [licenses](licenses), and notices embedded in each archive. OpenJDK legal files and Gradle distribution notices are retained. Public adaptation/launcher sources and the original runtime hash manifest are in [sources](sources).

- GitHub CLI: https://github.com/cli/cli (MIT), Android package metadata in `sources/gh-termux-package.json`; dynamic RUNPATH is adapted to `$ORIGIN`.
- OpenJDK and Android ARM64 package recipes: https://github.com/termux/termux-packages/tree/master/packages/openjdk-25 .
- Clang/LLVM Android package recipes: https://github.com/termux/termux-packages/tree/master/packages/clang .
- Gradle: https://gradle.org/releases/ .
- Android SDK/build tools: https://developer.android.com/tools .
- Core: Codex https://github.com/openai/codex ; Termux package recipes https://github.com/termux/termux-packages ; full license/source credits in the third-party notice.

The bootstrap backup preserves the APK core payload for recovery and source correspondence; it is not offered as an automatic core replacement. No account files, private keys, signing credentials, user chats or projects are included.

The APK core also includes the Git HTTP/HTTPS remote helper and its Android libcurl/nghttp2/nghttp3/ngtcp2/libssh2 dependency closure. Exact public package checksums are in `sources/git-http-package-inputs.json`; the adaptation is in `sources/prepare_git_http.py`. Ordinary Git HTTPS ls-remote, fetch and authenticated push now pass under the DevKit UID after correcting the compiled shell defaults in both Git and its HTTP helper. Local commit/hook/push/clone and a fake credential-helper scenario also pass; no GitHub API workaround is required. Upstream projects: https://curl.se/ , https://nghttp2.org/ , https://github.com/ngtcp2/ngtcp2 , https://www.libssh2.org/ .

## Validation

Archive hashes, complete entry manifests, ZIP integrity, ARM64 ELF headers and safe extraction are checked separately from functional execution. Unit tests cover corrupted downloads, traversal, protected command replacement, failed activation and registry persistence. Mocked registry tests are not evidence that downloaded native binaries execute on Android.

OpenSCAD r3 was actually packaged twice with identical bytes and activated by the real manager on Android ARM64/API 36, target SDK 28. Three STL geometry fixtures, independent CLI callers, manager reload, ZIP/file integrity and failed-update rollback passed. The engine is official WASM running on native Node; it is included unmodified in our complete component ZIP. Catalog installation downloads only our immutable GitHub archive; running the tool requires no engine download from the official site. See [adaptation and test instructions](sources/openscad), [source/license access](sources/openscad/SOURCE-OFFER.md) and [local validation](VALIDATION-OpenSCAD-local.json). Cold-cache installation from the published release URL passed; see [network validation](VALIDATION-OpenSCAD-network.json). Installed app UI, two actual chat windows and full app restart are separate phone checks. Per-component functional activation must pass on the targetSdk 28 app before a component is marked ready.

AI development assistance: OpenAI Codex

## Native adaptation corrections (2026-10-31)

Clang 21-r2 supplies the missing Android C headers, compiler-rt builtins and LLD, and the manager explicitly configures its app-owned resource directory and sysroot. Activation compiles, links and executes a stdio C fixture. It links to the current device Android Bionic libraries in `/system/lib64`; C++ standard-library headers and cross-API binary compatibility are not claimed. Public input hashes and recipes are in `sources/clang-package-inputs.json` and `sources/prepare_clang_component.py`. Apache/LLVM and NDK header notices are preserved in the package.

The APK core shell adaptation is documented in `sources/adapt_core_shells.py`. Git local transport command registration and the candidate runtime hashes are in `sources/native-runtime-additions.json`. Python's `subprocess.py` default shell is corrected while repacking the APK-owned standard library; no user account files are inputs. Java subprocesses, default CA roots, a real Gradle Exec task and a small signed Android APK build have been tested in disposable directories. Exact final-APK acceptance is separate from these package checks.


Clang 21-r2 requires the manager shipped in DevKitJob’s 0.2.20-preview (versionCode 33) or newer: earlier managers do not configure the new functional profile. The APK-update scenario was tested by installing r1 with the prior manager in an isolated profile, replacing the manager with the candidate version, then updating to r2 and compiling/linking/running a C program. The old active local directory is retained during verification.

The immutable r2 ZIP is reproducible with `python3 sources/reproduce_clang_r2.py --archive clang-21-r2-android-arm64.zip --out reproduction` (Python 3.14, direct access to the hash-locked public package inputs, or `--inputs` for a local cache). The helper reconstructs the old public base from unchanged files retained in r2, so removal of the obsolete r1 release ZIP does not break reproduction. This reproduces packaging and adaptation, not an upstream LLVM rebuild; the resulting SHA-256 was verified byte for byte.

The published manager source and its focused tests are available as `sources/devkit-tools.py` and `sources/test_tool_manager.py`. Builtin readiness receipts now bind both the expected binary SHA-256 and resolved binary path; a stale successful check for the same version string cannot mark a replaced APK binary ready.
