# Safety Model

Comet Desk is a muOS companion with an integrated Debian Trixie ARM64 environment. It does not replace the muOS host, firmware or bootloader.

## Non-negotiable rules

- Never modify muOS boot files, boot configuration, recovery, firmware or host APT database.
- Never format, repartition or write an image to a raw block device.
- Never infer the target storage card; the user selects TF1 or TF2.
- Reject missing/read-only mounts, symlink escapes, unexpected files and insufficient space.
- Verify every downloaded rootfs payload before extraction.
- Mount only the expected ext4 image through a loop device owned by Comet.
- Track every bind mount and loop device; verify cleanup before reporting success.
- Never interpolate unchecked UI text into a shell command.
- Restrict THE FORGE install/remove actions to a static curated package allowlist.
- Use one shared lock for Debian setup, APT package operations and desktop sessions.
- Suppress guest service autostart during package installation; do not replace muOS service management.

## Debian environment

The rootfs is Debian GNU/Linux 13 (Trixie) ARM64, stored as an ext4 file on TF1/TF2. It shares the running muOS kernel and selected devices. It is not an independent bootable image and has no guest kernel or bootloader.

The rootfs archive is pinned to an immutable source commit, exact compressed size and SHA-256. APT sources point to Trixie, Trixie updates and Trixie security.

## THE FORGE

THE FORGE does not pass arbitrary package names from the UI to APT. The package worker accepts only entries in its curated catalogue, verifies Debian APT availability and runs install/remove/update inside the mounted guest rootfs.

Filtered out by design: muOS host packages, kernel and firmware packages, bootloaders, partitioning tools, init/system managers, Snap, Flatpak, PackageKit, GNOME Software and KDE Discover. Input Leap remains visible but disabled until a trustworthy Debian Trixie ARM64 package source exists. QJoyPad is marked X11-only.

APT actions are serialized with environment setup and session launch. Package service scripts are prevented from starting guest daemons while the system is being prepared.

## Desktop sessions

- labwc is the default lightweight Wayland profile and requires a working DRM/KMS device.
- XFCE, LXDE, LXQt, IceWM, Fluxbox and Openbox are optional X11 profiles.
- The guest runs on the existing H700 muOS kernel and selected devices.
- If labwc cannot acquire a DRM/KMS device, an X11 profile must be used until the H700 display path is validated.

## Diagnostic report export

Diagnostic export is explicit and opt-in. It writes only the bounded device/storage summary; it does not crawl user files or include Wi-Fi details, account identifiers, device serials or raw block-device source paths.

Reports are written through a temporary file and renamed into place only after a successful write. If a report with the same timestamp already exists, the exporter selects a numbered filename instead of replacing the earlier report. A failed write or rename removes the temporary file and returns an error.

## Hardware validation still required

CI cannot prove framebuffer ownership or controller/audio behaviour on the RG35XX H. Physical tests must validate labwc DRM/KMS, Xorg fbdev fallback, controller mapping, audio/network access, APT operations, package launch, session exit, loop detach and automatic return to Comet.


### Diagnostic report publication

Diagnostic exports reserve their temporary file with exclusive-create mode before writing. A pre-existing file or symlink at the temporary path is never opened for writing, and the final report is published by rename only after the content is flushed and closed. This protects the export path from predictable temporary-file symlink redirection.
