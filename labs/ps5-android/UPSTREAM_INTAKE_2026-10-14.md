# AnyPS5 upstream intake — Android/Astro Bot feasibility

Date: 2026-10-14

## Upstream snapshot inspected

- Repository: https://github.com/boykopovar/AnyPS5
- Upstream default branch: `main`
- Inspected commit: `a5f493f90dca348a65561aed4bb325a629d1b668`
- License reported by GitHub: GPL-2.0-only
- Upstream description: automatic porting of PS5 executables to Linux and Windows.
- This note records metadata and findings only. It does not vendor or redistribute upstream source, game files, firmware, keys, or proprietary assets.

## What the upstream project actually does

AnyPS5 describes a relinker plus implementations of PS5 system PRX libraries. Its documented output is a native Linux ELF or Windows PE executable; the project explicitly says the converted program runs as a normal process, not through emulation or a separate runtime process. The browser-based web converter is a relinker UI, not a PS5 emulator or a game-streaming service.

The documented input is a clean ELF executable plus its bundled ELF modules in `sce_module/`, `sce_modules/`, or `prx/`. The usage guide says SELF/fSELF containers are skipped with a warning. That matters because an ordinary retail PS5 game package is not established by these docs as a ready-to-convert clean ELF.

## Android / Galaxy A15 compatibility assessment

**Current result: NOT DEMONSTRATED; do not claim Astro Bot runs on Android.**

- The upstream build guide lists x86-64 as a full-build requirement and describes Linux/Windows outputs. It does not document Android/ARM64 as a supported target.
- The relinker-only mode still produces x86-64 Linux ELF or Windows PE output; its docs say execution needs a compatible x86-64 host.
- The full build relies on CMake, Ninja, C++20 and numerous native graphics/audio dependencies, with Vulkan and SDL among them. The upstream submodules include SDL2, Vulkan-Headers, SPIRV-Headers/Tools, glslang, FFmpeg-related code, FreeType and others.
- Therefore, the browser relinker or a successful Linux build alone would not prove the converted game can execute on an ARM64 Android phone. A separate Android-compatible execution/translation path and game-specific compatibility evidence would be required.
- No upstream evidence inspected here establishes Astro Bot compatibility. Treat it as a test target, not a supported title.

## Safe next experiment

1. Capture the actual Android/Termux device inventory with `scripts/ps5_android/collect_android_env.sh` (read-only; no root and no package installation).
2. Run the repository's manual preflight workflow on GitHub Actions to record upstream commit, build metadata and license information into a temporary workspace.
3. First validate only the smallest independent relinker build in an x86-64 Linux Codespace/runner, using upstream instructions and tests. Do not attempt a full game build or download game content at this stage.
4. Separately evaluate whether any clean, lawfully obtained test ELF can be used for a non-game interoperability test. Do not bypass access controls or extract protected game content.
5. Only discuss Android execution after architecture, graphics driver, ABI, system-library and title-specific gates have evidence.

## Reproducibility and limits

The upstream repository metadata and text files were inspected through GitHub's public API/raw-file endpoints at the pinned commit above. A direct `git clone` from this execution environment failed because DNS/network access to `github.com` was unavailable. Consequently, **no local clone, build, Android device scan, or GitHub Actions run has been completed in this step**. The repository's preflight workflow remains the intended way to produce a runner-side report; it has not yet been dispatched.

## Upstream references

- Repository and license: https://github.com/boykopovar/AnyPS5
- Build guide: https://github.com/boykopovar/AnyPS5/blob/a5f493f90dca348a65561aed4bb325a629d1b668/docs/dev/BUILD.md
- Usage / input format: https://github.com/boykopovar/AnyPS5/blob/a5f493f90dca348a65561aed4bb325a629d1b668/docs/user/USAGE.md
- Architecture: https://github.com/boykopovar/AnyPS5/blob/a5f493f90dca348a65561aed4bb325a629d1b668/docs/dev/ARCHITECTURE.md
- CMake dependencies: https://github.com/boykopovar/AnyPS5/blob/a5f493f90dca348a65561aed4bb325a629d1b668/cmake/SystemDeps.cmake
