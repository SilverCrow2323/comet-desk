# Integrated XFCE environment

## Purpose

Comet Desk provides a controller-first XFCE desktop session on the RG35XX H without launching the Void Desk MUX application or another installer. It reuses the existing Void Desk H700 XFCE bootstrap inputs and owns the whole prepare/run/return lifecycle.

## Verified source profile

| Layer | Current source contract |
|---|---|
| Device | Anbernic RG35XX H |
| SoC | Allwinner H700 |
| Host | muOS Andromeda |
| Guest rootfs | Ubuntu Base 24.04.3 ARM64 (Noble) |
| Desktop | XFCE 4 |
| Display | Xorg + fbdev, 640×480 |
| Kernel | Running muOS kernel; no guest kernel |
| Image | Ext4 filesystem image, stored as a file on TF1 or TF2 |

The currently inspected Void Desk bootstrap source uses ubuntu-base-24.04.3-base-arm64.tar.gz. This is not a Debian Trixie root filesystem. Comet preserves the actual source profile and labels it accordingly.

## Downloaded inputs

The XFCE seed is pinned to Void Desk commit 0fd1447bcf9f31a5e812f78b9e2afed4db01cce7:

- assets/xfce.img.gz
- Compressed asset size: 4,181,220 bytes
- Git blob SHA-1: 9a9571d17f94dc9c8993782a4df4126833e47e8b

The ARM64 root filesystem is fetched from the Ubuntu Base 24.04 release directory:

- ubuntu-base-24.04.3-base-arm64.tar.gz
- Size: 29,865,086 bytes
- SHA-256: 7b2dced6dd56ad5e4a813fa25c8de307b655fdabc6ea9213175a92c48dabb048

The checksum is listed in Ubuntu Base's published SHA256SUMS file: https://ftp.lysator.liu.se/ubuntu-dvd/ubuntu-base/releases/24.04/release/SHA256SUMS.

## Comet-owned lifecycle

1. Select and validate a mounted, writable TF1 or TF2 card.
2. Require at least 5 GiB available.
3. Download and authenticate the compressed ext4 seed.
4. Expand it to MUOS/CometDesk/Desktop/xfce.img.
5. Download and authenticate Ubuntu Base ARM64.
6. Mount the ext4 file with a loop device and extract the root filesystem into it.
7. Install XFCE, Xorg, input, audio, network and file-manager packages inside the guest.
8. Verify XFCE entry points and persist a profile marker.
9. Unmount all bind mounts and detach the loop device.
10. On request, mount the image, bind required devices/services/storage and run startx.
11. When the user exits XFCE, clean up mounts and resume Comet Desk.

The MUX launcher supervises both frontends. Comet Desk requests a session using a single private file in its own data directory; its launcher then invokes the integrated Python manager and reopens the Comet UI after the session ends. This is an internal Comet workflow, not a hand-off to Void Desk MUX or Archive Manager.

## Safety boundaries

- The image is a file on TF1/TF2, not a raw disk image written to a block device.
- No partition table, muOS boot files, U-Boot, DTB or firmware are changed.
- The guest uses the existing H700 muOS kernel.
- Every downloaded input is size/checksum verified before extraction.
- Symlinked destinations, read-only mounts, insufficient space and invalid ext4 images are rejected.
- Loop devices and bind mounts are tracked and their cleanup is verified.
- A cleanup failure remains visible in Comet's status file and log.

## Hardware validation still required

CI cannot prove that fbdev takes ownership and returns cleanly on the real RG35XX H. Physical tests must verify cold Comet launch, ext4 loop mount, Xorg framebuffer, controller mapping, audio, Wi-Fi/Bluetooth, XFCE application launch, logout, loop detach and automatic return to Comet/muOS.
