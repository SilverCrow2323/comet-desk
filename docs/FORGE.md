# THE FORGE — Software Centre

THE FORGE is Comet Desk's Discover/Software-style frontend for the Debian Trixie ARM64 rootfs. It manages Debian packages in the guest and never runs APT against muOS itself.

## First catalogue groups

**H700 CORE** is a dedicated group for application developers. It includes libdrm/libgbm/EGL, Wayland, xkbcommon, evdev/libinput/udev, ALSA/PulseAudio and SDL2 image/font/mixer development libraries. These are the building blocks for graphics, controller/input and audio integrations.

| Group | Examples | H700 reason |
|---|---|---|
| Handheld & Input | evtest, joystick, inputattach, libinput-tools, QJoyPad, Xorg input drivers | inspect controller events and support X11 input mapping |
| Desktop | foot, waybar, mako, wofi, swaybg, XWayland, Thunar, PCManFM, Xarchiver | build the labwc and lightweight X11 workflow |
| Development | Git, curl/wget, Python venv/pip, build-essential, CMake, Ninja, pkg-config, SDL2 dev | build native ARM64 muOS companion tools and ports |
| Media & Audio | FFmpeg, MPV, ALSA utilities, Pavucontrol, SoX | media and audio workflows; hardware decode is not assumed |
| Network | OpenSSH client, rsync, Syncthing, ping tools | development and file transfer |
| Utilities | htop, btop, jq, tree, ncdu, zip/unzip, file, nano | inspect and maintain the guest environment |

Only packages present in the curated list can be installed or removed. The UI shows live availability from Debian's APT indexes, installed state from dpkg and the package's installed size. Package searches filter the current category.

## Controls

- L1/R1 changes the main Comet carousel tabs.
- D-pad up/down selects a package.
- D-pad left/right changes the package group.
- A installs a package that is available but not installed.
- X twice confirms removal of an installed package.
- Y refreshes Debian APT indexes.
- / begins keyboard search; typed text filters title, package name and description.

Selecting install, remove or index refresh opens a dedicated black operation console with the APT log, current task and progress percentage reported by apt/dpkg. Press **B / Esc** to hide the screen while the package worker continues. A shared Debian-system lock prevents overlapping APT, setup and desktop-session operations.

The first Comet Desk launch automatically prepares the base Debian Trixie + labwc environment on the first writable TF card with at least 9 GiB available. A failed previous attempt is retried rather than being mistaken for a successful setup. Additional desktop profiles use the same operation console from Desktop System.

## Compatibility policy

THE FORGE favours lightweight packages with a clear use on ARM64 handhelds. It excludes packages that would alter muOS itself or introduce another host service manager:

- no host muOS packages
- no kernel, bootloader, firmware or partition tools
- no systemd/init replacements
- no Snap, Flatpak, PackageKit, GNOME Software or KDE Discover
- no packages without an ARM64 candidate in the configured Debian Trixie repositories

Input Leap is shown as a disabled entry. Upstream Linux support exists, including Wayland support, but Linux/Wayland clipboard sharing is not currently supported and Debian Trixie ARM64 has no package in the configured APT repositories. We will only enable it after a verifiable ARM64 build/package is available. QJoyPad is included and clearly marked X11-only.
