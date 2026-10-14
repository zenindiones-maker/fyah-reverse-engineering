# Android ARM64 compatibility layer — research specification

Status: SPECIFICATION ONLY. No executable compatibility layer exists yet.
Date: 2026-10-14

## Objective

Investigate the missing path between a PS5 executable-porting tool and a possible Android ARM64 host. The initial deliverable is a measurable compatibility probe, not an Astro Bot launcher.

## Architecture under investigation

1. **Input/format gate** — identify the exact input format and architecture from a lawful, unprotected test binary. Reject unknown formats explicitly. Do not decrypt, unwrap protected packages, or bypass access controls.
2. **Relinker boundary** — treat AnyPS5 output as Linux x86-64 unless upstream evidence proves otherwise. Never assume its current output is Android/ARM64 compatible.
3. **Execution-architecture gate** — determine whether Android can execute the produced ABI natively. If not, evaluate a lawful user-space x86-64 translation/emulation route as a separate component; do not conflate translation with PS5 system emulation.
4. **System API gate** — enumerate missing host APIs and guest imports. Fail closed on unresolved imports; no silent success or fake stub implementations for behavior required by the test.
5. **Graphics gate** — inventory Vulkan/OpenGL ES capabilities and driver version on the actual device. Separate API availability from feature coverage and performance.
6. **Input/audio gate** — later probe SDL/input and audio dependencies only after the basic executable-format and CPU gates pass.
7. **Evidence gate** — every stage emits machine-readable results with device, OS, ABI, tool versions, source commit, test case, exit status, and logs. A failed or skipped gate must remain visibly failed/skipped.

## First implementation milestone: Android host probe

Create a small, dependency-light native/Termux probe that reports:

- Android release, SDK, device model and supported ABIs;
- process architecture and whether an x86-64 translation environment is advertised;
- kernel and available memory;
- Vulkan loader/device/driver information when the relevant tools are already installed;
- presence of Termux packages/tools needed for a future native test build;
- explicit `UNKNOWN` when a property cannot be queried.

The probe must be read-only by default, run without root, avoid downloading/building on the phone, and save a timestamped report. No benchmark claims should be made from capability strings alone.

## Pass/fail sequence

- **P0 — Device facts:** reproducible inventory collected from the actual A15.
- **P1 — Build feasibility:** minimal native test executable builds on a remote ARM64 Android-compatible environment, or the precise blocker is documented.
- **P2 — Host execution:** that test executable runs on Android and emits a verified result.
- **P3 — x86-64 execution path:** an independently licensed test ELF runs under a documented user-space translation/emulation path, if technically and legally feasible.
- **P4 — Relinker interoperability:** a harmless test input accepted by AnyPS5 can execute through the established path, with all required imports accounted for.
- **P5 — Game-specific feasibility:** only after prior gates, assess documented Astro Bot blockers from lawful sources. This gate may fail; do not imply compatibility from generic tests.

## Constraints

- Do not copy upstream source into this repository; fetch it into a temporary workspace only when needed.
- Respect the upstream GPL-2.0-only license if modifying or redistributing AnyPS5.
- Do not download or redistribute game ROMs/packages, firmware, console keys, proprietary assets, or user data.
- No DRM, signature, encryption, or access-control bypass.
- No root requirement, paid service, or unbounded build on the Galaxy A15.
- No claim of “runs Astro Bot” without reproducible title-specific evidence.

## Immediate next actions

1. Run `scripts/ps5_android/collect_android_env.sh` on the actual device and commit only a redacted, user-approved report if desired.
2. Run the manual GitHub Actions preflight and preserve its artifact/logs.
3. Use an x86-64 remote runner for the upstream relinker-only tests; keep this separate from Android/ARM64 work.
4. Implement the first probe only after device inventory establishes the available route.
