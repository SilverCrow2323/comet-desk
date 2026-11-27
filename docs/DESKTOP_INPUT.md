# Desktop Input

Comet Desk provides a controller bridge for Debian desktop sessions without asking the guest to install a second input stack.

## Architecture

`service/desktop_input.py` reads the selected muOS gamepad through Linux evdev and creates one virtual keyboard/mouse with `/dev/uinput`. It runs on the muOS host, before the guest compositor starts, so labwc/X11 can discover the virtual device during seat initialization.

The bridge uses Python's standard library only. It does not require pygame, python-evdev or a guest-side daemon. It exclusively grabs the selected gamepad while a desktop session is active, preventing the same physical buttons from reaching both the host and guest. The process releases its controls and device grab when the desktop session ends.

If evdev discovery or uinput creation fails, the desktop session is still allowed to start; the status is marked unavailable and the log records the failure. A physical keyboard/mouse remains a fallback.

## Default desktop mapping

| Controller | Desktop action |
| --- | --- |
| Left stick | Mouse pointer |
| A | Enter |
| B | Escape |
| L1 + A | Left mouse click |
| L1 + B | Right mouse click |
| Right stick | Vertical scroll; horizontal axis also emits horizontal wheel events |
| D-pad | Arrow keys |
| X | Backspace |
| Y | Tab |
| R1 + X | Alt + Tab |
| Start | Super key |
| Select | Comet Quick Panel (M) |

The click modifier is sampled when A/B is pressed; press L1 first, then A or B. The left/right sticks use independent deadzones and smoothed fractional accumulation so pointer movement and wheel events do not steal each other's input.

## Edit the mapping

Open **DESKTOP INPUT** in Comet Desk. Up/down selects a setting; left/right adjusts it.

The page exposes pointer speed, scroll speed, stick deadzone, bridge enablement and individual button mappings. Each supported button action can be cycled through the available actions or disabled. Y restores the default map.

The configuration is stored at `data/desktop-input.json`. Changes are persisted atomically and apply to the next desktop session; the active bridge is not hot-reconfigured while it owns the physical controller.

## IPTV player mapping

Full-screen Media Vault TV playback starts the same bridge with a dedicated media profile:

| Controller | Player action |
| --- | --- |
| A | Pause / resume |
| B | Quit player |
| X | Toggle fullscreen |
| Y | Mute |
| L1 + A / L1 + B | Left / right mouse click |
| Left stick | Pointer for MPV on-screen controls |
| D-pad | Directional navigation |

The media profile is deliberately separate from the user's desktop mapping so a custom binding for desktop applications cannot accidentally remove the emergency player-exit action.

## Status and debugging

- Configuration: `data/desktop-input.json`
- Status: `data/desktop-input.status`
- Session output: `data/desktop-environment.log`

A READY status includes the discovered evdev device path/name. UNAVAILABLE includes the reason. Physical controller discovery, axis ranges, click timing, compositor focus and the muOS uinput device still require validation on the RG35XX H; CI tests the mapping logic without claiming physical hardware coverage.
