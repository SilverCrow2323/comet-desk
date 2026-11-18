#!/usr/bin/env python3
"""Comet Desk's in-process XFCE environment manager for muOS / Allwinner H700.

This is part of Comet Desk. It does not launch or invoke the Void Desk MUX app,
Archive Manager, or another installer. It downloads the same pinned XFCE image
seed used by Void Desk, expands it, builds the ARM64 root filesystem in-place,
and launches Xorg/XFCE directly in a chroot. Only ordinary host kernel tools
(mount, losetup, chroot and apt-get inside the guest) are used.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import BinaryIO

# This pin is the exact XFCE image seed used by Void Desk's H700 bootstrap.
VOID_DESK_SOURCE_COMMIT = "0fd1447bcf9f31a5e812f78b9e2afed4db01cce7"
IMAGE_SEED_URL = (
    "https://raw.githubusercontent.com/SilverCrow2323/Void-Desk-Project/"
    + VOID_DESK_SOURCE_COMMIT + "/assets/xfce.img.gz"
)
IMAGE_SEED_GIT_BLOB_SHA1 = "9a9571d17f94dc9c8993782a4df4126833e47e8b"
IMAGE_SEED_SIZE = 4_181_220
UBUNTU_BASE_URL = (
    "https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/"
    "ubuntu-base-24.04.3-base-arm64.tar.gz"
)
UBUNTU_BASE_SIZE = 29_870_000
UBUNTU_BASE_SHA256 = "7b2dced6dd56ad5e4a813fa25c8de307b655fdabc6ea9213175a92c48dabb048"
UBUNTU_SOURCES = """deb http://ports.ubuntu.com/ubuntu-ports noble main universe
deb http://ports.ubuntu.com/ubuntu-ports noble-updates main universe
deb http://ports.ubuntu.com/ubuntu-ports noble-security main universe
"""
PACKAGES = (
    "ca-certificates xserver-xorg-core xserver-xorg-video-fbdev "
    "xserver-xorg-input-evdev xinit x11-xserver-utils dbus dbus-x11 "
    "xfce4-session xfwm4 xfce4-panel xfce4-settings xfdesktop4 "
    "xfce4-terminal thunar qjoypad matchbox-keyboard fonts-dejavu-core "
    "procps nano zenity xfce4-taskmanager xdotool x11-utils alsa-utils "
    "pulseaudio pavucontrol bluez blueman gvfs gvfs-backends udisks2 "
    "thunar-volman xarchiver"
)
SLOTS = {"tf1": Path("/mnt/mmc"), "tf2": Path("/mnt/sdcard")}
STAGING_RELATIVE = Path("MUOS") / "CometDesk" / "Desktop"
MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
CHUNK_SIZE = 256 * 1024
APP_ENV = {"HOME": "/root", "USER": "root", "LOGNAME": "root",
           "SHELL": "/bin/bash", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}


class SetupError(RuntimeError):
    pass


def clean_status(value: str) -> str:
    return str(value).replace("|", "/").replace(chr(10), " ").replace(chr(13), " ")[:220]


def write_status(app_dir: Path, state: str, percent: int, message: str,
                 location: str = "") -> None:
    status = app_dir / "data" / "desktop-environment.status"
    status.parent.mkdir(parents=True, exist_ok=True)
    payload = "{}|{}|{}|{}\n".format(
        state, max(0, min(100, int(percent))), clean_status(message),
        clean_status(location),
    )
    temporary = status.with_suffix(status.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, status)


def _run(command: list[str], *, log: BinaryIO | None = None,
         timeout: int | None = None, env: dict[str, str] | None = None) -> None:
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=log or subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False, timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError("{}: {}".format(command[0], exc)) from exc
    if result.returncode != 0:
        raise SetupError("{} exited with status {}".format(command[0], result.returncode))


def mount_table_from_text(contents: str) -> list[tuple[str, str, str]]:
    import re
    rows = []
    for line in contents.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            mountpoint = re.sub(
                r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)),
                fields[1],
            )
            rows.append((fields[0], mountpoint, fields[3]))
    return rows


def mount_table(path: str = "/proc/mounts") -> list[tuple[str, str, str]]:
    try:
        return mount_table_from_text(
            Path(path).read_text(encoding="utf-8", errors="replace")
        )
    except OSError as exc:
        raise SetupError("cannot read mount table: " + str(exc)) from exc


def mount_state(path: Path) -> tuple[bool, bool]:
    target = str(path)
    for _source, mountpoint, options in mount_table():
        if mountpoint == target:
            return True, "ro" not in options.split(",")
    return False, False


def mounted_slot(slot: str) -> tuple[bool, bool]:
    root = SLOTS.get(slot)
    if root is None:
        return False, False
    return mount_state(root)


def safe_staging_directory(root: Path) -> Path:
    current = root
    for component in STAGING_RELATIVE.parts:
        current = current / component
        if current.is_symlink():
            raise SetupError("refusing symbolic-link path: " + str(current))
        current.mkdir(mode=0o755, exist_ok=True)
        if not current.is_dir():
            raise SetupError("storage path is not a directory: " + str(current))
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise SetupError("desktop image path escaped the selected storage")
    return resolved


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(("blob {}\0".format(len(data))).encode("ascii"))
    digest.update(data)
    return digest.hexdigest()


def download_verified(url: str, destination: Path, *, expected_size: int | None,
                      expected_sha256: str | None = None,
                      expected_git_blob_sha1: str | None = None,
                      status: tuple[Path, str, int, str] | None = None,
                      max_bytes: int = 128 * 1024 * 1024,
                      opener=urllib.request.urlopen) -> Path:
    part = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    received = 0
    git_payload = bytearray() if expected_git_blob_sha1 else None
    if part.is_symlink() or destination.is_symlink():
        raise SetupError("download destination must not be a symbolic link")
    request = urllib.request.Request(
        url, headers={"User-Agent": "CometDesk-DesktopEnvironment/0.3",
                      "Accept": "application/octet-stream"},
    )
    try:
        with opener(request, timeout=60) as response, part.open("wb") as output:
            if getattr(response, "status", 200) != 200:
                raise SetupError("download server returned HTTP {}".format(
                    getattr(response, "status", "unknown")
                ))
            length = response.headers.get("Content-Length")
            if length:
                length = int(length)
                if length > max_bytes or (expected_size is not None and length != expected_size):
                    raise SetupError("published download size is unexpected")
            last = 0.0
            while True:
                block = response.read(CHUNK_SIZE)
                if not block:
                    break
                received += len(block)
                if received > max_bytes:
                    raise SetupError("download exceeded the permitted size")
                if expected_size is not None and received > expected_size:
                    raise SetupError("download exceeded the pinned size")
                output.write(block)
                digest.update(block)
                if git_payload is not None:
                    git_payload.extend(block)
                if status and time.monotonic() - last >= 0.25:
                    app_dir, state, base_percent, label = status
                    write_status(app_dir, state, base_percent, label)
                    last = time.monotonic()
            output.flush()
            os.fsync(output.fileno())
        if expected_size is not None and received != expected_size:
            raise SetupError("download size mismatch: {} of {} bytes".format(
                received, expected_size
            ))
        if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
            raise SetupError("download SHA-256 verification failed")
        if expected_git_blob_sha1 and git_blob_sha1(bytes(git_payload or b"")) != expected_git_blob_sha1:
            raise SetupError("Void Desk image seed failed its pinned Git blob checksum")
        os.replace(part, destination)
        return destination
    except Exception:
        part.unlink(missing_ok=True)
        raise


def _extract_gzip_image(seed: Path, image: Path, app_dir: Path) -> None:
    part = image.with_name(image.name + ".part")
    part.unlink(missing_ok=True)
    write_status(app_dir, "EXPANDING_IMAGE", 18, "Expanding the H700 ext4 image")
    try:
        with gzip.open(seed, "rb") as source, part.open("wb") as target:
            copied = 0
            next_mark = 512 * 1024 * 1024
            while True:
                chunk = source.read(4 * 1024 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                target.write(chunk)
                if copied >= next_mark:
                    write_status(app_dir, "EXPANDING_IMAGE",
                                 min(37, 18 + copied * 19 // (4 * 1024**3)),
                                 "Expanding ext4 image ({:.1f} GiB)".format(copied / 1024**3))
                    next_mark += 512 * 1024 * 1024
            target.flush()
            os.fsync(target.fileno())
        with part.open("rb") as stream:
            stream.seek(1080)
            if stream.read(2) != b"\x53\xef":
                raise SetupError("expanded image is not an ext4 filesystem")
        os.replace(part, image)
    except Exception:
        part.unlink(missing_ok=True)
        raise


class ImageMount:
    """Own and verify the loop device and mounts created by this process."""
    def __init__(self, image: Path, mountpoint: Path, log: BinaryIO):
        self.image = image
        self.mountpoint = mountpoint
        self.log = log
        self.loop: str | None = None
        self.created_mounts: list[Path] = []

    def mount_image(self) -> None:
        if self.mountpoint.is_symlink():
            raise SetupError("desktop mountpoint is a symbolic link")
        self.mountpoint.mkdir(parents=True, exist_ok=True)
        mounted, _rw = mount_state(self.mountpoint)
        if mounted:
            raise SetupError("desktop image is already mounted; refusing a second mount")
        result = subprocess.run(["losetup", "--find", "--show", str(self.image)],
                                capture_output=True, text=True, check=False)
        if result.returncode != 0 or not result.stdout.strip().startswith("/dev/loop"):
            raise SetupError(result.stderr.strip() or "cannot allocate a loop device")
        self.loop = result.stdout.strip()
        try:
            _run(["mount", self.loop, str(self.mountpoint)], log=self.log, timeout=30)
            mounted, _rw = mount_state(self.mountpoint)
            if not mounted:
                raise SetupError("loop mount command returned but mount state is absent")
            self.created_mounts.append(self.mountpoint)
        except Exception:
            subprocess.run(["losetup", "-d", self.loop], capture_output=True)
            self.loop = None
            raise

    def bind(self, source: Path, target: Path, *, filesystem: str | None = None) -> None:
        if not source.exists():
            return
        if target.is_symlink():
            raise SetupError("bind mount target is a symbolic link: " + str(target))
        target.mkdir(parents=True, exist_ok=True)
        mounted, _rw = mount_state(target)
        if mounted:
            raise SetupError("bind mount target is already mounted: " + str(target))
        command = ["mount"]
        if filesystem:
            command += ["-t", filesystem]
            command += [str(source), str(target)]
        else:
            command += ["--bind", str(source), str(target)]
        _run(command, log=self.log, timeout=20)
        mounted, _rw = mount_state(target)
        if not mounted:
            raise SetupError("bind mount could not be verified: " + str(target))
        self.created_mounts.append(target)

    def bind_host_tree(self, *, share_storage: bool) -> None:
        for relative, source, fs in (
            ("dev", Path("/dev"), None),
            ("proc", Path("proc"), "proc"),
            ("sys", Path("sys"), "sysfs"),
            ("dev/pts", Path("/dev/pts"), None),
            ("dev/shm", Path("/dev/shm"), None),
            ("dev/input", Path("/dev/input"), None),
            ("dev/snd", Path("/dev/snd"), None),
            ("dev/dri", Path("/dev/dri"), None),
            ("run/dbus", Path("/run/dbus"), None),
            ("run/udev", Path("/run/udev"), None),
            ("run/wpa_supplicant", Path("/run/wpa_supplicant"), None),
        ):
            self.bind(source, self.mountpoint / relative, filesystem=fs)
        resolv = self.mountpoint / "etc" / "resolv.conf"
        resolv.parent.mkdir(parents=True, exist_ok=True)
        if resolv.is_symlink():
            resolv.unlink()
        try:
            shutil.copyfile("/etc/resolv.conf", resolv)
        except OSError:
            pass
        if share_storage:
            for slot, source in SLOTS.items():
                if not source.is_dir():
                    continue
                target = self.mountpoint / str(source).lstrip("/")
                self.bind(source, target)

    def cleanup(self) -> bool:
        ok = True
        for target in reversed(self.created_mounts):
            mounted, _rw = mount_state(target)
            if not mounted:
                continue
            result = subprocess.run(["umount", str(target)],
                                    stdout=self.log, stderr=subprocess.STDOUT,
                                    check=False, timeout=20)
            if result.returncode != 0 or mount_state(target)[0]:
                subprocess.run(["umount", "-l", str(target)],
                               stdout=self.log, stderr=subprocess.STDOUT,
                               check=False)
                if mount_state(target)[0]:
                    ok = False
        self.created_mounts.clear()
        if self.loop:
            if any(source == self.loop for source, _mp, _opt in mount_table()):
                ok = False
            else:
                result = subprocess.run(["losetup", "-d", self.loop],
                                        stdout=self.log, stderr=subprocess.STDOUT,
                                        check=False)
                if result.returncode != 0:
                    ok = False
            if subprocess.run(["losetup", "-a"], capture_output=True,
                              text=True).stdout.find("({})".format(self.image)) >= 0:
                ok = False
            if ok:
                self.loop = None
        return ok


def _write_guest_configuration(root: Path) -> None:
    (root / "etc").mkdir(parents=True, exist_ok=True)
    (root / "etc/hostname").write_text("voiddesk\n", encoding="utf-8")
    (root / "etc/hosts").write_text(
        "127.0.0.1 localhost\n127.0.1.1 voiddesk\n", encoding="utf-8")
    (root / "etc/apt/sources.list").write_text(UBUNTU_SOURCES, encoding="utf-8")
    sources_dir = root / "etc/apt/sources.list.d"
    if sources_dir.is_dir():
        for item in sources_dir.iterdir():
            if item.is_file() and item.suffix in (".sources", ".list"):
                item.unlink()
    machine_id = __import__("uuid").uuid4().hex
    (root / "etc/machine-id").write_text(machine_id + "\n", encoding="ascii")
    dbus_id = root / "var/lib/dbus/machine-id"
    dbus_id.parent.mkdir(parents=True, exist_ok=True)
    dbus_id.write_text(machine_id + "\n", encoding="ascii")

    x11 = root / "etc/X11"
    x11.mkdir(parents=True, exist_ok=True)
    (x11 / "xorg.conf").write_text(
        '# Comet Desk // RG35XX-H framebuffer Xorg profile\n'
        'Section "Device"\n    Identifier "FBDEV"\n    Driver "fbdev"\n'
        '    Option "fbdev" "/dev/fb0"\nEndSection\n'
        'Section "Screen"\n    Identifier "Screen0"\n    Device "FBDEV"\n'
        'EndSection\nSection "ServerFlags"\n'
        '    Option "AutoAddGPU" "false"\n'
        '    Option "DontVTSwitch" "true"\nEndSection\n'
        'Section "InputClass"\n    Identifier "evdev-all"\n'
        '    MatchDevicePath "/dev/input/event*"\n    Driver "evdev"\n'
        'EndSection\n', encoding="utf-8")
    xinit = root / "root/.xinitrc"
    xinit.parent.mkdir(parents=True, exist_ok=True)
    xinit.write_text(
        '#!/bin/sh\n'
        'export NO_AT_BRIDGE=1 GTK_A11Y=none GTK_OVERLAY_SCROLLING=0\n'
        'export GSETTINGS_BACKEND=keyfile\n'
        'if [ -z "$DBUS_SESSION_BUS_ADDRESS" ] && command -v dbus-launch >/dev/null 2>&1; then\n'
        '  eval "$(dbus-launch --sh-syntax --exit-with-session)"\nfi\n'
        'xset s off -dpms 2>/dev/null\n'
        'for ctl in Master PCM Speaker Headphone; do amixer -q sset "$ctl" 80% unmute 2>/dev/null; done\n'
        'exec startxfce4\n', encoding="utf-8")
    xinit.chmod(0o755)
    settings = root / "root/.config/xfce4/xfconf/xfce-perchannel-xml"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "xfwm4.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<channel name="xfwm4" version="1.0"><property name="general" type="empty">'
        '<property name="use_compositing" type="bool" value="false"/>'
        '<property name="title_font" type="string" value="Sans Bold 8"/>'
        '</property></channel>\n', encoding="utf-8")
    gtk = root / "root/.config/gtk-3.0"
    gtk.mkdir(parents=True, exist_ok=True)
    (gtk / "settings.ini").write_text(
        "[Settings]\ngtk-font-name=Sans 8\ngtk-dialogs-use-header=false\n",
        encoding="utf-8")
    (root / ".comet-xfce-image").write_text(
        "Comet Desk built this XFCE image\n", encoding="utf-8")


def _bind_build_environment(manager: ImageMount) -> None:
    manager.bind_host_tree(share_storage=False)


def setup(slot: str, app_dir: Path) -> Path:
    if os.geteuid() != 0:
        raise SetupError("Comet Desk needs muOS app-runner root privileges for loop mounts and chroot")
    if slot not in SLOTS:
        raise SetupError("unknown storage slot")
    mounted, writable = mounted_slot(slot)
    if not mounted:
        raise SetupError(slot.upper() + " is not mounted")
    if not writable:
        raise SetupError(slot.upper() + " is mounted read-only")
    root = SLOTS[slot].resolve(strict=True)
    if root != SLOTS[slot] or not root.is_dir():
        raise SetupError("selected storage root is not a trusted mount")
    stage = safe_staging_directory(root)
    stats = os.statvfs(str(stage))
    free = stats.f_bavail * stats.f_frsize
    if free < MIN_FREE_BYTES:
        raise SetupError("XFCE setup needs at least 5 GiB free on the selected card")

    image = stage / "xfce.img"
    seed = stage / "xfce.img.gz"
    rootfs = stage / "ubuntu-base-24.04.3-base-arm64.tar.gz"
    marker = stage / ".comet-xfce-ready"
    mountpoint = app_dir / "data" / "desktop-mnt"
    log_path = app_dir / "data" / "desktop-environment.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if image.is_file() and marker.is_file():
        try:
            saved = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        if saved.get("profile") == "ubuntu-24.04-arm64-xfce":
            write_status(app_dir, "READY", 100, "XFCE image already installed", str(image))
            return image

    write_status(app_dir, "DOWNLOADING_TEMPLATE", 2, "Fetching the pinned H700 XFCE image seed")
    if not seed.exists() or seed.stat().st_size != IMAGE_SEED_SIZE:
        download_verified(IMAGE_SEED_URL, seed, expected_size=IMAGE_SEED_SIZE,
                          expected_git_blob_sha1=IMAGE_SEED_GIT_BLOB_SHA1,
                          status=(app_dir, "DOWNLOADING_TEMPLATE", 3, "Downloading XFCE image seed"))
    else:
        data = seed.read_bytes()
        if git_blob_sha1(data) != IMAGE_SEED_GIT_BLOB_SHA1:
            seed.unlink()
            download_verified(IMAGE_SEED_URL, seed, expected_size=IMAGE_SEED_SIZE,
                              expected_git_blob_sha1=IMAGE_SEED_GIT_BLOB_SHA1)
    if not image.exists():
        _extract_gzip_image(seed, image, app_dir)
    else:
        with image.open("rb") as stream:
            stream.seek(1080)
            if stream.read(2) != b"\x53\xef":
                raise SetupError("existing desktop image is not an ext4 filesystem")

    manager = ImageMount(image, mountpoint, log_path.open("ab"))
    try:
        write_status(app_dir, "PREPARING_ROOTFS", 42, "Mounting the XFCE filesystem image")
        manager.mount_image()
        if not (mountpoint / "etc/os-release").exists():
            write_status(app_dir, "DOWNLOADING_ROOTFS", 46, "Downloading official Ubuntu Base ARM64 root filesystem")
            if not rootfs.exists() or file_sha256(rootfs) != UBUNTU_BASE_SHA256:
                download_verified(UBUNTU_BASE_URL, rootfs, expected_size=None,
                                  expected_sha256=UBUNTU_BASE_SHA256,
                                  status=(app_dir, "DOWNLOADING_ROOTFS", 48, "Downloading Ubuntu Base ARM64"))
            write_status(app_dir, "EXTRACTING_ROOTFS", 55, "Extracting the verified ARM64 root filesystem")
            _run(["tar", "-xpf", str(rootfs), "-C", str(mountpoint)],
                 log=manager.log, timeout=900)
            (mountpoint / ".comet-rootfs-extracted").write_text("verified\n")
        os_release = (mountpoint / "etc/os-release").read_text(errors="replace")
        if "ID=ubuntu" not in os_release or "VERSION_ID=\"24.04\"" not in os_release:
            raise SetupError("root filesystem is not the expected Ubuntu 24.04 ARM64 base")
        _write_guest_configuration(mountpoint)
        _bind_build_environment(manager)
        policy = mountpoint / "usr/sbin/policy-rc.d"
        policy.write_text("#!/bin/sh\nexit 101\n", encoding="ascii")
        policy.chmod(0o755)
        env = dict(os.environ)
        env.update(APP_ENV)
        env["DEBIAN_FRONTEND"] = "noninteractive"
        write_status(app_dir, "INSTALLING_XFCE", 63, "Installing Xorg, XFCE and handheld input/audio packages")
        _run(["chroot", str(mountpoint), "/usr/bin/env",
              "DEBIAN_FRONTEND=noninteractive",
              "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
              "apt-get", "-o", "Acquire::ForceIPv4=true", "-o", "Acquire::Retries=2",
              "update"], log=manager.log, timeout=900, env=env)
        _run(["chroot", str(mountpoint), "/usr/bin/env",
              "DEBIAN_FRONTEND=noninteractive",
              "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
              "apt-get", "-o", "Acquire::ForceIPv4=true", "-o", "Acquire::Retries=2",
              "install", "-y", "--no-install-recommends"] + PACKAGES.split(),
             log=manager.log, timeout=2400, env=env)
        _run(["chroot", str(mountpoint), "/usr/bin/env",
              "PATH=/usr/sbin:/usr/bin:/sbin:/bin", "apt-get", "clean"],
             log=manager.log, timeout=120, env=env)
        policy.unlink(missing_ok=True)
        required = ("/usr/bin/startx", "/usr/bin/startxfce4", "/usr/bin/Xorg")
        missing = [item for item in required if not (mountpoint / item.lstrip("/")).exists()]
        if missing:
            raise SetupError("XFCE image verification failed; missing " + ", ".join(missing))
        marker.write_text(json.dumps({
            "profile": "ubuntu-24.04-arm64-xfce",
            "image": str(image),
            "template_git_blob_sha1": IMAGE_SEED_GIT_BLOB_SHA1,
            "rootfs_sha256": UBUNTU_BASE_SHA256,
            "created_at": int(time.time()),
        }, sort_keys=True), encoding="utf-8")
        write_status(app_dir, "READY", 100, "XFCE image prepared and verified", str(image))
        return image
    except Exception as exc:
        write_status(app_dir, "FAILED", 0, str(exc))
        raise
    finally:
        if not manager.cleanup():
            write_status(app_dir, "CLEANUP_REQUIRED", 0,
                         "Desktop image mount cleanup could not be verified; check the log")
        manager.log.close()


def launch(slot: str, app_dir: Path) -> int:
    if os.geteuid() != 0:
        raise SetupError("Comet Desk needs muOS app-runner root privileges to launch XFCE")
    if slot not in SLOTS:
        raise SetupError("unknown storage slot")
    mounted, writable = mounted_slot(slot)
    if not mounted:
        raise SetupError(slot.upper() + " is not mounted")
    root = SLOTS[slot].resolve(strict=True)
    stage = safe_staging_directory(root)
    image = stage / "xfce.img"
    marker = stage / ".comet-xfce-ready"
    if not image.is_file() or not marker.is_file():
        raise SetupError("XFCE has not been installed yet; run Desktop Setup first")
    state = json.loads(marker.read_text(encoding="utf-8"))
    if state.get("profile") != "ubuntu-24.04-arm64-xfce":
        raise SetupError("installed XFCE image profile is not recognized")

    mountpoint = app_dir / "data" / "desktop-mnt"
    log_path = app_dir / "data" / "desktop-environment.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_stream = log_path.open("ab")
    manager = ImageMount(image, mountpoint, log_stream)
    try:
        manager.mount_image()
        # Network, sound, input, and the user's selected SD cards are exposed
        # to the chroot. No other MUX app or desktop manager is started.
        manager.bind_host_tree(share_storage=True)
        write_status(app_dir, "RUNNING", 100, "XFCE desktop is running", str(image))
        env = dict(os.environ)
        env.update(APP_ENV)
        env["DISPLAY"] = ":0"
        env["XAUTHORITY"] = "/root/.Xauthority"
        result = subprocess.run(
            ["chroot", str(mountpoint), "/usr/bin/env",
             "HOME=/root", "USER=root", "LOGNAME=root", "SHELL=/bin/bash",
             "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
             "/usr/bin/startx", "/root/.xinitrc", "--",
             ":0", "vt1", "-novtswitch", "-keeptty"],
            stdin=subprocess.DEVNULL, stdout=log_stream,
            stderr=subprocess.STDOUT, env=env, check=False,
        )
        write_status(app_dir, "READY", 100,
                     "Desktop session ended; returned to Comet Desk")
        return result.returncode
    finally:
        clean = manager.cleanup()
        log_stream.close()
        if not clean:
            write_status(app_dir, "CLEANUP_REQUIRED", 0,
                         "Desktop returned but one or more mounts remain; inspect the log")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "session"))
    parser.add_argument("--slot", required=True, choices=sorted(SLOTS))
    parser.add_argument("--app-dir", default=os.environ.get("COMET_DESK_APP_DIR", ""))
    args = parser.parse_args()
    if not args.app_dir:
        print("COMET_DESK_APP_DIR is required", file=sys.stderr)
        return 2
    app_dir = Path(args.app_dir).resolve()
    try:
        if args.action == "setup":
            image = setup(args.slot, app_dir)
            print("[comet-desktop] prepared {}".format(image))
            return 0
        result = launch(args.slot, app_dir)
        print("[comet-desktop] XFCE session returned ({})".format(result))
        return 0
    except (SetupError, OSError, ValueError, urllib.error.URLError,
            subprocess.SubprocessError, json.JSONDecodeError) as exc:
        write_status(app_dir, "FAILED", 0, str(exc))
        print("[comet-desktop] ERROR: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
