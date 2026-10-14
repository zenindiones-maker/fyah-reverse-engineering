# PS5 → Android compatibility lab (experimental)

**Goal:** investigate whether parts of the AnyPS5 PC-portability approach can be validated on Android, using measured evidence rather than assumptions. Astro Bot is the motivating target, not a claimed supported game.

## Safety and scope

- Research public source and metadata; do not download, bundle, or redistribute commercial games, console keys, firmware, or proprietary assets.
- This lab does not bypass DRM, console protections, encryption, or access controls.
- Do not copy third-party source into this repository. Upstream source is fetched into a temporary workspace by the manually triggered preflight workflow and is not committed or packaged.
- No claim that AnyPS5 runs on Android. Its current design target and dependencies must be verified from the exact upstream revision.
- No automatic full build: the first run only inventories source revision and available toolchain. Build steps are added only after requirements are verified.

## Current workflow

1. Run **PS5 Android lab preflight** manually in GitHub Actions.
2. Inspect the generated report and exact upstream commit.
3. On the Android device, run `scripts/ps5_android/collect_android_env.sh` in Termux and save its output as a workflow artifact or attach it to the lab notes. Review the output before sharing; it includes device and environment metadata.
4. Compare Android ABI, available graphics APIs/tools, memory and upstream build assumptions.
5. Choose a small, lawful, reproducible proof of concept before attempting any game-specific work.

## Success criteria

- Upstream commit and license are recorded.
- Toolchain and platform assumptions are backed by files or commands, not guesses.
- Device diagnostics are reproducible and reviewed for private information.
- Every test result is marked PASS, FAIL, BLOCKED, or NOT RUN with logs and environment details.
- A successful preflight is **not** evidence that a game runs.

## Upstream

- AnyPS5: https://github.com/boykopovar/AnyPS5
- Repository research note: [AnyPS5 research](../../docs/reverse-engineering/ps5/anyps5-research.md)

## Status

Scaffold only. No AnyPS5 build, Android execution, GPU compatibility test, or Astro Bot compatibility test has been performed yet.
