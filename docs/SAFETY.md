# Safety Model

Comet Desk is a muOS companion with an integrated, reversible XFCE desktop environment. It is **not** a replacement firmware installer or bootloader manager.

## Non-negotiable rules

- Never modify muOS boot files, boot configuration, recovery or firmware.
- Never format, repartition or write an image to a raw block device.
- Never infer the target storage card; the user selects TF1 or TF2.
- Reject missing/read-only mounts, symlink escapes, unexpected existing files and insufficient space.
- Never interpolate unchecked UI text into shell commands.
- Verify every downloaded seed/rootfs payload before extracting or mounting it.
- Mount only the expected ext4 image through a loop device owned by the current Comet process.
- Track every bind mount and loop device created by Comet; verify cleanup before reporting success.
- Never display progress or a completed state unless the helper reports it.
- Keep the desktop root filesystem isolated from the muOS root filesystem.

## Integrated desktop sequence

1. Verify the RG35XX H / H700 ARM64 profile and the selected TF1/TF2 mount.
2. Check at least 5 GiB of free space and reject symlinked destinations.
3. Download the pinned Void Desk XFCE ext4 seed and verify its Git blob checksum.
4. Download Ubuntu Base 24.04.3 ARM64 and verify the exact size and SHA-256.
5. Expand the compressed seed to an ext4 image on the selected card.
6. Mount the image with a dedicated loop device, extract Ubuntu Base into it and validate the OS release.
7. Install Xorg, XFCE and handheld input/audio packages inside the guest root filesystem.
8. Verify the desktop entry points and persist a small profile manifest.
9. Unmount all guest bind mounts, detach the loop device and verify both are gone.
10. On launch, mount the image again, bind only required host devices/services/storage, and start Xorg/XFCE.
11. When XFCE exits, unmount and detach, then resume Comet Desk automatically.

## Distribution accuracy

The current Void Desk H700 bootstrap source at the pinned commit uses **Ubuntu Base 24.04.3 ARM64 (Noble)** with XFCE packages installed from Ubuntu ports. It is not a Debian Trixie root filesystem. Comet reports the actual base accurately.

## Host/guest boundary

The guest filesystem is an ext4 file stored on TF1 or TF2. It shares the running muOS kernel and selected host devices; it does not contain its own bootloader/kernel and is not a full-device OS image. Comet never flashes the file or asks Archive Manager/Void Desk to continue the workflow.

## Current limitations

- The desktop image is prepared online; initial setup requires Wi-Fi and several GiB free.
- Package installation time depends on the network and Ubuntu mirrors.
- Physical RG35XX H validation is still required for framebuffer ownership, input mapping, audio, Wi-Fi/Bluetooth and cleanup after abnormal exits.
- The M-key quick overlay is currently available in the Comet interface; a global in-desktop overlay still needs its own integrated session hotkey implementation.
