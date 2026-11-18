#!/usr/bin/env python3
"""Download the pinned, published Void Desk muOS installer into a chosen ARCHIVE slot.

The helper never installs a MUX package. It stages one official release asset,
validates its published SHA-256, and atomically moves it into ARCHIVE so the
user can install it with muOS Archive Manager.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import BinaryIO

RELEASE_TAG = "v10.2.0"
ASSET_NAME = "VoidDesk_v10.2.0.muxapp"
ASSET_SIZE = 3_305_314
ASSET_SHA256 = "c454615d995101f3db2cb8b7841a2a46bb32d7e0bae2d521dcd455f9991d12f5"
ASSET_URL = (
    "https://github.com/SilverCrow2323/Void-Desk-Project/releases/download/"
    "v10.2.0/VoidDesk_v10.2.0.muxapp"
)
SLOTS = {"tf1": Path("/mnt/mmc"), "tf2": Path("/mnt/sdcard")}
CHUNK_SIZE = 64 * 1024


def _clean(value: str) -> str:
    return str(value).replace("|", "/").replace("\r", " ").replace("\n", " ")[:220]


def write_status(path: Path, state: str, percent: int, message: str,
                 location: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "{}|{}|{}|{}\n".format(
        state, max(0, min(100, int(percent))), _clean(message), _clean(location)
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _unescape_mount_field(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def mounted_slot(slot: str, mounts_file: str = "/proc/mounts") -> tuple[bool, bool]:
    """Return (mounted, read_only) for one fixed muOS mount candidate."""
    root = SLOTS.get(slot)
    if root is None:
        return False, True
    try:
        lines = Path(mounts_file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False, True
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            continue
        mount_point = _unescape_mount_field(fields[1])
        if mount_point == str(root):
            return True, "ro" in fields[3].split(",")
    return False, True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stream_download(response: BinaryIO, destination: Path, expected_size: int,
                    expected_sha256: str, status_path: Path,
                    location: str = "") -> None:
    """Stream, fsync and verify a payload before the caller activates it."""
    part = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    received = 0
    last_update = 0.0
    try:
        with part.open("wb") as output:
            while True:
                block = response.read(CHUNK_SIZE)
                if not block:
                    break
                received += len(block)
                if received > expected_size:
                    raise ValueError("download exceeded the published asset size")
                output.write(block)
                digest.update(block)
                now = time.monotonic()
                if now - last_update >= 0.2:
                    percent = int(received * 100 / expected_size) if expected_size else 0
                    write_status(status_path, "DOWNLOADING", percent,
                                 "Downloading Void Desk " + RELEASE_TAG, location)
                    last_update = now
            output.flush()
            os.fsync(output.fileno())
        if received != expected_size:
            raise ValueError("download size mismatch: {} of {} bytes".format(
                received, expected_size
            ))
        if digest.hexdigest().lower() != expected_sha256.lower():
            raise ValueError("SHA-256 verification failed")
    except Exception:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def download(slot: str, app_dir: Path, mounts_file: str = "/proc/mounts",
             opener=urllib.request.urlopen) -> Path:
    status_path = app_dir / "data" / "desktop-download.status"
    write_status(status_path, "CHECKING", 0, "Checking target storage")
    if slot not in SLOTS:
        raise ValueError("unknown storage slot")
    root = SLOTS[slot]
    is_mounted, read_only = mounted_slot(slot, mounts_file)
    if not is_mounted:
        raise RuntimeError("{} is not mounted".format(slot.upper()))
    if read_only:
        raise RuntimeError("{} is mounted read-only".format(slot.upper()))

    try:
        root_real = root.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError("storage root is unavailable: " + str(exc)) from exc
    if root_real != root or not root_real.is_dir():
        raise RuntimeError("storage root is not a trusted mount directory")

    archive_dir = root_real / "ARCHIVE"
    if archive_dir.is_symlink():
        raise RuntimeError("ARCHIVE must not be a symbolic link")
    archive_dir.mkdir(mode=0o755, exist_ok=True)
    if not archive_dir.is_dir() or not os.access(str(archive_dir), os.W_OK):
        raise RuntimeError("ARCHIVE is not writable")
    storage_stats = os.statvfs(str(archive_dir))
    free_bytes = storage_stats.f_bavail * storage_stats.f_frsize
    if free_bytes < ASSET_SIZE + 2 * 1024 * 1024:
        raise RuntimeError("not enough free space in ARCHIVE")

    target = archive_dir / ASSET_NAME
    sidecar = target.with_name(target.name + ".sha256")
    if target.is_symlink() or sidecar.is_symlink():
        raise RuntimeError("existing package or checksum is a symbolic link")
    if target.exists():
        if not target.is_file():
            raise RuntimeError("existing target is not a regular file")
        if target.stat().st_size == ASSET_SIZE and sha256_file(target) == ASSET_SHA256:
            sidecar.write_text("{}  {}\\n".format(ASSET_SHA256, ASSET_NAME),
                               encoding="ascii")
            write_status(status_path, "DONE", 100, "Already downloaded and verified",
                         str(target))
            return target
        raise RuntimeError("a different file already exists; it was left untouched")

    part = target.with_name(target.name + ".part")
    if part.is_symlink():
        raise RuntimeError("partial download path is a symbolic link")
    part.unlink(missing_ok=True)
    request = urllib.request.Request(
        ASSET_URL,
        headers={
            "User-Agent": "CometDesk-DesktopSetup/0.2",
            "Accept": "application/octet-stream",
        },
    )
    write_status(status_path, "DOWNLOADING", 0, "Connecting to GitHub Releases",
                 str(target))
    try:
        with opener(request, timeout=30) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError("GitHub returned HTTP {}".format(status))
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) != ASSET_SIZE:
                raise RuntimeError("published asset length did not match the pinned release")
            stream_download(response, target, ASSET_SIZE, ASSET_SHA256,
                            status_path, str(target))
        os.replace(part, target)
        sidecar = target.with_name(target.name + ".sha256")
        sidecar.write_text("{}  {}\n".format(ASSET_SHA256, ASSET_NAME),
                           encoding="ascii")
        write_status(status_path, "DONE", 100,
                     "Verified. Open muOS Archive Manager to install.",
                     str(target))
        return target
    except Exception:
        part.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", required=True, choices=sorted(SLOTS))
    args = parser.parse_args()
    app_dir = Path(os.environ.get("COMET_DESK_APP_DIR", Path(__file__).resolve().parents[1]))
    status_path = app_dir / "data" / "desktop-download.status"
    try:
        target = download(args.slot, app_dir)
    except (OSError, RuntimeError, ValueError, urllib.error.URLError) as exc:
        write_status(status_path, "FAILED", 0, str(exc))
        print("[desktop-download] ERROR: {}".format(exc), file=sys.stderr)
        return 1
    print("[desktop-download] verified: {}".format(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
