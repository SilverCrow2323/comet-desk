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

## Phase 2 — Debian Trixie ARM64 desktop
- [x] Pin Debian GNU/Linux 13 (Trixie) ARM64 rootfs by immutable source commit, exact size and SHA-256.
- [x] Build one persistent ext4 rootfs with APT and a minimal H700-oriented base.
- [x] Install labwc as the default lightweight Wayland profile.
- [x] Add optional XFCE, LXDE, LXQt, IceWM, Fluxbox and Openbox profiles to the same rootfs.
- [x] Serialize setup, package operations and session launches with a shared Debian lock.
- [x] Keep muOS as host: no boot-chain, raw-device or host APT changes.
- [ ] Validate labwc DRM/KMS and X11 framebuffer sessions on the RG35XX H.

## Phase 2.1 — THE FORGE
- [x] Add a curated Debian ARM64 catalogue grouped by handheld input, desktop, development, media, network and utilities.
- [x] Add package search, live dpkg/APT availability, install, remove and index refresh operations.
- [x] Enforce an allowlist and filter host/init/bootloader/kernel/firmware and heavyweight app-store packages.
- [x] Add disabled Input Leap entry pending a trustworthy Debian Trixie ARM64 package source.
- [x] Keep the first-boot Debian desktop baseline lean; automatically bootstrap labwc when no ready guest exists.
- [x] Show bootstrap, profile and APT package tasks in a dedicated console with apt/dpkg-reported progress.
- [x] Cache package/application catalogue filtering instead of rebuilding long selectable lists every frame.
- [ ] Validate package dependencies and actual installation/removal on the RG35XX H.
- [x] Discover installed Debian .desktop applications and create an atomic Comet app catalogue.
- [x] Validate executable paths and launch arguments within the Debian rootfs; reject shell/privilege wrappers.
- [x] Launch one selected application under a Comet-supervised desktop session and return to Comet when it exits.
- [ ] Validate GUI application startup, input/audio, application exit and mount cleanup on the RG35XX H.

## Phase 3 — Session and application manager
- [x] Replace the placeholder Session Manager tab with APP DECK.
- [x] Scan freedesktop application entries from the selected Debian rootfs.
- [x] Filter unsafe, hidden, terminal-only and externally resolved executables.
- [x] Search and filter applications by category.
- [x] Route launches through the Comet supervisor; restore Comet after the application exits.
- [x] Add the global M Quick Panel to labwc and X11 sessions, including a supervised return-to-Comet request.
- [ ] Add explicit desktop-profile discovery and per-app launch preferences.
- [ ] Add DBus activation and terminal application support after session-bus supervision is validated.
- [ ] Validate display/session lifecycle and process cleanup on the RG35XX H.

## Phase 4 — Release engineering
- [x] Implement a minimal, reproducible .muxapp builder.
- [x] Validate archive layout, executable permissions and AArch64 runtime dependencies.
- [x] Add CI checks and per-run installable package artifacts.
- [x] Produce and verify the first CI `.muxapp` candidate, including archive integrity, AArch64 ELF payloads, executable launcher, PNG dimensions and SHA-256 sidecar.
- [ ] Install and test on real hardware before publishing a stable release.

## Release rule

A feature is not complete because its screen exists. It is complete when the underlying operation is implemented, validated, safely fails, and has been tested on the target device.
