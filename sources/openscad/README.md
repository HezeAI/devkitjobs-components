# OpenSCAD for DevKitJob’s

Maintained by HezeAI, with Codex assistance. Optional download only; this component is not embedded in the DevKit APK.

The geometry engine is the **unmodified official OpenSCAD 2026.10.29 Node/WebAssembly snapshot**. A portable static ARM64 syscall launcher invokes Android's system shell and the APK's native ARM64 Node runtime. No Ubuntu, PRoot, X11, Docker, compiler or desktop GUI is needed to package or run this component on Android. This is not a native C++ OpenSCAD build.

## Reproduce the component

```sh
python3 sources/openscad/build.py --out build/openscad
python3 sources/openscad/test.py --out build/openscad-tests --manager "$DEVKIT_TOOLS/devkit-tools.py"
```

The builder downloads or accepts the exact public ZIP locked in `upstream.lock.json`, checks its size, archive hash and unchanged JavaScript hash, generates the portable ELF from `launcher.S`, and packages the complete engine with fixed file order, timestamps and permissions. No installed application data or credentials are inputs. Python 3.14.8 / native DevKit zlib is the verified reproduction environment; the test requires two independent builds to have identical bytes. `--upstream PATH` permits an offline build from the same hash-locked ZIP.

The builder emits `openscad-2026.10.29-wasm-node-r3-android-arm64.zip` and `openscad.json` with immutable GitHub release URL, archive/file SHA-256, ABI, provenance and functional activation probe. The archive includes the engine: installation and normal execution never fetch it separately from openscad.org. Node 26.12.1 is supplied by the APK. Android ARM64/API 29+ and DevKit target SDK 28 are the tested runtime. Failed installs retain the prior active manager version.

## Tests and scope

The activation probe executes actual version queries and renders cube, boolean difference and tapered extrusion fixtures to binary STL. It verifies dimensions, signed volume, finite coordinates, closed consistently oriented edges and no degenerate edges. Fixtures use millimetres by convention; STL itself has no units. Known analytic fixture thicknesses are 1 mm (cube), at least 1 mm (boolean base), and at least 2 mm (extrusion). These test geometry, not a material/printer-specific guarantee. Full C++/Emscripten compilation and desktop GUI, text/fonts, arbitrary third-party SCAD libraries and other runtimes are not claimed tested.

The package test covers byte-identical rebuilds, archive/file integrity, portable execution from independent paths, real manager activation, a failed update retaining the active version, independent CLI callers, fresh manager reload and invalid SCAD failure. `--download` additionally requires a real cold-cache install from the published release URL; local-archive tests alone do not claim that download passed.

Normal use:

```sh
devkit-tools install openscad
openscad --version
openscad --export-format=binstl -o model.stl model.scad
```

## Sources and licenses

See [SOURCE-OFFER.md](SOURCE-OFFER.md), [source-index.json](source-index.json), and `licenses/`. The engine source revision is confirmed by `--info`: **fe482c342ea48bbe749563315741d0e58cdfd57f**. The engine remains GPL-2.0-or-later; the combined distribution and new adaptation are conveyed under GPL-3.0-or-later, retaining dependency notices and exceptions. Public corresponding-source links and a supplementary verified source-access bundle accompany the binary release.

The reproducible claim covers our launcher and complete component packaging with the unchanged hash-pinned official engine. C++/Emscripten engine compilation on Android, desktop GUI, fonts/text and arbitrary third-party SCAD libraries are not claimed tested. Upstream Docker recipes are source/build documentation; DevKit does not execute Docker or a foreign Linux environment.
