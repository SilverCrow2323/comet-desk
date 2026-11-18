# COMET DESK

![Comet Desk — Industrial Cyberpunk identity](docs/assets/comet-desk-cover.svg)


**A fast, focused desktop companion for muOS — part of the QWASAR ecosystem.**

Comet Desk is a lightweight MUX application for supported ARM64 handhelds. It stages the separate Void Desk OS Debian ARM64 disk image for H700 devices, alongside device diagnostics and session-management work, without replacing muOS.

> **Project status:** Early test candidate. The first self-contained RG35XX H muOS `.muxapp` has been built by CI and its archive, AArch64 runtime payloads and SHA-256 checksum have been verified. Physical-device validation is the next gate.

## What it is

The app and documentation share one visual identity: industrial megastructure artwork, a restrained cyan/violet/amber palette, angular navigation marks and compact controller-first layouts. See the [visual identity guide](docs/VISUAL_IDENTITY.md) and [screenshot evidence policy](docs/SCREENSHOTS.md).


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
| Desktop Setup | Download the Void Desk OS Debian Trixie ARM64 + labwc disk image to selected TF1 / TF2 storage | Implemented release lookup/staging client; OS image release and MultiBoot hand-off are pending |
| Session Manager | View and launch installed sessions | Planned |
| System Tools | Storage and service utilities | Planned |
| Diagnostics | Live device/storage snapshot and opt-in privacy-safe report export | Implemented; CI/package checks pass; physical-device validation pending |

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

The app bundles its low-memory background, six-tile PNG icon atlas and transparent PNG wordmark; source artwork and documentation graphics live beside the project docs. The visual system is documented in [Visual identity](docs/VISUAL_IDENTITY.md).

Every device-test milestone is distributed as an installable `.muxapp`. The package builder pins and validates the AArch64 LÖVE runtime, includes the muOS launcher, and publishes a SHA-256 checksum with the GitHub Actions artifact. See [MUX App build and install](docs/MUXAPP_BUILD.md).

## Project relationship

```text
QWASAR
├── Void Desk OS  — Debian Trixie ARM64 + labwc H700 system image
├── Void Desk     — proprietary desktop shell and H700 integration
└── Comet Desk    — muOS MUX companion and OS image staging client
```

Void Desk OS is a separate full-system image, not a MUX application. Comet Desk looks only for the dedicated OS disk-image release asset; it never downloads the Void Desk application package as a desktop image.

## Reference hardware

The first target is the **Anbernic RG35XX H running muOS Andromeda 2606.0**: Allwinner H700, AArch64, 1 GB RAM, 640×480 display and a 64 GB nominal TF1 baseline. The 64 GB figure is a reference configuration, not a limit. TF1 replacements and optional TF2 expansion cards are discovered at runtime; installation sizing must use the selected filesystem's live free space.

- [RG35XX H device profile](docs/DEVICE_PROFILE.md)
- Device-side read-only probe: `love/device_probe.lua` (bundled in the MUX App).
- Python reference probe: `python3 service/device_probe.py` (host-side development checks).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Safety model](docs/SAFETY.md)\n- [Void Desk OS image contract](docs/OS_IMAGE_CONTRACT.md)
- [Visual identity](docs/VISUAL_IDENTITY.md)
- [Screenshot evidence guide](docs/SCREENSHOTS.md)
- [Asset inventory](assets/README.md)

All user-facing interface text and project documentation are written in English.
