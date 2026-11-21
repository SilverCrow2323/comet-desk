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
│   ├── desktop_environment.py
│   ├── forge_apt.py
│   └── app_registry.py
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


## Debian Trixie desktop and THE FORGE

Desktop System builds one persistent Debian GNU/Linux 13 (Trixie) ARM64 rootfs with APT. The default profile is labwc; XFCE, LXDE, LXQt, IceWM, Fluxbox and Openbox can be installed as additional profiles in the same image. The rootfs is stored at MUOS/CometDesk/Desktop/debian.img on the explicitly selected TF1/TF2 card.

THE FORGE is Comet's curated APT software centre. It groups H700/muOS-oriented packages, queries live Debian APT availability and dpkg installation state, supports package search, installation, removal and index refresh. It includes a dedicated H700 CORE group for DRM/GBM/EGL, Wayland, evdev/libinput, ALSA/PulseAudio and SDL2 development libraries. Input Leap is visible but disabled because Debian Trixie ARM64 does not currently offer it in the configured APT repositories; QJoyPad is marked X11-only.

All package operations run inside the mounted Debian rootfs. The host muOS APT database is never touched. Desktop setup, package operations and session launches share one lock, preventing concurrent modification or mount attempts. See Debian Desktop Environment (DESKTOP_ENVIRONMENT.md) and THE FORGE (FORGE.md).

Controls: L1/R1 changes Comet tabs. APP DECK scans installed .desktop entries, D-pad up/down selects apps, D-pad left/right changes category, A launches the selected app through the currently installed desktop profile, Y refreshes the catalogue and / starts keyboard search. THE FORGE uses D-pad up/down for packages, D-pad left/right for category, A to install, X twice to remove and Y to refresh APT indexes. APT mutations are limited to the bundled curated allowlist.

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


## Curved navigation and Uplink

The main navigation is a curved five-card viewport over a recessed rail. L1/R1 moves the unwrapped carousel target; cards travel along the curve with eased interpolation, the selected card grows and takes its own accent colour, and the page body enters with a directional slide/fade. The selected page title and position indicators sit above the rail. The seven hubs are Overview, Desktop System, APP DECK, Uplink, THE FORGE, System Tools and Diagnostics.

Uplink reads live muOS state without blocking the LÖVE frame loop. The Python helper reports Wi-Fi association/IP, hotspot/AP state, Bluetooth power and paired-device count, plus the Andromeda Local DNS, Web Dashboard, SSH/SFTP, Virtual Terminal and Syncthing services. These are status indicators; Comet does not change muOS network configuration.

Rt:Tailscale-M is optional. Comet can download the pinned official `RtTailscale-M-0.2.0.muxapp` release directly, verify its 40,324,056-byte size and SHA-256, safely extract the single `RtTailscale/` tree into the muOS application directory, run its `rt install` / `rt ensure` service manager and read status through `rt summary` + `ts status --json`. The RT service manager remains the sole owner of `tailscaled`; Comet never starts a second daemon or copies node identity data. First login and account approval remain an explicit user action in Rt:Tailscale-M.

The RT release is pinned to v0.2.0, SHA-256 `55580f97902e45c7924b901138fa2cb8f6f125d7ba2b49def8f93f735558cad7`. Installation requires network access and sufficient free space on TF1 or TF2. Existing RT installs are never overwritten.

## Latest exact candidate — 21 November 2026

- Source: `1d5ff645c74e7b801ec446252fae4d69dc49536c` on `feat/diagnostic-report-export`.
- CI: [run #44895778133](https://github.com/SilverCrow2323/comet-desk/actions/runs/44895778133), with Lua, Python and package jobs all successful.
- Actions artifact: [#14703732736](https://github.com/SilverCrow2323/comet-desk/actions/runs/44895778133/artifacts/14703732736), 2,107,181 bytes; archive SHA-256 `c53c4b751fb88408d01268b0c8a59cf27ce56241b566b5cf78cce8b3dd4f9cd1`.
- Extracted `CometDesk-dev.muxapp`: 2,115,459 bytes; SHA-256 `d433657598d579488562a6cf942c0d1a4ed4fe6e4d677fea054743c01967806b`.
- The sidecar `CometDesk-dev.muxapp.sha256` was read from the downloaded artifact and matched the independently calculated package digest.

This proves that CI produced a structurally validated installable `.muxapp`. It does not prove installation or operation on a real RG35XX H. Keep the 1.0.0 release blocked on the six release-gate groups, especially TF1/TF2 install and upgrade preservation, desktop display/input/audio, APT/APP DECK operations, supervised return/cleanup, Uplink/Media Vault and extended stability.
## Latest exact candidate — 21 November 2026

- Source: `ee34134ebb7a3587d06c5bfbf714562ab03f2f5b` on `feat/diagnostic-report-export`.
- CI: [run #44951421199](https://github.com/SilverCrow2323/comet-desk/actions/runs/44951421199), with Lua, Python and package jobs all successful.
- Actions artifact: [#14724674427](https://github.com/SilverCrow2323/comet-desk/actions/runs/44951421199/artifacts/14724674427), 2,107,181 bytes; archive SHA-256 `44ae6f47200d03da2c8dedb031b4867b008c5799ab06ac0f84a3912ee60183af`.
- Extracted `CometDesk-dev.muxapp`: 2,115,459 bytes; SHA-256 `d433657598d579488562a6cf942c0d1a4ed4fe6e4d677fea054743c01967806b`.
- The sidecar in the downloaded archive was read and matched the independently calculated `.muxapp` digest exactly.

This proves that CI produced a structurally validated installable `.muxapp`. It does not prove installation or operation on a real RG35XX H. Keep the 1.0.0 release blocked on the six release-gate groups, especially TF1/TF2 install and upgrade preservation, desktop display/input/audio, APT/APP DECK operations, supervised return/cleanup, Uplink/Media Vault and extended stability.
## Latest exact candidate — 21 November 2026

- Source: `0d51c6173adca6b289d7eacaa40128678946b43d` on `feat/diagnostic-report-export`.
- CI: [run #44951531216](https://github.com/SilverCrow2323/comet-desk/actions/runs/44951531216), with Lua, Python and package jobs all successful.
- Actions artifact: [#14725976382](https://github.com/SilverCrow2323/comet-desk/actions/runs/44951531216/artifacts/14725976382), 2,107,181 bytes; archive SHA-256 `10bf9582dd1ead07b29508491a6c4f26b46cfe1727230f3460a8811f1992600a`.
- Extracted `CometDesk-dev.muxapp`: 2,115,459 bytes; SHA-256 `d433657598d579488562a6cf942c0d1a4ed4fe6e4d677fea054743c01967806b`.
- The sidecar in the downloaded archive was read and matched the independently calculated `.muxapp` digest exactly.

This proves that CI produced a structurally validated installable `.muxapp`. It does not prove installation or operation on a real RG35XX H. Keep the 1.0.0 release blocked on the six release-gate groups, especially TF1/TF2 install and upgrade preservation, desktop display/input/audio, APT/APP DECK operations, supervised return/cleanup, Uplink/Media Vault and extended stability.