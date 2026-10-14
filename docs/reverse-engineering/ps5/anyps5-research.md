# PS5 Reverse-Engineering Research: AnyPS5

**Status:** research index only; no upstream source copied or executed here.  
**Repository scope:** `zenindiones-maker/fyah-reverse-engineering`  
**Research branch:** `work/ps5-anyps5-research-v1`

## Primary project: AnyPS5

- Upstream: https://github.com/boykopovar/AnyPS5
- Upstream declares GPL-2.0.
- Stated goal: port PS5 executables to native Linux/Windows formats using a relinker and implementations of system libraries, without a separate emulation runtime.
- Main research areas: executable relinking, system-library implementations, GPU shader translation, compatibility testing.

## Critical interpretation of status metrics

Upstream status graphics report separate coverage for system libraries and shader instructions. These are implementation-specific metrics; they do **not** mean the same percentage of commercial games works. Recognizing a shader instruction does not by itself prove correct translation and execution in every workload.

Do not repeat coverage, compatibility, or FPS claims without recording the exact upstream commit, test target, host hardware, drivers, commands, logs, and reproducible evidence.

## Separate project: console-side jailbreak research

- Relapse upstream: https://github.com/soniciso1/relapse

Relapse is a separate console-side exploit/jailbreak project. Do not conflate its firmware compatibility or payload support with AnyPS5's PC-side portability work. Verify claims directly against upstream source, releases, and documented tests.

## Repository constraints

This repository's established policy is **links only for third-party tools; do not copy third-party source code into this repository**. Respect licenses and terms, and analyze only material that is owned, licensed, or otherwise authorized. Do not break DRM or circumvent technical protections or encryption.

Accordingly, this record adds upstream links and a verification plan only. It does not vendor, patch, build, or execute AnyPS5 or Relapse, and it does not modify existing audio/video analysis workflows or the REA harness.

## Reproducibility checklist

- [ ] Record the exact upstream commit SHA and release/tag inspected.
- [ ] Read upstream architecture, build instructions, license, dependencies, and limitations.
- [ ] Confirm the meaning and date of each coverage metric from source or documented implementation.
- [ ] Identify a lawful, documented test target and compatible host environment.
- [ ] Reproduce the test and preserve logs, environment details, rendering correctness, and performance evidence.
- [ ] Keep untested claims explicitly marked as unverified.
- [ ] Reassess whether any proposed integration complies with this repository's links-only policy before implementation.

## Current assessment

**Classification:** experimental PS5-to-PC executable-portability research.  
**Not established:** general-purpose PS5 emulation, broad commercial-game compatibility, or a console jailbreak.  
**Next step:** inspect and pin the upstream commit, then evaluate claims from code and reproducible evidence before considering any integration.
