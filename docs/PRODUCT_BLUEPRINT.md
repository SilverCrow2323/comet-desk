# Comet Desk — Product Blueprint

**Product target:** Comet Desk 1.0  
**Reference device:** Anbernic RG35XX H, muOS Andromeda 2606.0, Allwinner H700, 640×480, 1 GB RAM  
**Status:** Development contract. This document defines the intended stable product; it does not claim that untested hardware paths already work.

## The product in one sentence

Comet Desk is a controller-first muOS control deck that owns one persistent Debian ARM64 workspace, supervises its desktop sessions and applications, and exposes a small set of useful tools without taking ownership away from muOS.

It is not a second firmware, a general-purpose distro installer, or a miniature desktop environment pretending to be a handheld launcher.

## What 1.0 must deliver

A stable Comet Desk release must make six jobs boringly dependable:

1. **Desktop System** — install and maintain one persistent Debian Trixie ARM64 guest on an explicitly selected storage card; prepare and launch a supported desktop profile.
2. **Session supervision** — start a desktop or one registered application, retain ownership of its process group and mounts, and return cleanly to Comet.
3. **APP DECK** — discover safe installed GUI applications, search and filter them, and launch them through the supervisor.
4. **THE FORGE** — present a curated Debian package catalogue with truthful installed/available state and serialized package operations.
5. **UPLINK** — expose only real muOS-supported network/radio/service actions. A control that cannot perform its advertised action must be unavailable, not decorative.
6. **System Tools and Diagnostics** — show facts from live probes, distinguish unknown from unavailable, and export an explicitly requested privacy-scoped report.

If one of these jobs is unreliable, adding another module is the wrong next step.

## Hard product decisions

### muOS remains the owner of the device

- muOS remains the host and continues to boot the handheld.
- Comet owns a persistent Debian Trixie ARM64 userspace stored as an ext4 **file** on TF1 or TF2.
- The guest shares the running H700 kernel. It is not a separate bootable image.
- Comet must never edit boot files, U-Boot, DTBs, firmware, partition tables, or the host APT/dpkg database.
- No raw block-device writing, formatting, repartitioning, or automatic card selection followed by destructive work.

### One guest, one package database, one operation lock

The product keeps one Debian rootfs. Desktop profiles share that rootfs, installed libraries, APT state and user data. A second Debian image per profile would duplicate storage and make updates harder to reason about.

Setup, APT operations and desktop sessions share one kernel flock lock. The lock owner—not the existence of a status file—is the authority on whether the guest is busy. Status files are atomic, human-readable snapshots; they are never proof that a worker still exists.

### Default profile and compatibility

- labwc is the intended lightweight default because it is the smallest Wayland-first workflow currently integrated.
- labwc must not be described as hardware-validated until DRM/KMS startup, controller input, audio, exit and cleanup have passed on the RG35XX H.
- X11 profiles remain explicit alternatives, not an automatic silent fallback. The user must know which display path is being started.
- Keep optional profiles only while their install, launch and return paths are maintained. A profile that cannot pass the device matrix should be marked experimental or removed from the stable UI.

### Curated, not unlimited

THE FORGE is an H700-oriented package centre, not an unrestricted Debian app store. Package allowlisting, architecture availability and the host boundary are more important than catalogue size. Avoid installing compilers, SDKs and bulky media stacks in the first-boot baseline; make them opt-in.

APP DECK launches only validated registry entries. Arbitrary shell strings, privilege wrappers, host paths and unvalidated desktop-entry commands never come from UI input.

UPLINK controls the muOS host through supported host-side mechanisms. Guest networking must not become a second manager for the same radios or services. Rt:Tailscale-M remains the owner of its Tailscale daemon.

## The interface contract

Comet is designed for a native 640×480 screen and physical controls first.

- Every screen has one primary job and a visible current state.
- Keep the useful content inside the 20 px safe margin; no clipped labels, overlapping cards or controls hidden below the footer.
- Use the existing QWASAR cyan/violet/amber visual language, but reserve amber for warnings and green for verified success.
- Do not use animation to communicate progress. Animation is atmosphere; progress comes from the worker.
- Keep labels short and legible. Do not shrink important text to fit an overfilled panel; remove or reorganize content instead.
- Every action has a clear input hint, a confirmation where destructive, and visible success/failure feedback.
- Unknown, not detected, not installed, not checked, busy and failed are different states. Never collapse them into a generic green READY.
- The main navigation stays focused on the six jobs above. No placeholder page should masquerade as a finished feature.

### Screen responsibilities

| Screen | Owns | Must not become |
|---|---|---|
| Overview | Device snapshot, guest/session state, storage summary, recent actionable notice | A wall of duplicated telemetry |
| Desktop System | Storage target, free-space preflight, profiles, setup/session lifecycle | A distro installer for arbitrary images |
| APP DECK | Safe installed GUI app discovery, categories, search, launch | A terminal launcher or arbitrary command runner |
| UPLINK | Host radio/network/service state and supported actions | A second network stack or simulated toggle board |
| THE FORGE | Curated Debian APT catalogue and package transactions | An unrestricted package mirror |
| System Tools | Compact guest, package, registry and storage status | A control panel full of unimplemented buttons |
| Diagnostics | Read-only checks, precise faults, privacy-safe report export | A generic log-dump or personal-data collector |

## Reliability contract

Every long-running operation follows the same conceptual lifecycle:

**Preflight → Acquire lock → Execute → Verify result → Cleanup → Publish final state**

The interface must expose these outcomes distinctly:

- **READY** — the requested state was verified, not merely attempted.
- **BUSY** — a live worker owns the shared lock.
- **FAILED** — the requested work failed; include a useful reason and retain the log.
- **CLEANUP_REQUIRED** — the main action may have completed, but mount/process cleanup was not verified.
- **UNKNOWN / NOT CHECKED** — no reliable probe has established the state.

Additional invariants:

- Downloads are size/hash checked before use and partial files are not promoted to final assets.
- Persistent manifests are written atomically and describe the guest actually verified.
- Every mount and loop device is owned, tracked and checked during cleanup.
- A stale status file can never block recovery when no process owns the lock.
- A genuinely busy lock can never be bypassed to start a conflicting APT or mount operation.
- Worker output and APT Status-Fd events drive progress. Do not invent percentages or mark a task complete because a process was spawned.
- Failure messages say what failed and the safest next step. Never recommend deleting the lock file as a recovery shortcut.

## Performance budget

The reference handheld has limited memory and storage bandwidth. The stable product should prefer:

- no resident background daemon when polling from the Comet process is sufficient;
- bounded file reads and cached catalogues instead of rebuilding lists every frame;
- one supervised desktop/application session at a time;
- minimal first-boot packages and opt-in development tools;
- no heavy desktop effects or always-on visualizers;
- bounded logs and explicit cleanup of temporary downloads and stale requests.

A visually impressive feature that costs responsiveness or breaks the return path is not an improvement.

## Deliberately out of scope for 1.0

- Replacing muOS or introducing another boot manager.
- Multiple guest distributions or multiple independent Debian images.
- Arbitrary package installation from untrusted repositories.
- General-purpose partitioning, formatting or image flashing.
- DBus activation, terminal-app launching and background guest services until their lifecycle is supervised end-to-end.
- Broad claims for other H700 devices before their screen, controls, storage paths and firmware are tested.
- Decorative toggles, fake progress, simulated hardware state or placeholder feature pages.

These can be reconsidered only with a concrete user job, a safe backend and a testable acceptance condition.

## Release sequence

- **0.7.x — reliability line:** bootstrap recovery, operation truthfulness, package integrity, status consistency and the first real RG35XX H test loop.
- **0.8.0-rc — feature freeze:** complete the health/status model, finish the six core workflows, freeze UI and validate all supported paths on hardware.
- **1.0.0 — stable:** publish only after every release blocker in [RELEASE_GATES.md](RELEASE_GATES.md) is closed with evidence.

CI proves source checks and package construction. It does not prove DRM/KMS, framebuffer ownership, handheld controls, audio, radio behaviour, real APT operation or mount cleanup on the device.
