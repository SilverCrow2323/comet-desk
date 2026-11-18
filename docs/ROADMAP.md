# Roadmap

## Phase 0 — Foundation
- [x] Create the standalone QWASAR project repository.
- [x] Establish the LÖVE/Lua UI shell.
- [x] Define a shared QWASAR visual identity for app and documentation.
- [x] Add optimized PNG wordmark, icon atlas and 640×480-target background artwork.
- [x] Add documentation cover, visual system graphic and screenshot evidence rules.
- [x] Add controller and keyboard navigation.
- [x] Define safety and architecture boundaries.
- [x] Add animated Comet boot splash, ambient motion and page-focus transitions.\n- [x] Add M-key quick overlay and START + SELECT exit chord.\n- [ ] Validate the prototype on the RG35XX H.

## Phase 1 — Device intelligence
- [x] Add a read-only device probe (Lua on-device; Python reference probe for host tests).
- [x] Detect architecture, model hints, firmware metadata and TF1/TF2 mount candidates.
- [x] Show unknown values honestly; refine confidence scoring after physical-device evidence.
- [x] Read TF1/TF2 total and available space with read-only statvfs when supported.
- [x] Report filesystem read-only state when available.
- [x] Add an opt-in, privacy-scoped diagnostics report export with Lua formatting tests.

## Phase 2 — Desktop setup
- [ ] Select and validate a target storage location.
- [ ] Calculate required and available space.
- [ ] Stage payloads without changing the active system.
- [ ] Verify checksums and required files.
- [ ] Add rollback and interrupted-install recovery.
- [ ] Add managed desktop-image provisioning and session launch only after device-side tests.

## Phase 3 — Session manager
- [ ] Discover installed desktop sessions.
- [ ] Validate launch commands before displaying them.
- [ ] Start/stop sessions with clear status and logs.

## Phase 4 — Release engineering
- [x] Implement a minimal, reproducible .muxapp builder.
- [x] Validate archive layout, executable permissions and AArch64 runtime dependencies.
- [x] Add CI checks and per-run installable package artifacts.
- [x] Produce and verify the first CI `.muxapp` candidate, including archive integrity, AArch64 ELF payloads, executable launcher, PNG dimensions and SHA-256 sidecar.
- [ ] Install and test on real hardware before publishing a stable release.

## Release rule

A feature is not complete because its screen exists. It is complete when the underlying operation is implemented, validated, safely fails, and has been tested on the target device.
