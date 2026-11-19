# Comet Desk Architecture

## Design goal

Comet Desk is the controller-first Linux workspace layer for muOS. muOS remains the host firmware; Comet owns a persistent Debian Trixie ARM64 userspace, APT package lifecycle, desktop sessions and a future application registry.

## Runtime layers

1. **MUX entry point** — muOS launches the application through its native MUX runner.
2. **LÖVE control deck** — curved carousel, page state, controller/keyboard navigation and Uplink telemetry.
3. **Capability layer** — read-only device probe and explicit storage/network checks.
4. **Debian environment manager** — pinned Debian Trixie ARM64 rootfs, APT sources, labwc default profile and optional X11/Wayland sessions.
5. **THE FORGE** — curated APT catalogue, installed/available state, search, install/remove/update and a strict package allowlist.
6. **Session supervisor** — Comet launcher starts the selected Debian profile and reopens Comet after the session exits.
7. **Target storage** — user-selected TF1/TF2 destination; guest ext4 image is a file, never written to a raw block device.

## Debian guest

One persistent ext4 image contains Debian GNU/Linux 13 (Trixie) ARM64 and the APT database. labwc is the default lightweight Wayland profile; XFCE, LXDE, LXQt, IceWM, Fluxbox and Openbox are optional profiles installed into the same rootfs.

The guest shares the currently running muOS H700 kernel and only the host devices/services explicitly bound by Comet. It is not a second bootable firmware image.

## Software model

THE FORGE operates only inside the mounted Debian rootfs. APT commands are serialized with setup and session launches through one shared lock. The curated H700 catalogue focuses on graphics (DRM/GBM/EGL), Wayland, input (evdev/libinput), audio (ALSA/PulseAudio), SDL2 and useful development/network tools.

A subsequent Comet application registry will map package-installed executables to names, icons, categories, launch arguments and supported desktop sessions. Package installation does not yet automatically register or expose every executable as a Comet application.

## muOS host boundary

- No host muOS APT or dpkg operations.
- No writes to boot files, U-Boot, DTB, firmware or partition tables.
- No raw-device flashing or formatting.
- No systemd/init replacement or host daemon takeover.
- Explicit TF1/TF2 selection and live mount/read-only checks.
- Size/checksum validation for downloaded rootfs payloads.
- Verified loop and bind-mount cleanup.
- Physical RG35XX H validation remains required for DRM/KMS, framebuffer, controller, audio and session hand-off behaviour.

## Build evidence

The installable muxapp builder pins and validates the AArch64 LÖVE runtime, checks required helpers/assets, rejects unsafe ZIP paths and validates ELF architecture. Green CI proves source checks and package construction, not physical-device compatibility.
