#!/usr/bin/env python3
"""Build a self-contained AArch64 muOS .muxapp for Comet Desk."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VOID_DESK_RUNTIME_COMMIT = "0fd1447bcf9f31a5e812f78b9e2afed4db01cce7"
RUNTIME_FILES = {
    "lib/love": "lib/love",
    "lib/liblove-11.5.so": "lib/liblove-11.5.so",
    "lib/libluajit-5.1.so.2": "lib/libluajit-5.1.so.2",
}
REQUIRED = (
    "mux_launch.sh", "love/main.lua", "love/conf.lua", "love/device_probe.lua", "love/diagnostics_report.lua",
)
AARCH64_MACHINE = 183
LOVE_BLOB_SHA1 = "f28fbe1f41b32708a4d80ed58a92f12cdfd8f0da"
LOVE_RUNTIME_SOURCE_URL = "https://raw.githubusercontent.com/SilverCrow2323/dolphin-rt-core/79bdfc7707fd0785828e7a3f1146e775a6f312/Core_History/Dolphin%20RtCore%20for%20MuOS%20v11.5.00%20Triptych/Flavour%20III%20%7C%20'Frontendone'%20%5B%20Full%20L%C3%96VE%20Frontend%20GUI%20%5D/DolphinUI/lib/liblove-11.5.so"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def fetch_runtime(destination: Path) -> None:
    base = (
        "https://raw.githubusercontent.com/SilverCrow2323/"
        f"Void-Desk-Project/{VOID_DESK_RUNTIME_COMMIT}/"
    )
    destination.mkdir(parents=True, exist_ok=True)
    for relative, source in RUNTIME_FILES.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        url = LOVE_RUNTIME_SOURCE_URL if relative == "lib/liblove-11.5.so" else base + source
        request = urllib.request.Request(url, headers={"User-Agent": "CometDesk-builder"})
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read(64 * 1024 * 1024)
        if len(payload) < 64:
            raise RuntimeError(f"runtime file is unexpectedly small: {relative}")
        if relative == "lib/liblove-11.5.so" and git_blob_sha(payload) != LOVE_BLOB_SHA1:
            raise RuntimeError("pinned LÖVE shared library failed its Git blob checksum")
        if payload[:4] != b"\x7fELF" or payload[4] != 2 or payload[5] != 1:
            raise RuntimeError(f"{relative} is not a 64-bit little-endian ELF")
        machine = int.from_bytes(payload[18:20], "little")
        if machine != AARCH64_MACHINE:
            raise RuntimeError(f"{relative} is not an AArch64 binary (ELF machine {machine})")
        target.write_bytes(payload)
        target.chmod(0o755 if relative == "lib/love" else 0o644)


def zip_timestamp():
    epoch = max(int(os.environ.get("SOURCE_DATE_EPOCH", "315532800")), 315532800)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).timetuple()[:6]


def validate_archive(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if not infos:
                return ["archive is empty"]
            top = set()
            seen = set()
            for item in infos:
                name = item.filename
                member = PurePosixPath(name)
                if not name or "\\" in name or member.is_absolute() or ".." in member.parts:
                    errors.append(f"unsafe archive path: {name!r}")
                    continue
                if name in seen:
                    errors.append(f"duplicate archive entry: {name}")
                seen.add(name)
                if member.parts:
                    top.add(member.parts[0])
                mode = (item.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    errors.append(f"symlink is not allowed: {name}")
            if top != {"CometDesk"}:
                errors.append("archive must contain exactly one CometDesk/ root")
            for required in REQUIRED:
                if "CometDesk/" + required not in seen:
                    errors.append(f"required file missing: {required}")
            for required in RUNTIME_FILES:
                name = "CometDesk/" + required
                if name not in seen:
                    errors.append(f"runtime file missing: {required}")
                    continue
                data = archive.read(name)
                if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
                    errors.append(f"invalid AArch64 ELF: {required}")
                elif int.from_bytes(data[18:20], "little") != AARCH64_MACHINE:
                    errors.append(f"wrong ELF machine: {required}")
            launcher = next((item for item in infos if item.filename == "CometDesk/mux_launch.sh"), None)
            if launcher and not (((launcher.external_attr >> 16) & 0o111) != 0):
                errors.append("mux_launch.sh is not executable in the archive")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"cannot read archive: {exc}")
    return errors


def build(output: Path) -> Path:
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            raise RuntimeError(f"required project file missing: {relative}")
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix="comet-muxapp-") as temp:
        staging = Path(temp)
        package = staging / "CometDesk"
        package.mkdir()
        for relative in REQUIRED:
            target = package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
            if relative == "mux_launch.sh":
                target.chmod(0o755)
        fetch_runtime(package)
        (package / "data").mkdir(exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        timestamp = zip_timestamp()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
            for path in sorted(package.rglob("*")):
                if not path.is_file():
                    continue
                name = path.relative_to(staging).as_posix()
                info = zipfile.ZipInfo(name, date_time=timestamp)
                mode = stat.S_IMODE(path.stat().st_mode)
                info.external_attr = (stat.S_IFREG | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    errors = validate_archive(output)
    if errors:
        output.unlink(missing_ok=True)
        raise RuntimeError("; ".join(errors))
    digest = sha256_file(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii"
    )
    print(f"[muxapp] OK: {output} ({output.stat().st_size / 1048576:.1f} MiB)")
    print(f"[muxapp] SHA-256: {digest}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "CometDesk-dev.muxapp")
    args = parser.parse_args()
    try:
        build(args.output)
    except (OSError, RuntimeError, urllib.error.URLError) as exc:
        print(f"[muxapp] ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
