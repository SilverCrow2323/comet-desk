# Void Desk OS — image contract

**Product target:** a dedicated H700 Linux disk image, not a MUX application.

## Default system profile

| Layer | Target |
|---|---|
| Distribution | Debian Trixie |
| Architecture | ARM64 / AArch64 |
| Primary compositor | labwc (Wayland) |
| Desktop shell | Void Desk interface |
| Optional desktop | XFCE, installed as an opt-in layer |
| Hardware | Anbernic RG35XX H / Allwinner H700, 640×480 |
| Boot stack | H700-tuned Linux kernel + matching DTB + U-Boot |
| Boot management | H700 MultiBoot integration |

The normal image should start the lightweight labwc session. XFCE is not part of the default startup path and must remain optional, so the handheld does not pay its memory and startup cost until requested.

## Release contract consumed by Comet Desk

Comet Desk accepts only a published release whose tag begins with `voiddesk-os-v` and which contains this exact asset:

```text
VoidDeskOS-RG35XX-H-Debian-Trixie-labwc.img.xz
```

GitHub release metadata must include a SHA-256 digest for the asset. The MUX app downloader ignores ordinary Void Desk application releases and rejects any asset that does not match the image name, tag prefix, HTTPS GitHub release host, size limit and SHA-256 format.

The compressed full-disk image is staged on the user-selected mounted and writable SD card at:

```text
MUOS/CometDesk/OS-Staging/VoidDeskOS/
```

The current downloader verifies the compressed image and writes a sidecar checksum. It does **not** decompress, flash, repartition, install a bootloader, or change the active muOS installation.

## Boot and MultiBoot boundary

A downloaded full-disk image is not automatically bootable just because its download and checksum succeed. The kernel, DTB, bootloader, storage layout, panel revision and input devices must all be matched and tested.

H700 MultiBoot owns the eventual install/boot hand-off. Comet Desk must call a documented MultiBoot interface rather than inventing a raw-device write or a guessed boot path. Until that interface and the correct image layout are verified, the app reports the image as **staged** and does not offer a fake Launch action.

The RG35XX H standard-panel DTB is the first target. Other H700 models and panel revisions require explicit profiles and separate validation.

## Image build acceptance gates

- Reproducible Debian Trixie ARM64 root filesystem.
- labwc and its Wayland/DRM/input dependencies work on the H700 kernel.
- XFCE is an optional, installable desktop layer, not a second default session.
- H700 kernel build is pinned to an exact upstream revision and a documented patch/config set.
- Kernel image, DTB, U-Boot and partition map are packaged together when the release is intended as a full-disk image.
- First-boot setup creates a non-root user, generates machine identity, expands the root filesystem safely and never ships a shared default password.
- Release contains the exact image asset, published SHA-256 digest, image layout metadata, hardware profile and recovery instructions.
- Physical RG35XX H testing covers cold boot, panel/backlight stability, Wi-Fi, Bluetooth, audio, battery, input, suspend/reboot and MultiBoot return path.

## References

- [Void Desk application project](https://github.com/SilverCrow2323/Void-Desk-Project) — product UI and H700 application integration.
- [H700 Debian Trixie cyberdeck reference](https://github.com/hataketsu/rg35xxh-cyberdeck) — public engineering reference for the Debian ARM64, H700 kernel/DTB and full-disk image problem space. It is a separate project, not a Void Desk OS binary dependency.
