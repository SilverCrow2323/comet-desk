# Reference Device Profile — RG35XX H / muOS Andromeda

## Baseline

Comet Desk's first-class reference target is the **Anbernic RG35XX H** running **muOS Andromeda 2606.0**.

| Property | Reference value | Detection policy |
|---|---|---|
| Handheld | Anbernic RG35XX H | Device-tree/model hints; report confidence |
| SoC | Allwinner H700 family | Device-tree compatible/model evidence |
| CPU architecture | AArch64 / ARM64 | Runtime architecture probe |
| RAM | 1 GB | Read actual MemTotal; 1 GB is the reference configuration |
| Display | 640 × 480 | Reference geometry; query actual display where possible |
| Host firmware | muOS Andromeda 2606.0 | Detect release metadata; never infer from device model |
| TF1 | 64 GB nominal baseline | Report mounted filesystem and block-device capacity |
| TF2 | Optional expansion card | Detect only when a mounted/visible device is found |

The values above define the reference target, not hard-coded runtime facts. The live probe must show the detected value, source and confidence separately. If the kernel does not expose a field, show **Unknown** rather than copying the baseline into a live status panel.

## Storage model

The common Void Desk muOS application roots are:

- `/mnt/mmc/MUOS/application`
- `/mnt/sdcard/MUOS/application`

These are useful discovery anchors, but the application must not assume that every mount is present or that a path alone proves a physical card's identity.

Comet Desk reports each discovered filesystem with:

- mount point and source device;
- filesystem type;
- total, used and available bytes;
- whether it is read-only;
- associated block-device capacity when it can be resolved safely.

The UI may label the known muOS mount roots as **TF1 candidate** and **TF2 candidate**. It must retain the raw mount/source information and avoid claiming physical-slot certainty without device evidence.

## Expansion-card behaviour

Users commonly replace the baseline TF1 with a larger card and may add a second card. Therefore:

- no 64 GB capacity ceiling;
- no assumptions that TF1 is exactly 64 GB;
- no fixed TF2 size;
- no requirement that TF2 exists;
- calculate install space from the selected destination's live available bytes;
- show filesystem and free-space warnings before any future write operation.

Use bytes internally. Human-readable GB/TB values are presentation only; distinguish decimal GB from binary GiB where useful.

## Compatibility resolution

Void Desk's compatibility guidance requires firmware release + handheld model + controller identity; **H700 alone is not a sufficiently precise profile**. Comet Desk follows the same principle. The RG35XX H / Andromeda profile is the first target, while other H700 devices remain unverified until their display, input, storage and power behaviour are tested.

Reference implementation: [Void Desk device/firmware compatibility](https://github.com/SilverCrow2323/Void-Desk-Project/blob/main/docs/MUOS_FIRMWARE_COMPATIBILITY.md) and [QWASAR product ecosystem map](https://github.com/SilverCrow2323/Void-Desk-Project/blob/main/docs/PRODUCT_ECOSYSTEM_MAP.md).
