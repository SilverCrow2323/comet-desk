# APP DECK — Comet-managed Debian applications

APP DECK is Comet's application catalogue for the persistent Debian Trixie ARM64 guest. It is not a second MUX launcher and does not create standalone muOS applications.

## Discovery

The registry reads freedesktop .desktop entries from:
- /usr/share/applications
- /usr/local/share/applications
- /root/.local/share/applications

Only Type=Application entries with a resolvable executable inside the selected Debian root filesystem are listed. Hidden, NoDisplay and Terminal entries are skipped. Desktop field codes used for file/URL forwarding are removed where supported. Shell interpreters and privilege/command wrappers are rejected. Executable symlinks must resolve inside the guest rootfs. The catalogue is written atomically to Comet's private data directory.

## Launch lifecycle

1. The user selects an app from APP DECK.
2. Comet writes a three-line, atomically renamed request containing the selected storage slot, desktop profile and validated registry ID.
3. The MUX supervisor resumes after the LÖVE UI exits, validates the request ID and invokes the Debian environment manager.
4. The manager mounts the guest under a shared lock, re-reads the .desktop entry and validates the executable again.
5. Comet starts the requested installed desktop profile, waits for its Wayland socket or X11 display, then starts the validated executable as an argv array inside Debian. No shell command is assembled from the .desktop file.
6. When the application exits, the manager stops the desktop process group, verifies mount/loop cleanup and returns to the Comet frontend.

The app and desktop session share the Debian rootfs and the muOS host kernel. Comet is the lifecycle owner. The Comet frontend is not drawn over the external application: the framebuffer is occupied by the selected desktop until the app exits, after which Comet resumes.

## Deliberate limits

- DBus-only activatable applications are not yet launched by APP DECK.
- Terminal apps are excluded until Comet has a supervised terminal workflow.
- Unsupported Desktop Entry field codes and shell/privilege wrappers are omitted.
- App launch currently uses one foreground GUI process. Background launchers, helpers that daemonize, and multi-window app suites need explicit process-group policies before being exposed.
- The selected desktop profile must already be installed in the guest.
- Wayland/labwc still requires working DRM/KMS; X11 profiles depend on the host framebuffer and input path.

These restrictions are intentional. The registry does not interpret arbitrary desktop files as shell scripts.
