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
import fcntl
import gzip
import hashlib
import json
import os
import select
import shutil
import signal
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
# Official Debian Trixie ARM64 OCI rootfs layer, pinned to an immutable
# debuerreotype/docker-debian-artifacts commit and its OCI sha256 digest.
DEBIAN_ARTIFACT_COMMIT = "3b26c3995c7fae47d95ba678632a3520e97054f7"
DEBIAN_ROOTFS_URL = (
    "https://raw.githubusercontent.com/debuerreotype/docker-debian-artifacts/"
    + DEBIAN_ARTIFACT_COMMIT + "/trixie/oci/blobs/rootfs.tar.gz"
)
DEBIAN_ROOTFS_SIZE = 49_778_604
DEBIAN_ROOTFS_SHA256 = "23b69c48ce5c2a6fb0681d959fa700427ad2a7cf7e6be5d25249170a1853d7ad"
DEBIAN_SOURCES = """deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware
"""
# First boot intentionally installs only what is required for a usable desktop.
# Build tools, developer runtimes and archive utilities are opt-in through THE FORGE.
BASE_PACKAGES = (
    "apt ca-certificates locales dbus dbus-x11 polkitd udisks2 gvfs gvfs-backends "
    "fonts-dejavu-core fonts-liberation nano procps sudo xdg-utils xdg-user-dirs "
    "e2fsprogs libinput-tools seatd"
)
PROFILE_PACKAGES = {
    "labwc": "labwc waybar foot swaybg mako-notifier wofi xwayland",
    "xfce": "xfce4 xfce4-goodies xfce4-terminal thunar qjoypad matchbox-keyboard "
            "xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev "
            "xinit x11-xserver-utils xdotool x11-utils xbindkeys dmenu",
    "lxde": "lxde-core lxterminal pcmanfm openbox "
            "xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev "
            "xinit x11-xserver-utils xbindkeys dmenu",
    "lxqt": "lxqt-core qterminal pcmanfm-qt "
            "xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev "
            "xinit x11-xserver-utils xbindkeys dmenu",
    "icewm": "icewm icewm-themes tint2 xterm pcmanfm "
             "xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev "
             "xinit x11-xserver-utils xbindkeys dmenu",
    "fluxbox": "fluxbox tint2 xterm pcmanfm "
               "xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev "
               "xinit x11-xserver-utils xbindkeys dmenu",
    "openbox": "openbox obconf tint2 xterm pcmanfm "
               "xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev "
               "xinit x11-xserver-utils xbindkeys dmenu",
}
DEFAULT_PROFILE = "labwc"
DESKTOP_CONFIG_REVISION = 2
DESKTOP_IMAGE_BYTES = 8 * 1024 * 1024 * 1024
SLOTS = {"tf1": Path("/mnt/mmc"), "tf2": Path("/mnt/sdcard")}
STAGING_RELATIVE = Path("MUOS") / "CometDesk" / "Desktop"
MIN_FREE_BYTES = 9 * 1024 * 1024 * 1024
CHUNK_SIZE = 256 * 1024
APP_ENV = {"HOME": "/root", "USER": "root", "LOGNAME": "root",
           "SHELL": "/bin/bash", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}


class SetupError(RuntimeError):
    pass


def clean_status(value: str) -> str:
    return str(value).replace("|", "/").replace(chr(10), " ").replace(chr(13), " ")[:220]


def write_status(app_dir: Path, state: str, percent: int, message: str,
                 location: str = "", profile: str = "") -> None:
    status = app_dir / "data" / "desktop-environment.status"
    status.parent.mkdir(parents=True, exist_ok=True)
    payload = "{}|{}|{}|{}|{}\n".format(
        state, max(0, min(100, int(percent))), clean_status(message),
        clean_status(location), clean_status(profile),
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


def apt_status_event(line: str) -> tuple[float, str] | None:
    """Decode one APT Status-Fd event into a percentage and readable message."""
    fields = line.strip().split(":")
    if not fields:
        return None
    if fields[0] == "pmstatus" and len(fields) >= 4:
        try:
            percent = float(fields[2])
        except ValueError:
            return None
        return max(0.0, min(100.0, percent)), ":".join(fields[3:])
    if fields[0] == "dlstatus":
        numeric: list[float] = []
        for value in fields[1:]:
            try:
                numeric.append(float(value))
            except ValueError:
                continue
        if len(numeric) >= 2 and numeric[-1] > 0:
            percent = numeric[-2] * 100.0 / numeric[-1]
            return max(0.0, min(100.0, percent)), "Downloading Debian packages"
    return None


def run_apt_with_progress(
    command: list[str],
    *,
    log: BinaryIO,
    timeout: int,
    env: dict[str, str] | None = None,
    on_progress=None,
) -> None:
    """Run apt-get with its machine-readable Status-Fd channel.

    Apt/dpkg output continues to the normal operation log. Progress events travel
    over a dedicated inherited descriptor, so they never corrupt the log or TUI.
    """
    apt_index = next(
        (index for index, value in enumerate(command)
         if Path(value).name == "apt-get"),
        None,
    )
    if apt_index is None:
        raise SetupError("progress runner requires an apt-get command")

    read_fd, write_fd = os.pipe()
    monitored = list(command)
    monitored[apt_index + 1:apt_index + 1] = [
        "-o", "APT::Status-Fd={}".format(write_fd)
    ]
    process = None
    buffer = b""
    eof = False
    last_percent = -1.0
    deadline = time.monotonic() + timeout

    try:
        process = subprocess.Popen(
            monitored,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            pass_fds=(write_fd,),
            start_new_session=True,
        )
        os.close(write_fd)
        write_fd = -1

        while not eof or process.poll() is None:
            if time.monotonic() >= deadline:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                raise SetupError("apt-get timed out after {} seconds".format(timeout))

            if eof:
                try:
                    process.wait(timeout=0.15)
                except subprocess.TimeoutExpired:
                    pass
                continue

            readable, _, _ = select.select([read_fd], [], [], 0.15)
            if not readable:
                continue
            chunk = os.read(read_fd, 4096)
            if not chunk:
                eof = True
                continue
            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                event = apt_status_event(raw_line.decode("utf-8", errors="replace"))
                if event is not None:
                    percent, message = event
                    last_percent = percent
                    if on_progress is not None:
                        on_progress(int(percent), clean_status(message))

        if buffer:
            event = apt_status_event(buffer.decode("utf-8", errors="replace"))
            if event is not None and on_progress is not None:
                percent, message = event
                on_progress(int(percent), clean_status(message))

        return_code = process.wait()
        if return_code != 0:
            raise SetupError("apt-get exited with status {}".format(return_code))
    except OSError as exc:
        raise SetupError("apt-get: {}".format(exc)) from exc
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        os.close(read_fd)
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


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
                      status: tuple[Path, str, int, int, str] | None = None,
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
                    app_dir, state, start_percent, end_percent, label = status
                    percent = start_percent + int((end_percent - start_percent) * received / expected_size) if expected_size else start_percent
                    write_status(app_dir, state, percent, label)
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
        attached = subprocess.run(["losetup", "-a"], capture_output=True,
                                  text=True, check=False, timeout=20)
        if attached.returncode != 0:
            raise SetupError("cannot inspect existing loop devices")
        if str(self.image) in attached.stdout:
            raise SetupError("desktop image already has a loop device; refusing a duplicate mount")
        free = subprocess.run(["losetup", "-f"], capture_output=True,
                              text=True, check=False, timeout=20)
        if free.returncode != 0 or not free.stdout.strip().startswith("/dev/loop"):
            raise SetupError(free.stderr.strip() or "cannot find a free loop device")
        candidate = free.stdout.strip()
        linked = subprocess.run(["losetup", candidate, str(self.image)],
                                capture_output=True, text=True, check=False, timeout=20)
        if linked.returncode != 0:
            raise SetupError(linked.stderr.strip() or "cannot attach the desktop image")
        self.loop = candidate
        attached = subprocess.run(["losetup", "-a"], capture_output=True,
                                  text=True, check=False, timeout=20)
        if attached.returncode != 0 or str(self.image) not in attached.stdout:
            raise SetupError("loop attachment could not be verified")
        try:
            _run(["mount", self.loop, str(self.mountpoint)], log=self.log, timeout=30)
            mounted, _rw = mount_state(self.mountpoint)
            if not mounted:
                raise SetupError("loop mount command returned but mount state is absent")
            self.created_mounts.append(self.mountpoint)
        except Exception:
            # setup()/launch() own final cleanup; keep the loop reference so
            # a failed mount cannot silently leak a loop device.
            if mount_state(self.mountpoint)[0] and self.mountpoint not in self.created_mounts:
                self.created_mounts.append(self.mountpoint)
            raise

    def bind(self, source: Path, target: Path, *, filesystem: str | None = None) -> None:
        # proc/sys are mounted by filesystem type; their source tokens ("proc",
        # "sys") are not host paths and therefore must not be stat()'d.
        if filesystem is None and not source.exists():
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
            try:
                mounted, _rw = mount_state(target)
                if not mounted:
                    continue
                result = subprocess.run(["umount", str(target)],
                                        stdout=self.log, stderr=subprocess.STDOUT,
                                        check=False, timeout=20)
                if result.returncode != 0 or mount_state(target)[0]:
                    subprocess.run(["umount", "-l", str(target)],
                                   stdout=self.log, stderr=subprocess.STDOUT,
                                   check=False, timeout=20)
                if mount_state(target)[0]:
                    ok = False
            except (OSError, subprocess.SubprocessError, SetupError):
                ok = False
        self.created_mounts.clear()
        if self.loop:
            try:
                if any(source == self.loop for source, _mp, _opt in mount_table()):
                    ok = False
                else:
                    result = subprocess.run(["losetup", "-d", self.loop],
                                            stdout=self.log, stderr=subprocess.STDOUT,
                                            check=False, timeout=20)
                    if result.returncode != 0:
                        ok = False
                loop_state = subprocess.run(["losetup", "-a"], capture_output=True,
                                            text=True, check=False, timeout=20)
                if loop_state.returncode != 0 or str(self.image) in loop_state.stdout:
                    ok = False
            except (OSError, subprocess.SubprocessError, SetupError):
                ok = False
            if ok:
                self.loop = None
        return ok


def _write_guest_configuration(root: Path) -> None:
    (root / "etc").mkdir(parents=True, exist_ok=True)
    (root / "etc/apt").mkdir(parents=True, exist_ok=True)
    (root / "etc/hostname").write_text("comet-debian\n", encoding="utf-8")
    (root / "etc/hosts").write_text(
        "127.0.0.1 localhost\n127.0.1.1 comet-debian\n", encoding="utf-8")
    (root / "etc/apt/sources.list").write_text(DEBIAN_SOURCES, encoding="utf-8")
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
        '# Comet Desk // RG35XX-H framebuffer fallback profile\n'
        'Section "Device"\n    Identifier "FBDEV"\n    Driver "fbdev"\n'
        '    Option "fbdev" "/dev/fb0"\nEndSection\n'
        'Section "Screen"\n    Identifier "Screen0"\n    Device "FBDEV"\n'
        'EndSection\nSection "ServerFlags"\n'
        '    Option "AutoAddGPU" "false"\n'
        '    Option "DontVTSwitch" "true"\nEndSection\n'
        'Section "InputClass"\n    Identifier "evdev-all"\n'
        '    MatchDevicePath "/dev/input/event*"\n    Driver "evdev"\n'
        'EndSection\n', encoding="utf-8")

    labwc = root / "root/.config/labwc"
    labwc.mkdir(parents=True, exist_ok=True)
    (labwc / "autostart").write_text(
        "waybar >/tmp/comet-waybar.log 2>&1 &\n"
        "swaybg -c '#080f1d' >/tmp/comet-swaybg.log 2>&1 &\n"
        "mako >/tmp/comet-mako.log 2>&1 &\n"
        "foot --server >/tmp/comet-foot.log 2>&1 &\n",
        encoding="utf-8",
    )
    (labwc / "rc.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<labwc_config>\n'
        '  <core><decoration>server</decoration><gap>0</gap></core>\n'
        '  <keyboard><keybind key="W-Return"><action name="Execute"><command>foot</command></action></keybind>'
        '<keybind key="W-q"><action name="Exit"/></keybind>'
        '<keybind key="m"><action name="Execute"><command>/usr/local/bin/comet-quick-panel</command></action></keybind></keyboard>\n'
        '  <mouse><default/></mouse>\n'
        '</labwc_config>\n', encoding="utf-8")

    wofi_dir = root / "root/.config/wofi"
    wofi_dir.mkdir(parents=True, exist_ok=True)
    (wofi_dir / "style.css").write_text(
        "window { background-color: rgba(8, 15, 29, 0.97); border: 2px solid #3bdde5; border-radius: 12px; }\n"
        "#input { background: #111d32; color: #edf7ff; border: 1px solid #3bdde5; border-radius: 8px; margin: 8px; padding: 8px; }\n"
        "#entry { color: #d7e7f4; padding: 6px; }\n"
        "#entry:selected { background: #2a2149; color: #ffffff; border-radius: 6px; }\n",
        encoding="utf-8",
    )

    quick_panel = root / "usr/local/bin/comet-quick-panel"
    quick_panel.parent.mkdir(parents=True, exist_ok=True)
    quick_panel.write_text(
        "#!/bin/sh\n"
        "runtime_dir=/run/user/0\n"
        "[ -n \"$XDG_RUNTIME_DIR\" ] && runtime_dir=\"$XDG_RUNTIME_DIR\"\n"
        "if [ -S \"$runtime_dir/wayland-0\" ] && command -v wofi >/dev/null 2>&1; then\n"
        "  WAYLAND_DISPLAY=\"$WAYLAND_DISPLAY\"\n"
        "[ -n \"$WAYLAND_DISPLAY\" ] || WAYLAND_DISPLAY=wayland-0\n"
        "  export WAYLAND_DISPLAY\n"
        "  choice=$(printf 'Open application menu\\nReturn to Comet Desk\\n' | wofi --style /root/.config/wofi/style.css --dmenu --prompt 'COMET // QUICK PANEL') || exit 0\n"
        "  case \"$choice\" in\n"
        "    'Open application menu') wofi --style /root/.config/wofi/style.css --show drun ;;\n"
        "    'Return to Comet Desk') : > \"$runtime_dir/comet-return.request\" ;;\n"
        "  esac\n"
        "else\n"
        "  choice=$(printf 'Open application menu\\nReturn to Comet Desk\\n' | dmenu -i -p 'COMET // QUICK PANEL' -nb '#080f1d' -nf '#d7e7f4' -sb '#2a2149' -sf '#3bdde5' -fn 'DejaVu Sans:size=12') || exit 0\n"
        "  case \"$choice\" in\n"
        "    'Open application menu') dmenu_run ;;\n"
        "    'Return to Comet Desk') : > \"$runtime_dir/comet-return.request\" ;;\n"
        "  esac\n"
        "fi\n",
        encoding="utf-8",
    )
    quick_panel.chmod(0o755)

    xbindkeys = root / "root/.xbindkeysrc"
    xbindkeys.write_text(
        '"comet-quick-panel"\n'
        '    m\n',
        encoding="utf-8",
    )

    x11_script = root / "usr/local/bin/comet-session-x11"
    x11_script.parent.mkdir(parents=True, exist_ok=True)
    x11_script.write_text(
        "#!/bin/sh\n"
        "xbindkeys -f /root/.xbindkeysrc >/tmp/comet-xbindkeys.log 2>&1 &\n"
        "qjoypad --notray Default >/dev/null 2>&1 &\n"
        "case " + chr(34) + "$" + "{COMET_DESKTOP_PROFILE:-icewm}" + chr(34) + " in\n"
        "  xfce) exec startxfce4 ;;\n"
        "  lxde) exec startlxde ;;\n"
        "  lxqt) exec startlxqt ;;\n"
        "  icewm) exec icewm-session ;;\n"
        "  fluxbox) exec startfluxbox ;;\n"
        "  openbox) exec openbox-session ;;\n"
        '  *) echo "Unknown X11 desktop profile" >&2; exit 64 ;;\n'
        "esac\n", encoding="utf-8")
    x11_script.chmod(0o755)

    qjoypad = root / "root/.qjoypad3"
    qjoypad.mkdir(parents=True, exist_ok=True)
    (qjoypad / "Default.lyt").write_text(
        "# QJoyPad 4.3 Layout File\n"
        "# Comet Desk controller profile for RG35XX H\n"
        "Joystick 1 {\n"
        "\tAxis 1: gradient, maxSpeed 3, mouse+h\n"
        "\tAxis 2: gradient, maxSpeed 3, mouse+v\n"
        "\tAxis 3: gradient, +key 114, -key 113\n"
        "\tAxis 4: gradient, +key 117, -key 112\n"
        "\tAxis 5: +key 114, -key 113\n"
        "\tAxis 6: +key 116, -key 111\n"
        "\tButton 4: mouse 1\n\tButton 5: key 166\n"
        "\tButton 6: mouse 2\n\tButton 7: mouse 3\n"
        "\tButton 8: mouse 4\n\tButton 9: mouse 5\n"
        "\tButton 10: key 9\n\tButton 11: key 36\n"
        "\tButton 13: mouse 1\n\tButton 16: mouse 3\n"
        "}\n", encoding="utf-8")
    (qjoypad / "layout").write_text("Default\n", encoding="utf-8")

    settings = root / "root/.config/xfce4/xfconf/xfce-perchannel-xml"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "xfwm4.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<channel name="xfwm4" version="1.0"><property name="general" type="empty">'
        '<property name="use_compositing" type="bool" value="false"/>'
        '<property name="title_font" type="string" value="Sans Bold 10"/>'
        '</property></channel>\n', encoding="utf-8")
    gtk = root / "root/.config/gtk-3.0"
    gtk.mkdir(parents=True, exist_ok=True)
    (gtk / "settings.ini").write_text(
        "[Settings]\ngtk-font-name=Sans 10\ngtk-dialogs-use-header=false\n",
        encoding="utf-8")
    (root / ".comet-debian-rootfs").write_text(
        "Debian GNU/Linux 13 (trixie) arm64\n", encoding="utf-8")

def _bind_build_environment(manager: ImageMount) -> None:
    manager.bind_host_tree(share_storage=False)


def _read_manifest(marker: Path) -> dict:
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_manifest(marker: Path, *, image: Path, installed_profiles: set[str],
                    selected_profile: str) -> None:
    payload = {
        "distribution": "debian",
        "release": "13",
        "codename": "trixie",
        "architecture": "arm64",
        "default_profile": DEFAULT_PROFILE,
        "selected_profile": selected_profile,
        "installed_profiles": sorted(installed_profiles),
        "image": str(image),
        "rootfs_sha256": DEBIAN_ROOTFS_SHA256,
        "seed_git_blob_sha1": IMAGE_SEED_GIT_BLOB_SHA1,
        "desktop_config_revision": DESKTOP_CONFIG_REVISION,
        "updated_at": int(time.time()),
    }
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temporary, marker)


def write_app_config_revision(app_dir: Path) -> None:
    path = app_dir / "data" / "desktop-config-revision"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="ascii") as stream:
        stream.write(str(DESKTOP_CONFIG_REVISION) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def setup(slot: str, app_dir: Path, profile: str = DEFAULT_PROFILE) -> Path:
    if os.geteuid() != 0:
        raise SetupError("Comet Desk needs muOS app-runner root privileges for loop mounts and chroot")
    if os.uname().machine not in ("aarch64", "arm64"):
        raise SetupError("Debian desktop profile requires an ARM64 H700 host")
    if slot not in SLOTS:
        raise SetupError("unknown storage slot")
    if profile not in PROFILE_PACKAGES:
        raise SetupError("unknown desktop profile: " + profile)

    mounted, writable = mounted_slot(slot)
    if not mounted:
        raise SetupError(slot.upper() + " is not mounted")
    if not writable:
        raise SetupError(slot.upper() + " is mounted read-only")
    root = SLOTS[slot].resolve(strict=True)
    if root != SLOTS[slot] or not root.is_dir():
        raise SetupError("selected storage root is not a trusted mount")

    stage = safe_staging_directory(root)
    free = os.statvfs(str(stage)).f_bavail * os.statvfs(str(stage)).f_frsize
    if free < MIN_FREE_BYTES:
        raise SetupError("Debian environment setup requires at least 9 GiB free")

    image = stage / "debian.img"
    seed = stage / "h700-ext4-seed.img.gz"
    rootfs = stage / "debian-trixie-arm64-rootfs.tar.gz"
    marker = stage / ".comet-debian-ready"
    mountpoint = app_dir / "data" / "desktop-mnt"
    log_path = app_dir / "data" / "desktop-environment.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for protected in (image, seed, rootfs, marker, mountpoint):
        if protected.is_symlink():
            raise SetupError("refusing symbolic-link desktop path: " + str(protected))

    manifest = _read_manifest(marker)
    if image.is_file() and manifest.get("distribution") == "debian":
        installed = set(manifest.get("installed_profiles", []))
        if (profile in installed
                and int(manifest.get("desktop_config_revision", 0)) >= DESKTOP_CONFIG_REVISION):
            write_app_config_revision(app_dir)
            write_status(app_dir, "READY", 100,
                         "Debian Trixie ready // " + profile.upper(),
                         str(image), profile)
            return image
    else:
        installed = set()

    if not image.exists():
        write_status(app_dir, "DOWNLOADING_TEMPLATE", 2,
                     "Downloading the pinned H700 ext4 filesystem seed",
                     str(image), profile)
        if not seed.exists() or seed.stat().st_size != IMAGE_SEED_SIZE:
            download_verified(
                IMAGE_SEED_URL, seed, expected_size=IMAGE_SEED_SIZE,
                expected_git_blob_sha1=IMAGE_SEED_GIT_BLOB_SHA1,
                status=(app_dir, "DOWNLOADING_TEMPLATE", 3, 12, "Downloading ext4 seed"),
            )
        elif git_blob_sha1(seed.read_bytes()) != IMAGE_SEED_GIT_BLOB_SHA1:
            seed.unlink()
            download_verified(
                IMAGE_SEED_URL, seed, expected_size=IMAGE_SEED_SIZE,
                expected_git_blob_sha1=IMAGE_SEED_GIT_BLOB_SHA1,
                status=(app_dir, "DOWNLOADING_TEMPLATE", 3, 12, "Downloading ext4 seed"),
            )
        _extract_gzip_image(seed, image, app_dir)
        # Keep the container large enough for Debian, APT caches and several
        # optional environments. The filesystem itself is grown after e2fsprogs
        # has been installed in the guest.
        os.truncate(image, DESKTOP_IMAGE_BYTES)
    else:
        with image.open("rb") as stream:
            stream.seek(1080)
            if stream.read(2) != b"\x53\xef":
                raise SetupError("existing Debian image is not an ext4 filesystem")

    log_stream = log_path.open("ab")
    manager = ImageMount(image, mountpoint, log_stream)
    try:
        write_status(app_dir, "PREPARING_ROOTFS", 18,
                     "Mounting the Debian filesystem container",
                     str(image), profile)
        manager.mount_image()

        rootfs_marker = mountpoint / ".comet-debian-rootfs-ready"
        if not rootfs_marker.is_file():
            existing_release = mountpoint / "etc/os-release"
            if existing_release.is_file():
                current_release = existing_release.read_text(errors="replace")
                if ("ID=debian" not in current_release
                        or 'VERSION_ID="13"' not in current_release
                        or "VERSION_CODENAME=trixie" not in current_release):
                    raise SetupError(
                        "existing image contains a non-Debian root filesystem; "
                        "refusing to overlay Debian on an unknown operating system"
                    )
            write_status(app_dir, "DOWNLOADING_ROOTFS", 23,
                         "Downloading verified Debian Trixie ARM64 rootfs",
                         str(image), profile)
            if (not rootfs.is_file()
                    or rootfs.stat().st_size != DEBIAN_ROOTFS_SIZE
                    or file_sha256(rootfs) != DEBIAN_ROOTFS_SHA256):
                download_verified(
                    DEBIAN_ROOTFS_URL, rootfs,
                    expected_size=DEBIAN_ROOTFS_SIZE,
                    expected_sha256=DEBIAN_ROOTFS_SHA256,
                    status=(app_dir, "DOWNLOADING_ROOTFS", 23, 34,
                            "Downloading Debian Trixie ARM64"),
                    max_bytes=64 * 1024 * 1024,
                )
            write_status(app_dir, "EXTRACTING_ROOTFS", 36,
                         "Extracting the Debian ARM64 root filesystem",
                         str(image), profile)
            _run(["tar", "-xzpf", str(rootfs), "-C", str(mountpoint)],
                 log=manager.log, timeout=900)
            os_release = (mountpoint / "etc/os-release").read_text(errors="replace")
            if ("ID=debian" not in os_release
                    or 'VERSION_ID="13"' not in os_release
                    or "VERSION_CODENAME=trixie" not in os_release):
                raise SetupError("downloaded rootfs is not Debian 13 Trixie")
            _write_guest_configuration(mountpoint)
            (mountpoint / "etc/fstab").write_text("", encoding="ascii")
            temporary_marker = rootfs_marker.with_suffix(".tmp")
            temporary_marker.write_text(
                "Debian GNU/Linux 13 (Trixie) ARM64 rootfs verified\\n",
                encoding="ascii",
            )
            os.replace(temporary_marker, rootfs_marker)
        else:
            os_release = (mountpoint / "etc/os-release").read_text(errors="replace")
            if ("ID=debian" not in os_release
                    or 'VERSION_ID="13"' not in os_release
                    or "VERSION_CODENAME=trixie" not in os_release):
                raise SetupError("rootfs readiness marker does not match Debian Trixie")

        _write_guest_configuration(mountpoint)
        # Disable service autostart while apt unpacks: the guest shares muOS's
        # running kernel and must not start independent host-level daemons.
        _bind_build_environment(manager)
        policy = mountpoint / "usr/sbin/policy-rc.d"
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text("#!/bin/sh\nexit 101\n", encoding="ascii")
        policy.chmod(0o755)

        env = dict(os.environ)
        env.update(APP_ENV)
        env["DEBIAN_FRONTEND"] = "noninteractive"

        write_status(app_dir, "APT_UPDATE", 42,
                     "Refreshing Debian Trixie package indexes",
                     str(image), profile)
        run_apt_with_progress(
            ["chroot", str(mountpoint), "/usr/bin/env",
             "DEBIAN_FRONTEND=noninteractive",
             "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
             "apt-get", "-o", "Acquire::Retries=2", "update"],
            log=manager.log, timeout=1200, env=env,
            on_progress=lambda percent, message: write_status(
                app_dir, "APT_UPDATE", 42 + int(percent * 0.14),
                message or "Refreshing Debian Trixie package indexes",
                str(image), profile,
            ),
        )

        packages = BASE_PACKAGES.split() + PROFILE_PACKAGES[DEFAULT_PROFILE].split()
        if profile != DEFAULT_PROFILE:
            packages += PROFILE_PACKAGES[profile].split()
        packages = list(dict.fromkeys(packages))
        write_status(app_dir, "INSTALLING_PROFILE", 58,
                     "Installing APT profile // " + profile.upper(),
                     str(image), profile)
        run_apt_with_progress(
            ["chroot", str(mountpoint), "/usr/bin/env",
             "DEBIAN_FRONTEND=noninteractive",
             "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
             "apt-get", "-o", "Acquire::Retries=2",
             "install", "-y", "--no-install-recommends"] + packages,
            log=manager.log, timeout=3600, env=env,
            on_progress=lambda percent, message: write_status(
                app_dir, "INSTALLING_PROFILE", 58 + int(percent * 0.37),
                message or ("Installing APT profile // " + profile.upper()),
                str(image), profile,
            ),
        )
        _run(["chroot", str(mountpoint), "/usr/bin/env",
              "PATH=/usr/sbin:/usr/bin:/sbin:/bin", "apt-get", "clean"],
             log=manager.log, timeout=180, env=env)

        # Resize the mounted ext4 guest to the full sparse container size.
        loop = manager.loop
        if not loop:
            raise SetupError("desktop loop device was lost before filesystem expansion")
        _run(["chroot", str(mountpoint), "/usr/sbin/resize2fs", loop],
             log=manager.log, timeout=900, env=env)

        policy.unlink(missing_ok=True)
        required = {
            "labwc": ("/usr/bin/labwc",),
            "xfce": ("/usr/bin/startxfce4",),
            "lxde": ("/usr/bin/startlxde",),
            "lxqt": ("/usr/bin/startlxqt",),
            "icewm": ("/usr/bin/icewm-session",),
            "fluxbox": ("/usr/bin/startfluxbox",),
            "openbox": ("/usr/bin/openbox-session",),
        }
        missing = [path for path in required[profile]
                   if not (mountpoint / path.lstrip("/")).exists()]
        if missing:
            raise SetupError("profile installation incomplete: " + ", ".join(missing))

        installed.add(DEFAULT_PROFILE)
        installed.add(profile)
        _write_manifest(marker, image=image,
                        installed_profiles=installed,
                        selected_profile=profile)
        write_app_config_revision(app_dir)
        write_status(app_dir, "READY", 100,
                     "Debian Trixie ready // " + profile.upper(),
                     str(image), profile)
        return image
    except Exception as exc:
        write_status(app_dir, "FAILED", 0, str(exc), str(image), profile)
        raise
    finally:
        if not manager.cleanup():
            write_status(app_dir, "CLEANUP_REQUIRED", 0,
                         "Debian image mount cleanup could not be verified; check the log",
                         str(image), profile)
        log_stream.close()


def _x11_profile_command(profile: str) -> str:
    commands = {
        "xfce": "/usr/bin/startxfce4",
        "lxde": "/usr/bin/startlxde",
        "lxqt": "/usr/bin/startlxqt",
        "icewm": "/usr/bin/icewm-session",
        "fluxbox": "/usr/bin/startfluxbox",
        "openbox": "/usr/bin/openbox-session",
    }
    if profile not in commands:
        raise SetupError("profile does not use the X11 backend: " + profile)
    return commands[profile]


def stop_process_group(process: subprocess.Popen, grace_seconds: float = 6.0) -> None:
    """Stop the whole session/app process group, including reparented helpers."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, OSError):
            break
        time.sleep(0.1)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    try:
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass


def launch(slot: str, app_dir: Path, profile: str = DEFAULT_PROFILE,
           app_id: str | None = None) -> int:
    if os.geteuid() != 0:
        raise SetupError("Comet Desk needs muOS app-runner root privileges to launch a desktop")
    if slot not in SLOTS:
        raise SetupError("unknown storage slot")
    if profile not in PROFILE_PACKAGES:
        raise SetupError("unknown desktop profile: " + profile)
    mounted, _writable = mounted_slot(slot)
    if not mounted:
        raise SetupError(slot.upper() + " is not mounted")

    root = SLOTS[slot].resolve(strict=True)
    stage = safe_staging_directory(root)
    image = stage / "debian.img"
    marker = stage / ".comet-debian-ready"
    if image.is_symlink() or marker.is_symlink():
        raise SetupError("refusing symbolic-link Debian image or manifest")
    manifest = _read_manifest(marker)
    if (manifest.get("distribution") != "debian"
            or manifest.get("codename") != "trixie"
            or int(manifest.get("desktop_config_revision", 0)) < DESKTOP_CONFIG_REVISION
            or profile not in set(manifest.get("installed_profiles", []))):
        raise SetupError("Debian profile is not installed; run Desktop Setup first")

    mountpoint = app_dir / "data" / "desktop-mnt"
    log_path = app_dir / "data" / "desktop-environment.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_dir = app_dir / "data" / "desktop-runtime"
    if runtime_dir.is_symlink():
        raise SetupError("desktop runtime directory is a symbolic link")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.chmod(0o700)

    log_stream = log_path.open("ab")
    manager = ImageMount(image, mountpoint, log_stream)
    try:
        manager.mount_image()
        manager.bind_host_tree(share_storage=True)
        manager.bind(runtime_dir, mountpoint / "run/user/0")

        env = dict(os.environ)
        env.update(APP_ENV)
        env["HOME"] = "/root"
        env["XDG_RUNTIME_DIR"] = "/run/user/0"
        env["COMET_DESKTOP_PROFILE"] = profile
        write_status(app_dir, "RUNNING", 100,
                     "Debian desktop running // " + profile.upper(),
                     str(image), profile)

        if profile == "labwc":
            drm = Path("/dev/dri")
            drm_devices = list(drm.glob("card*")) if drm.is_dir() else []
            if not drm_devices:
                raise SetupError(
                    "labwc requires a DRM/KMS device at /dev/dri/card*. "
                    "Choose an X11 profile (IceWM, Fluxbox, Openbox, LXDE, LXQt or XFCE) "
                    "until the muOS H700 DRM path is available."
                )
            command = [
                "chroot", str(mountpoint), "/usr/bin/env",
                "HOME=/root", "USER=root", "LOGNAME=root",
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "XDG_RUNTIME_DIR=/run/user/0", "WLR_BACKENDS=drm",
                "LIBSEAT_BACKEND=builtin", "/usr/bin/labwc",
            ]
        else:
            command = [
                "chroot", str(mountpoint), "/usr/bin/env",
                "HOME=/root", "USER=root", "LOGNAME=root", "SHELL=/bin/bash",
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "XDG_RUNTIME_DIR=/run/user/0",
                "COMET_DESKTOP_PROFILE=" + profile,
                "/usr/bin/startx", "/usr/local/bin/comet-session-x11", "--",
                ":0", "vt1", "-novtswitch", "-keeptty",
            ]
        application = None
        if app_id:
            import app_registry
            application = app_registry.find_application(mountpoint, app_id)
            if application is None:
                raise SetupError("application is no longer installed; refresh APP DECK")

        return_request = runtime_dir / "comet-return.request"
        return_request.unlink(missing_ok=True)
        session = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=log_stream,
            stderr=subprocess.STDOUT, env=env, start_new_session=True,
        )
        app_process = None
        try:
            if application is None:
                write_status(app_dir, "RUNNING", 100,
                             "Debian desktop running // press M for Comet Quick Panel",
                             str(image), profile)
                while session.poll() is None and not return_request.exists():
                    time.sleep(0.2)
                return_code = session.poll()
                write_status(app_dir, "READY", 100,
                             "Returned to Comet Desk from desktop Quick Panel"
                             if return_request.exists()
                             else "Desktop session ended; returned to Comet Desk",
                             str(image), profile)
                return return_code or 0

            deadline = time.monotonic() + 45
            ready = False
            while time.monotonic() < deadline:
                if session.poll() is not None:
                    raise SetupError(
                        "desktop session exited before the application became available; "
                        "inspect desktop-environment.log"
                    )
                if profile == "labwc":
                    ready = (runtime_dir / "wayland-0").exists()
                else:
                    probe_display = subprocess.run(
                        ["chroot", str(mountpoint), "/usr/bin/env",
                         "DISPLAY=:0", "HOME=/root", "XAUTHORITY=/root/.Xauthority",
                         "PATH=/usr/bin:/bin", "/usr/bin/xdpyinfo", "-display", ":0"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, check=False, timeout=3,
                    )
                    ready = probe_display.returncode == 0
                if ready:
                    break
                time.sleep(0.25)
            if not ready:
                raise SetupError("desktop display did not become ready within 45 seconds")

            app_variables = [
                "HOME=/root", "USER=root", "LOGNAME=root",
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "XDG_RUNTIME_DIR=/run/user/0",
            ]
            if profile == "labwc":
                app_variables += [
                    "XDG_SESSION_TYPE=wayland", "WAYLAND_DISPLAY=wayland-0",
                    "LIBSEAT_BACKEND=builtin",
                ]
            else:
                app_variables += [
                    "XDG_SESSION_TYPE=x11", "DISPLAY=:0",
                    "XAUTHORITY=/root/.Xauthority",
                ]
            app_command = [
                "chroot", str(mountpoint), "/usr/bin/env",
                *app_variables, *application["exec"],
            ]
            write_status(app_dir, "APP_RUNNING", 100,
                         "Comet application // " + application["name"],
                         str(image), profile)
            app_process = subprocess.Popen(
                app_command, stdin=subprocess.DEVNULL, stdout=log_stream,
                stderr=subprocess.STDOUT, env=env, start_new_session=True,
            )
            while app_process.poll() is None and not return_request.exists():
                if session.poll() is not None:
                    raise SetupError("desktop session exited while the application was running")
                time.sleep(0.2)
            return_code = app_process.poll()
            write_status(app_dir, "READY", 100,
                         "Returned to Comet Desk from desktop Quick Panel"
                         if return_request.exists()
                         else "Application closed; returned to Comet Desk",
                         str(image), profile)
            return return_code or 0
        finally:
            if app_process is not None:
                stop_process_group(app_process)
            stop_process_group(session)
            return_request.unlink(missing_ok=True)
    finally:
        clean = manager.cleanup()
        log_stream.close()
        if not clean:
            write_status(app_dir, "CLEANUP_REQUIRED", 0,
                         "Desktop returned but one or more mounts remain; inspect the log",
                         str(image), profile)



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "session"))
    parser.add_argument("--slot", required=True, choices=sorted(SLOTS))
    parser.add_argument("--profile", choices=sorted(PROFILE_PACKAGES), default=DEFAULT_PROFILE)
    parser.add_argument("--app-dir", default=os.environ.get("COMET_DESK_APP_DIR", ""))
    parser.add_argument("--app-id", default="")
    args = parser.parse_args()
    if not args.app_dir:
        print("COMET_DESK_APP_DIR is required", file=sys.stderr)
        return 2
    app_dir = Path(args.app_dir).resolve()
    lock_path = app_dir / "data" / "debian-system.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            write_status(app_dir, "BUSY", 0,
                         "Another Debian/ APT operation is already running",
                         profile=args.profile)
            return 1
        try:
            if args.action == "setup":
                image = setup(args.slot, app_dir, args.profile)
                print("[comet-desktop] Debian Trixie prepared: {} ({})".format(
                    image, args.profile
                ))
                return 0
            result = launch(args.slot, app_dir, args.profile, args.app_id or None)
            print("[comet-desktop] {} session returned ({})".format(
                args.profile, result
            ))
            return 0
        except (SetupError, OSError, ValueError, urllib.error.URLError,
                subprocess.SubprocessError, json.JSONDecodeError) as exc:
            write_status(app_dir, "FAILED", 0, str(exc), profile=args.profile)
            print("[comet-desktop] ERROR: {}".format(exc), file=sys.stderr)
            return 1
        finally:
            try:
                fcntl.flock(lock, fcntl.LOCK_UN)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
