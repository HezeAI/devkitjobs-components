# Changelog

## native-2026-10-31-r1

Add optional OpenSCAD CLI adaptation with a portable Android ARM64 launcher, complete hash-pinned official engine included in our GitHub archive, complete adaptation sources, reproducible packaging, licenses and real manager/geometry tests. OpenSCAD is not embedded in the APK. Existing component archives and hashes are unchanged.

## native-2026-10-30-r1

Initial Android ARM64 component set: GitHub CLI, OpenJDK, Gradle, Android SDK/APK builder and Clang; immutable core recovery archive; integrity manifests, dependency metadata and adaptation sources. Downloaded execution in the targetSdk 28 app is experimental and pending device verification.

## 2026-10-31 native r2

Clang 21-r2 restores full Android C compile/link/run with pinned headers, compiler-rt and LLD. OpenSCAD r3 contains the full official WASM engine. Binary-bound builtin check receipts and deterministic package reproduction are documented in README. Existing unchanged component versions remain intact.
