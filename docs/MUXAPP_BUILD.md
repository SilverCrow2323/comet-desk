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
│   └── device_probe.lua
├── lib/
│   ├── love
│   ├── liblove-11.5.so
│   └── libluajit-5.1.so.2
└── data/
```

The AArch64 launcher and LuaJIT runtime are fetched from a pinned Void Desk commit; the LÖVE 11.5 shared library comes from the pinned Dolphin RT Core runtime source. All three are checked as 64-bit little-endian AArch64 ELF, and the LÖVE shared library also has a pinned Git blob checksum. The package includes the read-only Lua device probe; the validator rejects missing application/runtime files, unsafe paths, symlinks, wrong ELF architecture and a non-executable launcher.

The launcher follows the muOS Andromeda application runner contract: it sources `/opt/muos/script/var/func.sh`, calls `SETUP_APP`, and uses the runtime application path `/run/muos/storage/application/CometDesk`. It does not hard-code SD1/SD2 mount roots.

## Get the CI package

Every push, pull request and manual workflow run builds a package after the Lua and Python checks pass. Open the repository's **Actions** tab, select the **Project checks and device package** run, then download the `CometDesk-muOS-Andromeda-RG35XX-H` artifact. It contains the `.muxapp` and matching SHA-256 sidecar.


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
5. If launch fails, retrieve `MUOS/application/CometDesk/data/comet-desk.log` and report the exact muOS release.

Archive Manager installs the `CometDesk/` folder under `MUOS/application/`. Keep the original archive and its SHA-256 sidecar for reproducible test records.

## Evidence levels

- Builder + archive tests: package structure and static runtime checks.
- GitHub Actions artifact: a downloadable installable package was produced.
- Desktop LÖVE run: desktop renderer only.
- Physical RG35XX H run: actual device, firmware, controls and framebuffer behaviour.

Only the last level counts as device validation.
