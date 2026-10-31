# Corresponding source and license access

The component ZIP contains the unmodified official OpenSCAD engine and all source of the Android launcher, adapter, package builder and tests. The engine is not embedded in the DevKit APK. Installation and execution use the GitHub component archive, including its engine; neither requires a download from openscad.org.

Free corresponding-source access is offered alongside the binary through the public version-control repositories and source archives identified in `source-index.json`. OpenSCAD's exact source commit is fe482c342ea48bbe749563315741d0e58cdfd57f; geometry submodule revisions are pinned there. To obtain that tree and its submodules:

```sh
git clone https://github.com/openscad/openscad.git
git -C openscad checkout fe482c342ea48bbe749563315741d0e58cdfd57f
git -C openscad submodule update --init --recursive
```

The index links GPL/LGPL/MPL dependency source as well as permissive dependencies, and the upstream WASM build project with patches and CMake/Emscripten instructions. A separate source-access bundle in the same release mirrors verified dependency source archives and this index. It is supplementary: remaining source trees are available through their explicit public VCS links. No password or account is needed. Source access is provided under GPLv3 section 6(d), rather than a three-year written physical-media offer. The maintainer must keep corresponding-source access available while these binaries are distributed.

OpenSCAD is GPL-2.0-or-later; the combined distribution and the new adaptation are conveyed under GPL-3.0-or-later. Individual copyright notices, exceptions and dependency licenses remain in force. Full GPL/LGPL texts and upstream notices are in `licenses/`. The original engine is not relabelled as HezeAI-authored code.

The upstream WASM base uses some development refs. Eigen's 597 installed headers were compared byte for byte against the source commit in the index. The engine C++/Emscripten build has not been rerun here; reproducibility tests cover our packaging and portable launcher, with the unchanged official engine pinned by SHA-256. Do not interpret this as certification of a bit-identical upstream compiler rebuild or of desktop GUI support.

No accounts, keys, user projects or signing credentials are inputs or package contents.
