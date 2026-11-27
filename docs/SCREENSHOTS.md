# Screenshot and visual evidence guide

Screenshots are evidence, not illustrations. Never label a concept image or generated artwork as an application screenshot.

## Capture classes

- `desktop-preview`: real LÖVE application running on a desktop.
- `rg35xx-h-muos-andromeda`: captured from the physical handheld.
- `mockup`: explicitly labelled design concept only; never used to prove a feature works.

## Required metadata

For each screenshot, record:
- repository commit SHA and build identifier;
- capture class and device/firmware when applicable;
- screen/module name and relevant controller focus state;
- whether the feature shown is implemented, partial or a visual placeholder.

## Planned screenshot set

1. Overview — device identity and storage summary.
2. Diagnostics — read-only checks and export affordance.
3. Desktop Setup — preflight-only state, clearly labelled as not yet installing.
4. Session Manager — actual discovered sessions only; no invented entries.
5. Export result — only after a real report has been written and inspected.

## Capture policy

Use the actual application framebuffer/window. Crop only empty desktop chrome; do not repaint, replace labels, fabricate telemetry or alter feature states. For device captures, preserve the original image and record the firmware/build details alongside it.

Until a real capture exists, documentation uses the dedicated artwork and UI diagrams from `docs/assets/`, not fake screenshots.
