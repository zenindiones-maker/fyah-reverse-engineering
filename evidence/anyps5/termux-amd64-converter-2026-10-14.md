# AnyPS5 — AMD64 converter test on Termux

Date: 2026-10-14

## Source and environment

- Source repository: https://github.com/boykopovar/AnyPS5
- Source branch: `main`
- Source commit tested: `a31043146e70a3e17232d6b1df4d6e993791d73b`
- Environment: Android / Termux / AArch64
- Build target: `amd64_only_converter_tests`
- Build directory: `~/.cache/anyps5-converter-tests`

## Test evidence

Command:

```sh
ctest --test-dir "$HOME/.cache/anyps5-converter-tests" --output-on-failure -R '^amd64_only_converter$'
```

Observed result:

```text
Start 42: amd64_only_converter
1/1 Test #42: amd64_only_converter ............. Passed 0.07 sec

100% tests passed, 0 tests failed out of 1
Total Test time (real) = 0.09 sec
```

Build target was already up to date when checked (`ninja ... amd64_only_converter_tests -j 1` reported `no work to do`). The executable existed at `~/.cache/anyps5-converter-tests/tests/amd64_only_converter_tests` and was reported as 5.8 MiB.

## Source integrity

- The temporary CMake adjustment was restored; `CMakeLists.txt` contains the original `elseif(NOT APPLE)` condition at line 60.
- The AnyPS5 source working tree was clean before the local evidence report was added.
- A local-only commit was created in the AnyPS5 checkout: `4d99c06` (`docs: record Termux AMD64 converter test result`). That local commit was not pushed to the upstream repository.

## Scope and limitations

This confirms only the `amd64_only_converter` unit test passed in this Termux build configuration. It does not demonstrate full PS5 compatibility, execution of a PS5 game, or successful Astro Bot launch. The test executable and build cache remain on the local Android device; they are not included in this report.
