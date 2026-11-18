# Comet Desk Architecture

## Design goal

A small, quick-launching MUX application that coordinates desktop-related tasks on muOS. Comet Desk is deliberately not a second Void Desk: it reuses proven ideas, not the larger project's whole service surface.

## Runtime layers

1. **MUX entry point** — muOS launches the application through its MUX app mechanism.
2. **LÖVE shell** — Lua UI, controller navigation, screen scaling and page state.
3. **Capability layer** — small, explicit adapters for device facts and supported operations.
4. **Task layer** — staged setup/session/diagnostic workflows.
5. **Target storage** — user-selected destination for desktop payloads; never assumed.

## muOS package and runtime

The repository produces a self-contained `.muxapp` for every device-test build. The package includes the muOS `mux_launch.sh` lifecycle entry point, the LÖVE game, a read-only Lua device probe, and a pinned AArch64 LÖVE 11.5 runtime.

The launcher follows the muOS Andromeda application runner contract: it sources the shared helper, calls `SETUP_APP`, and uses `/run/muos/storage/application/CometDesk` so SD1/SD2 placement remains muOS-managed.

The builder rejects unsafe archive paths, symlinks, missing application/runtime files, wrong ELF architecture and a non-executable launcher. A successful package build is not proof of physical-device compatibility.

## Current prototype

- `love/main.lua`: navigation shell, Overview and Diagnostics rendering.
- `love/conf.lua`: LÖVE application metadata and 640×480 baseline.
- `love/device_probe.lua`: read-only model, SoC, architecture, RAM, firmware-marker and TF1/TF2 mount probe, including read-only statvfs capacity/free-space data when available.
- The Overview and Diagnostics screens display the live probe snapshot.
- Storage capacity/free-space and read-only state use LuaJIT FFI statvfs calls against already detected mounts; unavailable stats remain explicitly unavailable.
- No privileged installer or filesystem mutation is wired into the UI.

## Device profiles

A profile must be evidence-based and contain at least:

- device identifier / detected model (when available);
- architecture and SoC family;
- display dimensions and orientation;
- available input devices and button mapping;
- storage mount points and free space;
- supported graphics/runtime capabilities.

The H700 profile is the first validation target. A shared SoC does not automatically prove that every handheld has identical controls, display geometry or storage layout.

## Task execution contract

Every future operation should expose:

- preflight checks;
- exact source and destination;
- required free space;
- files and settings it will create or modify;
- backup/recovery strategy;
- progress and cancellation boundaries;
- post-install validation.

Operations should be idempotent where possible. A failed stage must leave a clear recovery state and must not report success.

## Void Desk learning boundary

Void Desk is the reference for lessons around LÖVE packaging, H700 runtime validation, controller-first UX and safe muOS integration. Comet Desk should keep its own compact code, dependency list and release pipeline.
