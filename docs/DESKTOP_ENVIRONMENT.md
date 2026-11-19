# Debian Desktop Environment

## Purpose

Comet Desk manages one persistent Debian GNU/Linux 13 (Trixie) ARM64 root filesystem on TF1 or TF2. APT is the application and development package manager. Comet runs desktop sessions and later app-launch integrations inside this rootfs; muOS remains the host and supplies the running H700 kernel and hardware devices.

This is **not** an independent bootable firmware image, and Comet does not modify muOS boot files, partitions or firmware.

## Pinned Debian base

| Item | Value |
|---|---|
| Distribution | Debian GNU/Linux 13 (Trixie) |
| Release manifest | 13.7 (stable) |
| Architecture | arm64 / AArch64 |
| Rootfs source | debuerreotype OCI Debian artifact |
| Source commit | `3b26c3995c7fae47d95ba678632a3520e97054f7` |
| Asset | `trixie/oci/blobs/rootfs.tar.gz` |
| Compressed size | 49,778,604 bytes |
| SHA-256 | `23b69c48ce5c2a6fb0681d959fa700427ad2a7cf7e6be5d25249170a1853d7ad` |

The URL is immutable and the OCI layer digest is checked before extraction:
https://raw.githubusercontent.com/debuerreotype/docker-debian-artifacts/3b26c3995c7fae47d95ba678632a3520e97054f7/trixie/oci/blobs/rootfs.tar.gz

APT sources point to Debian Trixie, Trixie updates and Trixie security. The guest package database and caches persist in the Debian image.

## Image layout and storage

- Image file: `MUOS/CometDesk/Desktop/debian.img`
- Container size: 8 GiB (ext4 filesystem is expanded after the base packages are installed)
- Minimum free space required before setup: 9 GiB on the selected card
- Supported locations: explicitly selected TF1 or TF2
- The root filesystem is mounted through a loop device only during setup, package operations or a desktop session.

## Desktop profiles

One Debian rootfs supports multiple installable environments. They share APT, libraries, user data and installed applications.

| Profile | Session | Notes |
|---|---|---|
| **labwc** | Wayland | Default lightweight profile; requires a usable DRM/KMS card device |
| XFCE | X11 | Full traditional desktop; QJoyPad support |
| LXDE | X11 | Lightweight GTK desktop |
| LXQt | X11 | Lightweight Qt desktop |
| IceWM | X11 | Minimal window manager |
| Fluxbox | X11 | Minimal window manager |
| Openbox | X11 | Minimal window manager |

Installing another profile adds its packages to the existing rootfs; it does not download a second operating system. On devices where `/dev/dri/card*` is absent or the wlroots DRM backend cannot take ownership, labwc is not launchable yet; choose an X11 profile until the H700 display path is validated.

## Comet-owned lifecycle

1. Validate the selected writable TF1/TF2 mount and the RG35XX H ARM64 profile.
2. Download the pinned ext4 seed and Debian Trixie ARM64 rootfs.
3. Verify exact asset size and SHA-256 before extraction.
4. Expand the persistent image container and extract Debian into it.
5. Write Debian Trixie APT sources and the Comet H700 display/input profile.
6. Install the minimal APT baseline plus labwc and the selected environment profile.
7. Verify the installed session entry points and persist a profile manifest.
8. Unmount and detach all loop/bind mounts.
9. On launch, Comet mounts the same image, exposes only required host devices/services, and starts the selected compositor/session.
10. When the session ends, Comet cleans up and the muOS launcher reopens Comet Desk.

A shared Debian-system lock serializes environment setup, package-manager operations and desktop sessions.

## H700 CORE dependencies

THE FORGE has a dedicated H700 CORE group for native application work:

- **Graphics:** libdrm-dev, libgbm-dev, libegl1-mesa-dev, libgl4es-dev
- **Wayland:** libwayland-dev, wayland-protocols, libxkbcommon-dev
- **Input:** libevdev-dev, libinput-dev, libudev-dev
- **Audio:** libasound2-dev, libpulse-dev
- **SDL2:** libsdl2-image-dev, libsdl2-ttf-dev, libsdl2-mixer-dev

These are package candidates, not a promise that every H700 peripheral or API is hardware-accelerated. Applications must use the capabilities actually exposed by muOS.

## THE FORGE — APT software centre

THE FORGE presents a curated, filtered catalogue grouped into handheld/input, desktop, development, media/audio, network and utilities. It reads real availability and installation state from Debian's APT/dpkg database.

The first catalogue focuses on packages useful for muOS/H700 work:
- Input inspection and controller tools: `evtest`, `joystick`, `inputattach`, `libinput-tools`, `qjoypad`, Xorg input drivers
- Development: Git, curl/wget, Python venv/pip, GCC/build-essential, CMake, Ninja, pkg-config and SDL2 development files
- Desktop: Foot, Waybar, Mako, Wofi, SwayBG, XWayland, Thunar, PCManFM and Xarchiver
- Media/audio: FFmpeg, MPV, ALSA tools, Pavucontrol and SoX
- Network: OpenSSH client, rsync, Syncthing and ping tools
- Utilities: htop, btop, jq, tree, ncdu, zip/unzip, file and nano

Only package names in Comet's catalogue may be installed or removed through the UI. The service verifies availability against the guest's APT cache, never interpolates arbitrary UI input into a shell command, avoids automatic service startup during package installation and never modifies the host muOS package database.

### Input Leap status

Input Leap is shown in the input catalogue, but disabled. The upstream project supports Linux and has Wayland support, but its documentation notes that clipboard sharing is not supported on Linux/Wayland. Debian Trixie ARM64 does not currently publish an `input-leap` package in the configured repositories, so Comet does not pretend it is an APT-installable package. It can be added later through a separately verified ARM64 build if needed.

QJoyPad is available in Debian Trixie ARM64 but is an X11 application; it is not presented as a native labwc/Wayland input mapper.

### Deliberately filtered out

THE FORGE does not offer:
- muOS host packages, kernel images, firmware, bootloaders or partition tools
- systemd/init replacement, host service managers or host daemons
- Snap, Flatpak, GNOME Software, KDE Discover or PackageKit
- packages without a suitable Debian Trixie ARM64 package candidate
- heavyweight desktop meta-packages as one-click “recommended” installs

Comet itself provides the curated software-centre workflow; it does not need to install another app store into the guest.

## App integration direction

APT installs dependencies and Linux programs into the shared Debian rootfs. The next Comet subsystem will maintain an app registry (name, executable, arguments, icon, category, required packages and session compatibility), then launch those programs within the active Comet-managed desktop session. Installing a package does not yet automatically register it as a Comet application.

## Safety boundaries

- No raw block-device writes, partition edits, firmware flashes or muOS boot changes.
- Reject missing/read-only mounts, symlink paths and unexpected image/manifest files.
- Verify the pinned rootfs payload before extraction.
- Restrict package operations to the curated catalogue.
- Serialize APT, setup and session operations through one lock.
- Track and verify loop and bind mount cleanup.
- A cleanup failure is written to status and log files.

## Hardware validation still required

CI verifies syntax, package structure and service logic, but not a real display hand-off. The RG35XX H must validate loop mount, labwc DRM/KMS acquisition, Xorg fbdev fallback, controller mapping, audio/network access, package installation, app launch, session exit and full cleanup.
