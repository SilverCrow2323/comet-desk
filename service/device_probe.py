#!/usr/bin/env python3
"""Read-only hardware, firmware and storage probe for Comet Desk.

No shell commands, writes, mounts, formatting or privilege escalation.
Unknown values remain unknown; the RG35XX H baseline is not substituted
for live measurements.
"""
from __future__ import annotations

import json
import os
import platform
import re
from pathlib import Path
from typing import Any

REFERENCE = {
    "device": "Anbernic RG35XX H",
    "soc": "Allwinner H700",
    "architecture": "aarch64",
    "ram_bytes": 1024 ** 3,
    "display": {"width": 640, "height": 480},
    "firmware": "muOS Andromeda 2606.0",
    "tf1_nominal_bytes": 64_000_000_000,
}

MUOS_MOUNT_CANDIDATES = (
    ("/mnt/mmc", "TF1 candidate"),
    ("/mnt/sdcard", "TF2 candidate"),
)


def read_text(path: str | Path) -> str | None:
    try:
        value = Path(path).read_bytes().replace(b"\x00", b" ").decode(
            "utf-8", errors="replace"
        ).strip()
        return value or None
    except (OSError, ValueError):
        return None


def parse_meminfo() -> dict[str, int | None]:
    raw = read_text("/proc/meminfo") or ""
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB", raw, re.MULTILINE)
    total = int(match.group(1)) * 1024 if match else None
    return {"total_bytes": total}


def _mounts() -> list[dict[str, str]]:
    result = []
    raw = read_text("/proc/mounts") or ""
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        # proc mount fields escape spaces as octal sequences.
        unescape = lambda s: re.sub(
            r"\\([0-7]{3})",
            lambda m: chr(int(m.group(1), 8)),
            s,
        )
        result.append({
            "source": unescape(fields[0]),
            "mount_point": unescape(fields[1]),
            "filesystem": fields[2],
            "options": fields[3],
        })
    return result


def _filesystem_stats(mount_point: str) -> dict[str, int] | None:
    try:
        st = os.statvfs(mount_point)
        block = st.f_frsize or st.f_bsize
        total = st.f_blocks * block
        free = st.f_bfree * block
        available = st.f_bavail * block
        return {
            "total_bytes": total,
            "used_bytes": max(0, total - free),
            "available_bytes": available,
        }
    except OSError:
        return None


def _block_size_bytes(source: str) -> int | None:
    """Resolve a /dev/mmcblk partition to its parent disk size, if possible."""
    name = Path(source).name
    if not name.startswith("mmcblk"):
        return None
    # Partition names are mmcblk0p1; the parent is mmcblk0.
    parent = re.sub(r"p\d+$", "", name)
    if parent == name:
        parent = name
    size_text = read_text(Path("/sys/class/block") / parent / "size")
    if not size_text or not size_text.isdigit():
        return None
    # Linux block sysfs 'size' is expressed in 512-byte sectors.
    return int(size_text) * 512


def storage_inventory() -> list[dict[str, Any]]:
    mounts = _mounts()
    by_point = {item["mount_point"]: item for item in mounts}
    found = []
    for mount_point, slot_hint in MUOS_MOUNT_CANDIDATES:
        mount = by_point.get(mount_point)
        if not mount:
            # A candidate may be a parent directory with a mounted child;
            # don't invent a mount or report its parent directory as a card.
            continue
        stats = _filesystem_stats(mount_point)
        if not stats:
            continue
        source = mount["source"]
        found.append({
            "slot_hint": slot_hint,
            "mount_point": mount_point,
            "source": source,
            "read_only": "ro" in mount["options"].split(","),
            "filesystem": mount["filesystem"],
            "filesystem_capacity_bytes": stats["total_bytes"],
            "used_bytes": stats["used_bytes"],
            "available_bytes": stats["available_bytes"],
            "block_device_capacity_bytes": _block_size_bytes(source),
            "capacity_note": (
                "Block-device size is unavailable; filesystem capacity shown."
                if _block_size_bytes(source) is None
                else "Block-device and filesystem capacity are reported separately."
            ),
        })
    return found


def device_identity() -> dict[str, Any]:
    model = (
        read_text("/proc/device-tree/model")
        or read_text("/sys/firmware/devicetree/base/model")
    )
    compatible = (
        read_text("/proc/device-tree/compatible")
        or read_text("/sys/firmware/devicetree/base/compatible")
    )
    machine = platform.machine().lower()
    is_arm64 = machine in ("aarch64", "arm64")
    model_text = (model or "").lower()
    compatible_text = (compatible or "").lower()
    is_rg35xx_h = "rg35xx-h" in model_text or "rg35xx h" in model_text
    is_h700_hint = "h700" in compatible_text or "sun50i-h700" in compatible_text
    return {
        "model": model,
        "compatible": compatible,
        "architecture": machine or None,
        "is_arm64": is_arm64,
        "rg35xx_h_match": is_rg35xx_h,
        "h700_match": is_h700_hint,
        "confidence": "device-tree" if model or compatible else "architecture-only",
    }


def firmware_info() -> dict[str, Any]:
    candidates = (
        "/etc/os-release",
        "/usr/lib/os-release",
        "/mnt/mmc/MUOS/version.txt",
        "/mnt/mmc/MUOS/version",
    )
    metadata = {}
    for candidate in candidates:
        value = read_text(candidate)
        if value:
            metadata[candidate] = value[:2048]
    combined = "\n".join(metadata.values()).lower()
    is_muos = "muos" in combined or "mustardos" in combined
    if "andromeda" in combined or "2606.0" in combined:
        release = "Andromeda 2606.0"
        confidence = "release-marker"
    else:
        release = None
        confidence = "unknown"
    return {
        "family": "muOS" if is_muos else None,
        "release": release,
        "confidence": confidence,
        "metadata_sources": list(metadata.keys()),
    }


def probe() -> dict[str, Any]:
    identity = device_identity()
    return {
        "schema_version": 1,
        "probe": "comet-device-probe",
        "read_only": True,
        "reference_profile": "rg35xx-h-muos-andromeda",
        "device": identity,
        "memory": parse_meminfo(),
        "firmware": firmware_info(),
        "storage": storage_inventory(),
        "display_reference": REFERENCE["display"],
        "baseline": {
            "device": REFERENCE["device"],
            "soc": REFERENCE["soc"],
            "ram_bytes": REFERENCE["ram_bytes"],
            "tf1_nominal_bytes": REFERENCE["tf1_nominal_bytes"],
            "note": "Reference values only; live measurements above take precedence.",
        },
    }


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2, sort_keys=True))
