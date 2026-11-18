# Comet Desk assets

This folder contains the shared runtime artwork and source identity files.

- `backgrounds/comet-dashboard-640x480.png` — low-memory, darkened in-app background artwork (320×240 source, scaled to the 640×480 canvas).
- `icons/comet-desk-atlas.png` — six 48×48 transparent tiles: app mark, Overview, Setup, Sessions, Tools and Diagnostics.
- `branding/comet-desk-wordmark.svg` — scalable Comet Desk wordmark source.

The MUX builder includes the PNG background and icon atlas in every device package. The SVG wordmark remains a documentation/source asset. PNG assets are intentionally palette-limited to keep the H700/1 GB target lightweight.
