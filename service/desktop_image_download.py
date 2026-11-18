#!/usr/bin/env python3
"""Download a published Void Desk OS disk image for the H700 target.

This is deliberately NOT a Void Desk MUX-app downloader. It accepts only the
named Debian Trixie ARM64 + labwc OS image asset from a tagged OS release.
The image is staged on the user-selected SD card; no flashing, partitioning,
bootloader changes or installation are performed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import BinaryIO, Any

REPOSITORY = "SilverCrow2323/Void-Desk-Project"
RELEASES_API = "https://api.github.com/repos/{}/releases?per_page=50".format(REPOSITORY)
OS_TAG_PREFIX = "voiddesk-os-v"
IMAGE_NAME = "VoidDeskOS-RG35XX-H-Debian-Trixie-labwc.img.xz"
IMAGE_FORMAT = "img.xz"
IMAGE_PROFILE = {
    "device": "Anbernic RG35XX H",
    "soc": "Allwinner H700",
    "architecture": "arm64",
    "distribution": "Debian Trixie",
    "compositor": "labwc",
}
SLOTS = {"tf1": Path("/mnt/mmc"), "tf2": Path("/mnt/sdcard")}
STAGING_RELATIVE = Path("MUOS") / "CometDesk" / "OS-Staging" / "VoidDeskOS"
CHUNK_SIZE = 256 * 1024
MAX_IMAGE_BYTES = 32 * 1024 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ImageReleaseUnavailable(RuntimeError):
    pass


def _clean(value: str) -> str:
    return str(value).replace("|", "/").replace("\\r", " ").replace("\\n", " ")[:220]


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
        if _unescape_mount_field(fields[1]) == str(root):
            return True, "ro" in fields[3].split(",")
    return False, True


def select_os_asset(releases: list[dict[str, Any]]) -> dict[str, Any]:
    """Select only the pinned OS image asset; a .muxapp can never match."""
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = str(release.get("tag_name") or "")
        if not tag.startswith(OS_TAG_PREFIX):
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("name") != IMAGE_NAME:
                continue
            digest = str(asset.get("digest") or "")
            if not digest.startswith("sha256:"):
                continue
            digest = digest.split(":", 1)[1].lower()
            try:
                size = int(asset.get("size") or 0)
            except (TypeError, ValueError):
                continue
            url = str(asset.get("browser_download_url") or "")
            if not HEX_SHA256.fullmatch(digest):
                continue
            if not (0 < size <= MAX_IMAGE_BYTES):
                continue
            if not url.startswith("https://github.com/{}/releases/download/".format(REPOSITORY)):
                continue
            if not url.endswith("/" + IMAGE_NAME):
                continue
            return {
                "tag": tag,
                "name": IMAGE_NAME,
                "size": size,
                "sha256": digest,
                "url": url,
                "html_url": str(release.get("html_url") or ""),
                "published_at": str(release.get("published_at") or ""),
            }
    raise ImageReleaseUnavailable(
        "Void Desk OS image is not published yet (expected Debian Trixie ARM64 + labwc)"
    )


def fetch_latest_os_asset(opener=urllib.request.urlopen) -> dict[str, Any]:
    request = urllib.request.Request(
        RELEASES_API,
        headers={
            "User-Agent": "CometDesk-OS-Image-Downloader/0.3",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with opener(request, timeout=20) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError("GitHub release catalogue returned HTTP {}".format(
                getattr(response, "status", "unknown")
            ))
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("GitHub returned an invalid release catalogue")
    return select_os_asset(payload)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stream_download(response: BinaryIO, destination: Path, expected_size: int,
                    expected_sha256: str, status_path: Path,
                    location: str = "") -> None:
    """Download to a partial file, fsync, and verify size + SHA-256."""
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
                    raise ValueError("download exceeded the published image size")
                output.write(block)
                digest.update(block)
                now = time.monotonic()
                if now - last_update >= 0.2:
                    percent = int(received * 100 / expected_size) if expected_size else 0
                    write_status(status_path, "DOWNLOADING", percent,
                                 "Downloading Void Desk OS " + IMAGE_FORMAT, location)
                    last_update = now
            output.flush()
            os.fsync(output.fileno())
        if received != expected_size:
            raise ValueError("image size mismatch: {} of {} bytes".format(
                received, expected_size
            ))
        if digest.hexdigest().lower() != expected_sha256.lower():
            raise ValueError("image SHA-256 verification failed")
    except Exception:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _safe_staging_directory(root: Path) -> Path:
    current = root
    for component in STAGING_RELATIVE.parts:
        current = current / component
        if current.is_symlink():
            raise RuntimeError("refusing symbolic-link storage path: {}".format(current))
        current.mkdir(mode=0o755, exist_ok=True)
        if not current.is_dir():
            raise RuntimeError("storage path is not a directory: {}".format(current))
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise RuntimeError("OS image staging path escaped the selected SD card")
    return resolved


def download(slot: str, app_dir: Path, mounts_file: str = "/proc/mounts",
             opener=urllib.request.urlopen) -> Path:
    status_path = app_dir / "data" / "desktop-image-download.status"
    write_status(status_path, "CHECKING_RELEASE", 0, "Looking for a Void Desk OS image")
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
        raise RuntimeError("selected storage is unavailable: " + str(exc)) from exc
    if root_real != root or not root_real.is_dir():
        raise RuntimeError("selected storage root is not a trusted mount directory")

    asset = fetch_latest_os_asset(opener)
    staging = _safe_staging_directory(root_real)
    target = staging / asset["name"]
    checksum = target.with_name(target.name + ".sha256")
    if target.is_symlink() or checksum.is_symlink():
        raise RuntimeError("existing OS image or checksum is a symbolic link")
    if target.exists():
        if not target.is_file():
            raise RuntimeError("existing OS image is not a regular file")
        if target.stat().st_size == asset["size"] and sha256_file(target) == asset["sha256"]:
            checksum.write_text("{}  {}\n".format(asset["sha256"], asset["name"]),
                                encoding="ascii")
            write_status(status_path, "DONE", 100, "Void Desk OS image already verified",
                         str(target))
            return target
        raise RuntimeError("a different OS image already exists; it was left untouched")

    partial = target.with_name(target.name + ".part")
    if partial.is_symlink():
        raise RuntimeError("partial OS image path is a symbolic link")
    free_bytes = os.statvfs(str(staging)).f_bavail * os.statvfs(str(staging)).f_frsize
    if free_bytes < asset["size"] + 64 * 1024 * 1024:
        raise RuntimeError("not enough free space for the compressed OS image")

    request = urllib.request.Request(
        asset["url"],
        headers={"User-Agent": "CometDesk-OS-Image-Downloader/0.3",
                 "Accept": "application/octet-stream"},
    )
    write_status(status_path, "DOWNLOADING", 0,
                 "Downloading {} ({})".format(asset["tag"], asset["name"]),
                 str(target))
    try:
        with opener(request, timeout=60) as response:
            if getattr(response, "status", 200) != 200:
                raise RuntimeError("OS image server returned HTTP {}".format(
                    getattr(response, "status", "unknown")
                ))
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) != asset["size"]:
                raise RuntimeError("published OS image length did not match release metadata")
            stream_download(response, target, asset["size"], asset["sha256"],
                            status_path, str(target))
        os.replace(partial, target)
        checksum.write_text("{}  {}\n".format(asset["sha256"], asset["name"]),
                            encoding="ascii")
        write_status(status_path, "DONE", 100,
                     "OS image verified; boot hand-off is a separate step",
                     str(target))
        return target
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", required=True, choices=sorted(SLOTS))
    args = parser.parse_args()
    app_dir = Path(os.environ.get("COMET_DESK_APP_DIR",
                                  Path(__file__).resolve().parents[1]))
    status_path = app_dir / "data" / "desktop-image-download.status"
    try:
        target = download(args.slot, app_dir)
    except ImageReleaseUnavailable as exc:
        write_status(status_path, "NOT_PUBLISHED", 0, str(exc))
        print("[desktop-image] {}".format(exc), file=sys.stderr)
        return 3
    except (OSError, RuntimeError, ValueError, urllib.error.URLError) as exc:
        write_status(status_path, "FAILED", 0, str(exc))
        print("[desktop-image] ERROR: {}".format(exc), file=sys.stderr)
        return 1
    print("[desktop-image] verified: {}".format(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
