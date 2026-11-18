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

## Phase 2 — Integrated XFCE environment
- [x] Select TF1 / TF2 from live detected mount candidates and reject missing/read-only targets.
- [x] Check free space and reject symlinked storage paths.
- [x] Pin the existing Void Desk H700 XFCE ext4 image seed by size and Git blob checksum.
- [x] Download Ubuntu Base 24.04.3 ARM64 and verify its published size and SHA-256.
- [x] Expand the ext4 image and extract the root filesystem into it.
- [x] Install Xorg, XFCE and handheld input/audio packages inside the guest image.
- [x] Mount the desktop image, run its session directly and resume Comet Desk on return.
- [x] Track and verify loop device and bind-mount cleanup.
- [ ] Validate the integrated setup and session lifecycle on the RG35XX H.
- [ ] Add recovery UI for interrupted setup and unclean shutdown.

- [x] Add curved L1/R1 navigation with animated per-tab accent colours and directional page transitions.\n- [x] Add Uplink status for Wi-Fi, hotspot, Bluetooth and muOS Andromeda Web Services.\n- [x] Add checksum-pinned Rt:Tailscale-M install and RT-owned service discovery/actions.\n- [ ] Validate wireless telemetry and RT installation on the RG35XX H.\n\n## Phase 3 — Session manager
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
