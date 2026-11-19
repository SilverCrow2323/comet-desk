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
