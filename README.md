# COMET DESK

**A fast, focused desktop companion for muOS — part of the QWASAR ecosystem.**

Comet Desk is a lightweight MUX application for supported ARM64 handhelds. It brings desktop setup, session management and device diagnostics into one controller-friendly interface without replacing muOS.

> **Project status:** Early foundation / prototype. Hardware installation workflows are not yet enabled.

## What it is

- A compact, standalone MUX app in the QWASAR family.
- Built with LÖVE 11.5 and Lua, informed by practical work on [Void Desk](https://github.com/SilverCrow2323/Void-Desk-Project).
- Designed around the muOS Andromeda experience and H700-class handhelds.
- Intentionally smaller in scope than Void Desk: quick to launch, quick to navigate, and focused on a few reliable jobs.

## First targets

- Anbernic RG35XX H (Allwinner H700, ARM64, 640×480).
- Related H700 devices will be added only after their display, controls and storage paths are verified.

## Initial modules

| Module | Purpose | Current state |
|---|---|---|
| Overview | Device/app landing screen | UI prototype |
| Desktop Setup | Guided desktop deployment | Planned; locked pending safety checks |
| Session Manager | View and launch installed sessions | Planned |
| System Tools | Storage and service utilities | Planned |
| Diagnostics | Read-only system and compatibility checks | Planned |

## Safety principles

1. muOS remains the host system; Comet Desk does not replace its boot chain.
2. Desktop payloads must use an explicitly selected target location.
3. No formatting, partitioning, deleting or overwriting without a clear preview and confirmation.
4. Installation must be staged, validated and recoverable.
5. Device-specific paths and capabilities must be detected, not guessed.
6. Until a workflow is implemented and tested, the UI must label it as unavailable rather than simulate success.

## Development

The current prototype is a pure LÖVE/Lua interface and can be opened on a desktop with LÖVE 11.5:

```sh
love love
```

The muOS .muxapp packaging/launcher integration is a separate milestone. It will be based on verified QWASAR/Void Desk packaging experience, with Comet-specific paths and dependencies — not by copying Void Desk wholesale.

## Project relationship

```text
QWASAR
├── Void Desk     — broader desktop environment and integration work
└── Comet Desk    — lightweight muOS MUX companion
```

Void Desk is the experience base, not a runtime dependency.

## Reference hardware

The first target is the **Anbernic RG35XX H running muOS Andromeda 2606.0**: Allwinner H700, AArch64, 1 GB RAM, 640×480 display and a 64 GB nominal TF1 baseline. The 64 GB figure is a reference configuration, not a limit. TF1 replacements and optional TF2 expansion cards are discovered at runtime; installation sizing must use the selected filesystem's live free space.

- [RG35XX H device profile](docs/DEVICE_PROFILE.md)
- Read-only probe: `python3 service/device_probe.py` (development/host inspection; device-side results require hardware validation).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Safety model](docs/SAFETY.md)

All user-facing interface text and project documentation are written in English.
