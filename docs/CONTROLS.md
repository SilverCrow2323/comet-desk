# Comet Desk — controller map

The control deck is built around the RG35XX H's shoulder buttons and the native 640×480 display. Navigation and section actions are deliberately separate.

## Main control deck

| Input | Action |
| --- | --- |
| **L1** | Previous section |
| **R1** | Next section |
| **A** | Expand the selected section |
| **SELECT** | Show or hide the active Debian/APT task console |
| **START + SELECT** | Exit Comet Desk |
| **M** (desktop keyboard) | Open/close the Comet Quick Panel |

Only L1 and R1 change tabs on the controller. The D-pad never changes the selected tab.

## Expanded section overlay

| Input | Action |
| --- | --- |
| **B** | Close the current section |
| **D-pad Up/Down** | Move through the section's selectable items, or scroll informational sections |
| **D-pad Left/Right** | Change storage slot or category where the section supports it |
| **A** | Run the focused section action |
| **Mouse wheel / Page Up / Page Down** | Scroll the overlay in desktop preview |

Each overlay has its own accent colour and frame treatment. Its footer shows the active controls for that section; unsupported actions are not shown as working controls.

## Task console

SELECT toggles the dedicated Debian bootstrap / APT console. Hiding the console does not stop or cancel its worker. The task keeps its shared Debian lock and continues to publish status and log output. SELECT opens the console again; B hides it while an active task continues.

The console reads the Comet task status and log:
- `data/desktop-environment.status`
- `data/desktop-environment.log`

The old `desktop-download.status` belongs to the separate MUX package-download flow. It is not the Debian desktop bootstrap status.

## Keyboard preview

For desktop LÖVE preview, Enter/Space/A expands a section, Escape/B closes it, F8 toggles the task console and F9+F8 exits. Arrow keys navigate the current expanded section; they do not switch tabs. The app's controller behaviour remains the reference for the RG35XX H.


## Desktop Input

The Debian desktop receives one virtual host-side keyboard/mouse device. The default profile is:

| Controller input | Desktop action |
| --- | --- |
| Left stick | Mouse pointer |
| A / B | Enter / Escape |
| L1 + A / L1 + B | Left / right mouse click |
| Right stick | Vertical / horizontal scroll |
| D-pad | Arrow keys |
| X / Y | Backspace / Tab |
| R1 + X | Alt + Tab |
| Start / Select | Super / Comet Quick Panel (M) |

Open **DESKTOP INPUT** to change pointer speed, scroll speed, deadzone, bridge enablement and the action bound to each supported button. Changes are saved to `data/desktop-input.json` and applied on the next desktop session. The media player uses a separate mapping: A pause, B quit, X fullscreen, Y mute.

## Media Vault

M opens the Comet Quick Panel. It displays Now Playing and provides A pause/resume, X stop and Y open Media Vault. Inside Media Vault, D-pad left/right cycles **TV**, **RADIO**, **PLAYLISTS** and **EPG**; up/down selects a channel, station or source; A plays the selected channel/station or activates a playlist; Y toggles a TV/radio favourite; X stops playback; Start refreshes the IPTV catalogue and EPG. EPG shows the selected channel's Now/Next programmes.

For IPTV, copy local `.m3u` or `.m3u8` files to `data/media/playlists/imports`. They appear under PLAYLISTS after the catalogue refresh. The default remote source is IPTV-org Italy. TV entries show XMLTV Now/Next when a matching EPG source is available. Custom HTTP/HTTPS playlist sources can also be added with the service command documented in [Media Vault](MEDIA_VAULT.md).

Web radio presets include Rai Radio 1, Radio Deejay, Radio Italia and Radio 24. They are editable in `data/media-vault.json`; stream availability is controlled by each broadcaster and may change.

A single Media Vault supervisor owns playback. Starting another stream stops the previous one. Comet stops playback before launching Debian, on normal frontend exit, and when the foreground IPTV player returns. The heartbeat watchdog also stops playback when the frontend disappears unexpectedly.
