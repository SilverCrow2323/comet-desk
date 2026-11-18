# Comet Desk — muOS MUX App build

Every milestone intended for physical RG35XX H testing must produce a complete `.muxapp`. A desktop-only run is never reported as a handheld test.

## Package contract

The builder creates one ZIP-compatible `.muxapp` with exactly one top-level directory:

```text
CometDesk/
├── mux_launch.sh
├── love/
│   ├── main.lua
│   ├── conf.lua
│   ├── theme.lua
│   ├── device_probe.lua
│   └── diagnostics_report.lua
├── service/
│   └── desktop_environment.py
├── assets/
│   ├── backgrounds/comet-dashboard-640x480.png
│   ├── branding/comet-desk-logo.png
│   └── icons/comet-desk-atlas.png
├── lib/
│   ├── love
│   ├── liblove-11.5.so
│   └── libluajit-5.1.so.2
└── data/
```

The AArch64 launcher and LuaJIT runtime are fetched from a pinned Void Desk commit; the LÖVE 11.5 shared library comes from the Dolphin RT Core runtime source pinned to commit `cb11b977364dc88c82259fa259434bad682c6f81`. All three are checked as 64-bit little-endian AArch64 ELF, and the LÖVE shared library also has a pinned Git blob checksum. The package includes the read-only Lua device probe, opt-in diagnostic report exporter, canonical theme tokens, a palette-limited 640×480 background and a compact transparent icon atlas; the validator rejects missing application/runtime files, unsafe paths, symlinks, wrong ELF architecture and a non-executable launcher.

The launcher follows the muOS Andromeda application runner contract: it sources `/opt/muos/script/var/func.sh`, calls `SETUP_APP`, and uses the runtime application path `/run/muos/storage/application/CometDesk`. It does not hard-code SD1/SD2 mount roots.

## Get the CI package

Every push, pull request and manual workflow run builds a package after the Lua and Python checks pass. Open the repository's **Actions** tab, select the **Project checks and device package** run, then download the `CometDesk-muOS-Andromeda-RG35XX-H` artifact. It contains the `.muxapp` and matching SHA-256 sidecar.


## Integrated XFCE environment

The Desktop Setup page builds the desktop environment inside Comet Desk. It uses the exact XFCE image seed pinned from the Void Desk H700 source (assets/xfce.img.gz) and the Ubuntu Base 24.04.3 ARM64 root filesystem. The currently inspected Void Desk bootstrap uses Ubuntu Base 24.04.3 (Noble), not Debian Trixie; Comet keeps that verified base/profile consistent rather than silently relabelling it.

Comet downloads the 4,181,220-byte image seed and verifies its Git blob SHA-1, downloads the 29,865,086-byte Ubuntu Base archive and verifies its SHA-256, expands the 4 GiB ext4 image, extracts the ARM64 root filesystem into it, and installs the XFCE/Xorg/input/audio packages. The environment is stored on the selected TF1/TF2 card at MUOS/CometDesk/Desktop/. The image is loop-mounted only while Comet is preparing or running the session.

No external MUX app or installer is called. The MUX launcher supervises Comet: when the user starts XFCE, Comet's own UI exits to release the framebuffer, the same launcher invokes Comet's integrated session manager, and the UI is reopened after XFCE exits. The desktop uses the existing muOS kernel and host devices; it is not a second bootable OS.

The helper rejects missing or read-only target mounts, symbolic-link paths, insufficient free space, unexpected asset sizes, checksum mismatches and unverified loop/mount state. It does not format or repartition cards, flash raw devices, change muOS boot files or replace the active firmware. The mount tree and loop device are cleaned up on return; any cleanup failure remains visible in the status file and log.

Controls: **L1 / R1** cycle navigation tabs, **A / Enter** installs XFCE or launches the prepared session, **Left / Right** selects TF1/TF2, **M** opens the Comet quick overlay while Comet is active, and **START + SELECT** exits Comet Desk.

## Visual assets

The app uses the same palette and navigation icons documented in [Visual identity](VISUAL_IDENTITY.md). Artwork is palette-limited and scaled for the 640×480 H700 target. The background is decorative only: all status text and controls remain live UI elements drawn by the app.

## Diagnostic report export

On the Diagnostics page, press **Y** on the handheld (or **E** on a keyboard) to write a timestamped text report. On muOS it is saved under `CometDesk/data/`; desktop development builds use the LÖVE save directory. The report contains only device model, SoC, architecture, RAM, firmware marker, detected mount/filesystem and capacity statistics. It deliberately excludes mount source identifiers, serial numbers, network details and personal files. Export is user-initiated; normal startup and periodic probes do not write reports.

## Build locally

Requires Python 3.10+ and network access to the pinned runtime source:

```sh
python3 tools/build_muxapp.py --output dist/CometDesk-dev.muxapp
python3 -m pytest -q
```

The builder also writes a SHA-256 sidecar. Do not rename the archive without renaming its checksum file.

## Install on the RG35XX H

1. Copy `CometDesk-dev.muxapp` to the SD1 `ARCHIVE` directory.
2. Open **Applications → Archive Manager**.
3. Select the Comet Desk package and let Archive Manager finish extraction.
4. Open **Applications → Comet Desk**.
5. If launch fails, retrieve `CometDesk/data/comet-desk.log` from the configured application storage (SD1 or SD2) and report the exact muOS release.

Archive Manager installs the `CometDesk/` folder under `MUOS/application/`. Keep the original archive and its SHA-256 sidecar for reproducible test records.

## Evidence levels

- Builder + archive tests: package structure and static runtime checks.
- GitHub Actions artifact: a downloadable installable package was produced.
- Desktop LÖVE run: desktop renderer only.
- Physical RG35XX H run: actual device, firmware, controls and framebuffer behaviour.

Only the last level counts as device validation.
