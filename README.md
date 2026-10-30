# DevKitJob’s native components

Android ARM64 components for DevKitJob’s, maintained by HezeAI. Native execution uses Android/Bionic; Ubuntu, PRoot and X11 are not required.

## Experimental compatibility

Downloaded executables require the experimental DevKit targetSdk 28 build. The app continues to compile against Android SDK 35. Package compatibility and archive integrity do not establish device execution: downloaded component activation, two-chat availability and restart persistence are pending tests on the developer’s phone. The original APK-embedded toolchain is retained in the previous full release and the core backup below.

## Components

| Component | Version | Download bytes | Dependencies |
|---|---|---:|---|
| GitHub CLI | 2.103.3-r1 | 14016689 | Android system libraries |
| OpenJDK 25 | 25.0.5-r1 | 147091352 | Android system libraries |
| Gradle | 9.5.0-r1 | 140362158 | jdk |
| Android SDK + APK builder | 35-36.0.0-r1 | 43449668 | jdk |
| Clang / LLVM | 21-r1 | 65999525 | Android system libraries |

Exact URLs, SHA-256 values, expanded file hashes, ABI, minimum Android API, commands and functional probes are recorded in [tools.json](tools.json) and [components.json](components.json). Published versioned assets are immutable. The stable `releases/latest/download/tools.json` endpoint is the app’s update catalog.

## Storage and activation

The app creates `files/tools` in its private storage. Known catalog packages appear in **Basic**; externally researched/adapted imports appear in **Downloaded**. Both use the same versioned storage and registry. Each install downloads to a cache, verifies the archive, rejects unsafe paths and links, verifies ELF/ABI and dependencies, and executes functional probes before atomic activation. Failed updates retain the previous active version. Active dependencies and old version directories are retained; no working chats are restarted.

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

## Validation

Archive hashes, complete entry manifests, ZIP integrity, ARM64 ELF headers and safe extraction are checked separately from functional execution. Unit tests cover corrupted downloads, traversal, protected command replacement, failed activation and registry persistence. Mocked registry tests are not evidence that downloaded native binaries execute on Android. Per-component functional activation must pass on the targetSdk 28 app before a component is marked ready.

AI development assistance: OpenAI Codex
