# Safety Model

Comet Desk is a helper application, not an OS installer.

## Non-negotiable rules

- Never modify muOS boot files or boot configuration as part of normal desktop setup.
- Never infer the install destination from a hard-coded mount path.
- Never format, repartition or recursively delete a target.
- Never run shell commands assembled from unchecked UI strings.
- Never run privileged operations without a narrowly scoped helper and explicit user confirmation.
- Never display a completed/progress state unless the underlying operation reports it.
- Never silently continue after a failed preflight, checksum or write.

## Required install sequence

1. Identify the device and supported profile.
2. Enumerate mounted storage and ask the user to choose a target.
3. Resolve the target and reject unsafe paths (including symlink escapes).
4. Check free space, filesystem support and write access.
5. Present a plan: payload, destination, size, changed files and recovery path.
6. Stage into a temporary directory on the same filesystem.
7. Verify every downloaded/copied payload against a trusted checksum.
8. Atomically activate the staged installation where the filesystem allows.
9. Verify the result and write a recovery manifest.
10. Offer rollback using only the manifest-owned files.

## Current implementation status

Desktop Setup now downloads the published Void Desk v10.2.0 MUX package into a selected, detected TF1 or TF2 `ARCHIVE/` folder. The fixed helper rejects missing/read-only mounts, symbolic-link targets, insufficient free space, conflicting existing files and incomplete or checksum-invalid payloads. It writes to a `.part` file and publishes only after exact size and SHA-256 verification.

The downloaded package is **not** automatically extracted or installed. muOS Archive Manager remains the installation boundary, and the user must initiate that step. The downloader does not alter the boot chain, partition table, muOS configuration or existing application folders.

The frontend also provides an animated boot sequence, low-cost ambient motion, an M-key quick overlay and a START + SELECT exit chord. The quick overlay currently belongs to the Comet Desk frontend; a global overlay inside an independent XFCE session is not yet wired to the desktop-session hand-off layer.
