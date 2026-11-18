# Roadmap

## Phase 0 — Foundation
- [x] Create the standalone QWASAR project repository.
- [x] Establish the LÖVE/Lua UI shell.
- [x] Define a shared QWASAR visual identity for app and documentation.
- [x] Add optimized PNG wordmark, icon atlas and 640×480-target background artwork.
- [x] Add documentation cover, visual system graphic and screenshot evidence rules.
- [x] Add controller and keyboard navigation.
- [x] Add L1/R1 section cycling in the main navigation.
- [x] Add animated Comet boot splash, ambient motion and page-focus transitions.
- [x] Add M-key quick overlay and START + SELECT exit chord.
- [ ] Validate the updated controls and animations on the RG35XX H.

## Phase 1 — Device intelligence
- [x] Add a read-only device probe (Lua on-device; Python reference probe for host tests).
- [x] Detect architecture, model hints, firmware metadata and TF1/TF2 mount candidates.
- [x] Show unknown values honestly; refine confidence scoring after physical-device evidence.
- [x] Read TF1/TF2 total and available space with read-only statvfs when supported.
- [x] Report filesystem read-only state when available.
- [x] Add an opt-in, privacy-scoped diagnostics report export with Lua formatting tests.

## Phase 2 — Void Desk OS image setup
- [x] Select TF1 / TF2 from live detected mount candidates and reject missing/read-only targets.
- [x] Read live free space before image staging.
- [x] Look up only the dedicated `voiddesk-os-v*` release asset (never a Void Desk MUX app).
- [x] Stage the compressed Debian Trixie ARM64 + labwc full-disk image under `MUOS/CometDesk/OS-Staging/VoidDeskOS/`.
- [x] Verify published SHA-256 and exact size before atomic publication.
- [ ] Publish the actual Void Desk OS H700 disk image.
- [ ] Integrate install/boot hand-off with the verified H700 MultiBoot contract.
- [ ] Add rollback and interrupted-install recovery.
- [ ] Validate cold boot, device input, panel, audio, Wi-Fi, Bluetooth and return to muOS.

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
