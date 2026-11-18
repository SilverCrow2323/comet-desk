# Comet Desk — visual identity

Comet Desk uses the QWASAR **Megastructure / Industrial Cyberpunk** design language. The application and documentation share one visual system: the same palette, font families, icon language, spacing logic and graphic motifs.

![Comet Desk visual system](assets/visual-system.png)

## Core palette

| Token | Hex | Use |
|---|---|---|
| Graphite | `#090C13` | Main canvas |
| Panel | `#111620` | Primary surfaces |
| Panel raised | `#161D29` | Selected and nested surfaces |
| Structural line | `#293F57` | Dividers, outlines and grid |
| Signal cyan | `#38E0F0` | Focus, active navigation, links and primary data |
| Violet | `#9E6EFA` | Secondary accents and section markers |
| Amber | `#FFB852` | Warnings, attention and pending states |
| Magenta | `#F64DB4` | Rare highlight accent |
| Status green | `#59E6AE` | Verified/healthy state only |
| Ice white | `#E8F2FA` | Main text |
| Steel muted | `#7A97B0` | Supporting text and metadata |

Keep the palette restrained. Cyan is the primary signal; amber is not a generic decoration and green must retain its status meaning.

## Typography

- **Inter Bold** — display titles, section headings and prominent values.
- **Inter Medium** — interface labels and body copy.
- **PT Mono** — telemetry, timestamps, technical labels, keys and metadata.

These are bundled with the app so the 640×480 interface does not depend on system fonts. Documentation should use the same families; where fonts cannot be embedded, use a close sans-serif/monospace fallback while preserving the hierarchy.

Font files retain their upstream licences in `assets/fonts/THIRD-PARTY-LICENSES.md`.

## Graphic grammar

- Industrial frames, measurement ticks, thin technical rules and restrained grid overlays.
- Layered megastructure/city artwork with negative space reserved for text.
- Angular orbital/comet mark, not generic clip-art.
- Cyan active states, violet secondary navigation, amber warnings.
- Compact controller-first composition designed at 640×480 before scaling upward.

## Asset map

- `assets/branding/` — product wordmark and identity.
- `assets/icons/` — app icon and individual navigation icons.
- `assets/backgrounds/` — in-app 640×480 artwork.
- `assets/ui/` — reusable interface texture.
- `assets/fonts/` — bundled UI typefaces and notices.
- `docs/assets/` — documentation covers and explanatory graphics.

## Screenshots and evidence

Documentation screenshots must be captured from a real application build. Label each capture with the build/commit and target (desktop preview or physical RG35XX H). Never present a mockup, generated illustration or design-board image as a functional screenshot. Generated artwork is used as artwork only; UI screenshots remain genuine captures.

When a feature is not implemented, show its real current screen and label the limitation. Do not create fictional success states for documentation.
