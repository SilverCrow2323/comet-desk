# Comet Desk — Release Gates

This checklist is the authority for release readiness. A green GitHub Actions run is necessary, not sufficient.

## Gate 1 — Repository and package integrity

- [ ] Lua sources parse with the pinned Lua/LuaJIT-compatible checks.
- [ ] Python sources compile and the complete pytest suite passes.
- [ ] Shell launchers pass sh -n.
- [ ] MUX package builds from a clean checkout.
- [ ] Archive paths, permissions, required assets and AArch64 ELF payloads validate.
- [ ] SHA-256 sidecar matches the final package.
- [ ] Package version shown in the UI matches the version shipped in the archive.
- [ ] No generated test files, credentials, personal logs or device-specific private data are included.

## Gate 2 — Install and first bootstrap (RG35XX H / muOS Andromeda)

- [ ] Install over the previous Comet build without losing the user's Debian guest or its manifest.
- [ ] Clean install to TF1 with the exact available-space preflight shown before work starts.
- [ ] Install to TF2 when TF2 is mounted and explicitly selected.
- [ ] Verify the download size and SHA-256, ext4 image creation, Debian Trixie release identity and selected profile.
- [ ] Interrupt a download and confirm the next attempt safely resumes or replaces only the partial asset.
- [ ] Interrupt setup and confirm a retry does not mistake stale status for a live worker.
- [ ] Confirm a genuinely active worker blocks a second setup/APT/session operation.
- [ ] Confirm setup failure leaves a useful log and never reports READY.
- [ ] Confirm repeated launch does not reinstall an already verified guest/profile.

## Gate 3 — Desktop and session lifecycle

- [ ] Start labwc on the reference device and confirm display ownership, readable 640×480 output and correct scaling.
- [ ] Verify controller navigation, keyboard input and mouse emulation where supported.
- [ ] Verify audio output and network access from the guest without taking over muOS services.
- [ ] Start and exit each desktop profile that is advertised as supported in the stable UI.
- [ ] Start one known GUI application from APP DECK, close it, and confirm Comet returns automatically.
- [ ] Confirm child processes are terminated and the process group is reaped.
- [ ] Confirm loop and bind mounts are detached after normal exit and after a failed launch.
- [ ] Confirm the Quick Panel's return request works on each supported display backend.

## Gate 4 — THE FORGE and package safety

- [ ] Refresh Trixie APT indexes from the guest only.
- [ ] Install one small package, verify its dpkg state, and refresh the catalogue.
- [ ] Remove that package with the explicit confirmation flow.
- [ ] Verify dependency handling, noninteractive operation and useful error output.
- [ ] Confirm an unavailable or non-allowlisted package cannot reach APT.
- [ ] Confirm no command changes muOS host APT/dpkg state.
- [ ] Confirm a failed APT task releases the shared lock and cleans up mounts.
- [ ] Confirm a live APT task cannot overlap setup or a desktop session.

## Gate 5 — UPLINK and diagnostics

- [ ] Every displayed Wi-Fi, hotspot and Bluetooth state comes from a real host probe.
- [ ] Every enabled toggle performs its advertised host action and reports the actual result.
- [ ] Unsupported operations are visibly unavailable; no fake success state is possible.
- [ ] Rt:Tailscale-M integration does not start a second owner for the Tailscale daemon.
- [ ] Diagnostics distinguish unknown, unavailable, not installed, busy, failed and cleanup-required.
- [ ] Export is opt-in and contains no passwords, Wi-Fi credentials, account IDs, serial numbers or personal file paths beyond what is strictly needed.
- [ ] The exported report is readable and useful enough to diagnose a failed test without collecting private content.

## Gate 6 — Stability and usability

- [ ] All screens fit native 640×480 without clipped content or overlapping controls.
- [ ] Every primary screen and action can be used with the handheld controls.
- [ ] Important status text remains readable at native resolution.
- [ ] No navigation or rendering regression after repeated tab cycling and catalogue filtering.
- [ ] A 30-minute idle Comet session does not show unbounded memory/log growth.
- [ ] Repeated desktop launch/return cycles do not leak mounts, processes or input grabs.
- [ ] A low-storage, read-only-card, missing-network and missing-profile case fails clearly and safely.

## Evidence required for each hardware check

Record the Comet version, device, muOS version, selected storage slot, test steps, result and relevant redacted log excerpt. Use screenshots only when captured from the real target hardware. CI screenshots or desktop mock-ups are not hardware evidence.

## Release blockers

Do not publish stable while any of these remain:

- a false READY state;
- two conflicting Debian workers can run at once;
- an operation cannot release or account for its mounts;
- Comet cannot return after a supervised session;
- UI input can bypass the package allowlist or host boundary;
- a supported feature is represented by a non-functional control;
- a crash or interrupted setup can corrupt an existing verified guest without a safe recovery path.

A failed gate is not a reason to hide the test. It is a reason to keep the release in development.
