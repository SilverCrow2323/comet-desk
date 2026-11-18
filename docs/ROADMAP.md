# Roadmap

## Phase 0 — Foundation
- [x] Create the standalone QWASAR project repository.
- [x] Establish the LÖVE/Lua UI shell.
- [x] Add controller and keyboard navigation.
- [x] Define safety and architecture boundaries.
- [ ] Validate the prototype on the RG35XX H.

## Phase 1 — Device intelligence
- [ ] Add a read-only device probe.
- [ ] Detect architecture, model hints, display and storage mounts.
- [ ] Show confidence and unknown values honestly.
- [ ] Add a diagnostics report export.

## Phase 2 — Desktop setup
- [ ] Select and validate a target storage location.
- [ ] Calculate required and available space.
- [ ] Stage payloads without changing the active system.
- [ ] Verify checksums and required files.
- [ ] Add rollback and interrupted-install recovery.
- [ ] Enable installation only after device-side tests.

## Phase 3 — Session manager
- [ ] Discover installed desktop sessions.
- [ ] Validate launch commands before displaying them.
- [ ] Start/stop sessions with clear status and logs.

## Phase 4 — Release engineering
- [ ] Implement a minimal, reproducible .muxapp builder.
- [ ] Validate archive layout, executable permissions and runtime dependencies.
- [ ] Add CI checks and release artifacts.
- [ ] Test on real hardware before publishing a stable release.

## Release rule

A feature is not complete because its screen exists. It is complete when the underlying operation is implemented, validated, safely fails, and has been tested on the target device.
