# Comet Desk Architecture

## Design goal

A small, quick-launching MUX application that coordinates desktop-related tasks on muOS. Comet Desk is deliberately not a second Void Desk: it reuses proven ideas, not the larger project's whole service surface.

## Runtime layers

1. **MUX entry point** — muOS launches the application through its MUX app mechanism.
2. **LÖVE shell** — Lua UI, controller navigation, screen scaling and page state.
3. **Capability layer** — small, explicit adapters for device facts and supported operations.
4. **Task layer** — staged setup/session/diagnostic workflows.
5. **Target storage** — user-selected destination for desktop payloads; never assumed.

## Current prototype

- `love/main.lua`: navigation shell and page rendering.
- `love/conf.lua`: LÖVE application metadata and 640×480 baseline.
- No privileged installer or filesystem mutation is currently wired into the UI.

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
