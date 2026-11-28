# Project: Comet Desk

## Purpose
Provide a small, controller-first MUX companion for muOS handhelds. Comet Desk focuses on quick device diagnostics, session discovery and carefully staged desktop setup; it does not replace muOS or duplicate the full Void Desk environment.

## Users and use cases
- RG35XX H owners who need a lightweight device/session companion.
- Maintainers packaging and validating an installable muOS .muxapp.
- Contributors testing device probes, controller navigation and storage-safe workflows.

## Scope and boundaries
In scope: LÖVE 11.5/Lua UI, read-only device/storage probe, diagnostics export, session discovery, and a future staged desktop payload workflow with checksum and rollback controls.

Out of scope: bootloader changes, partitioning/formatting, automatic system replacement, arbitrary privileged shell execution, and claiming that a prototype screen means the underlying operation is implemented. Void Desk is a design/engineering reference, not a runtime dependency.

## Target
- Reference device: Anbernic RG35XX H, Allwinner H700, AArch64, 640×480, muOS Andromeda 2606.0.
- Runtime: LÖVE 11.5 with pinned AArch64 shared libraries.
- Development: Lua 5.1-compatible syntax, Python host tests and deterministic .muxapp packaging.

## Architecture
- LÖVE UI and controller/keyboard input.
- Read-only device probe for identity hints, memory and mounted storage.
- Package builder that stages the CometDesk/ tree and validates archive paths, runtime ELF architecture and launcher permissions.
- Future desktop/session services, kept unavailable until their operations and recovery paths are implemented.

## Dependencies and integration
The muOS MUX launcher contract and LÖVE 11.5 runtime are packaged with the app. The runtime source is pinned to a specific Void Desk/Dolphin Rt snapshot and checked by content hash. No dependency on Void Desk being installed is intended.

## Safety, accessibility and localization
Device probing remains read-only. Installation must require an explicit target, space preview, checksum verification, staging and rollback. Reject path traversal and archive symlinks. Controls must be reachable by D-pad/buttons and readable at 640×480. Do not claim hardware validation without a physical RG35XX H test.

## Verified baseline
The repository contains a LÖVE/Lua prototype, read-only device probe, package builder and host tests. CI builds an installable RG35XX H .muxapp artifact; physical device qualification remains open.
