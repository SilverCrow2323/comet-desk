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


## Desktop Setup download

The Desktop Setup page downloads the published Void Desk **v10.2.0** muOS package into the selected, detected TF1 or TF2 `ARCHIVE/` folder. This is a verified package handoff, not an automatic desktop installation: the user completes installation with **Applications → Archive Manager**.

The helper is pinned to the official [v10.2.0 release asset](https://github.com/SilverCrow2323/Void-Desk-Project/releases/tag/v10.2.0), checks the selected mount is present and writable, validates the exact 3,305,314-byte size and SHA-256, and only then publishes the partial download using an atomic rename. A different existing file is left untouched. No boot files, partitions or muOS settings are changed.

Controls: **A / Enter** starts the download; **Left / Right** selects TF1 / TF2; **M** opens the Comet quick overlay; **START + SELECT** exits Comet Desk. The M overlay currently belongs to the Comet Desk frontend; a global overlay inside a separately running XFCE session is not yet connected.

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
