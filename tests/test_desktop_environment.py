from __future__ import annotations

import gzip
import hashlib
import io
import json

import pytest

import service.desktop_environment as desktop


def test_pinned_image_seed_uses_the_void_desk_git_blob():
    assert desktop.IMAGE_SEED_GIT_BLOB_SHA1 == "9a9571d17f94dc9c8993782a4df4126833e47e8b"
    assert desktop.git_blob_sha1(b"test") == "30d74d258442c7c65512eafab474568dd706c430"


def test_verified_download_rejects_wrong_size_and_checksum(tmp_path):
    class FakeResponse(io.BytesIO):
        status = 200
        headers = {"Content-Length": "8"}
        def __enter__(self): return self
        def __exit__(self, *args): self.close()

    payload = b"payload!"
    target = tmp_path / "asset.bin"
    with pytest.raises(desktop.SetupError, match="SHA-256"):
        desktop.download_verified(
            "https://example.invalid/asset.bin", target,
            expected_size=len(payload), expected_sha256="0" * 64,
            opener=lambda *_args, **_kwargs: FakeResponse(payload),
        )
    assert not target.exists()
    assert not (tmp_path / "asset.bin.part").exists()


def test_rootfs_extraction_streams_plain_tar_to_busybox_compatible_command(tmp_path):
    captured = tmp_path / "captured.tar"
    args_file = tmp_path / "tar.args"
    fake_tar = tmp_path / "tar"
    fake_tar.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "pathlib.Path(" + repr(str(captured)) + ").write_bytes(sys.stdin.buffer.read())\n"
        "pathlib.Path(" + repr(str(args_file)) + ").write_text('\\n'.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    fake_tar.chmod(0o755)

    raw_tar = b"plain tar stream from verified Debian gzip"
    archive = tmp_path / "rootfs.tar.gz"
    archive.write_bytes(gzip.compress(raw_tar))
    destination = tmp_path / "guest"
    destination.mkdir()
    log_path = tmp_path / "extract.log"

    with log_path.open("wb") as log:
        desktop.extract_gzip_tar(
            archive, destination, log=log, timeout=10, tar_command=str(fake_tar)
        )

    assert captured.read_bytes() == raw_tar
    args = args_file.read_text(encoding="utf-8").splitlines()
    assert args == ["-x", "-f", "-", "-C", str(destination)]
    assert "z" not in "".join(args)
    assert "p" not in "".join(args)


def test_rootfs_extraction_reports_tar_failure(tmp_path):
    fake_tar = tmp_path / "tar-fails"
    fake_tar.write_text(
        "#!/bin/sh\ncat >/dev/null\nexit 23\n",
        encoding="utf-8",
    )
    fake_tar.chmod(0o755)
    archive = tmp_path / "rootfs.tar.gz"
    archive.write_bytes(gzip.compress(b"plain tar stream"))
    with (tmp_path / "extract.log").open("wb") as log:
        with pytest.raises(desktop.SetupError, match="status 23"):
            desktop.extract_gzip_tar(
                archive, tmp_path, log=log, timeout=10, tar_command=str(fake_tar)
            )


def test_rootfs_extraction_with_system_tar_restores_files_and_symlinks(tmp_path):
    import shutil
    import tarfile

    tar_executable = shutil.which("tar")
    if not tar_executable:
        pytest.skip("tar is unavailable")

    source = tmp_path / "source"
    (source / "usr/bin").mkdir(parents=True)
    executable = source / "usr/bin/comet-test"
    executable.write_text("#!/bin/sh\\necho Comet\\n", encoding="utf-8")
    executable.chmod(0o755)
    (source / "bin").symlink_to("usr/bin", target_is_directory=True)

    raw_tar = tmp_path / "rootfs.tar"
    with tarfile.open(raw_tar, "w") as archive:
        archive.add(source / "usr", arcname="usr")
        archive.add(source / "bin", arcname="bin", recursive=False)
    archive = tmp_path / "rootfs.tar.gz"
    archive.write_bytes(gzip.compress(raw_tar.read_bytes()))

    destination = tmp_path / "guest"
    destination.mkdir()
    with (tmp_path / "extract.log").open("wb") as log:
        desktop.extract_gzip_tar(
            archive, destination, log=log, timeout=10, tar_command=tar_executable
        )

    assert (destination / "usr/bin/comet-test").read_text(encoding="utf-8").endswith("echo Comet\\n")
    assert (destination / "usr/bin/comet-test").stat().st_mode & 0o111
    assert (destination / "bin").is_symlink()
    assert (destination / "bin").readlink().as_posix() == "usr/bin"


def test_mount_parser_decodes_escaped_mount_path(tmp_path):
    target = tmp_path / "Comet Desk"
    rows = desktop.mount_table_from_text(
        "/dev/loop0 {} ext4 rw,relatime 0 0\n".format(str(target).replace(" ", "\\040"))
    )
    assert rows == [("/dev/loop0", str(target), "rw,relatime")]


def test_staging_path_is_confined_to_selected_root(tmp_path):
    root = tmp_path / "sd"
    root.mkdir()
    stage = desktop.safe_staging_directory(root)
    assert stage.is_relative_to(root)
    assert stage.parts[-3:] == ("MUOS", "CometDesk", "Desktop")


def test_staging_path_rejects_symlink_escape(tmp_path):
    root = tmp_path / "sd"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "MUOS").symlink_to(outside, target_is_directory=True)
    with pytest.raises(desktop.SetupError, match="symbolic-link"):
        desktop.safe_staging_directory(root)


def test_mount_parser_uses_exact_mountpoint_and_read_only_state():
    rows = desktop.mount_table_from_text(
        "/dev/mmcblk0p1 /mnt/mmc exfat rw,nosuid,nodev 0 0" + chr(10)
        + "/dev/mmcblk1p1 /mnt/sdcard exfat ro,nosuid,nodev 0 0"
    )
    assert rows == [
        ("/dev/mmcblk0p1", "/mnt/mmc", "rw,nosuid,nodev"),
        ("/dev/mmcblk1p1", "/mnt/sdcard", "ro,nosuid,nodev"),
    ]

def test_guest_profile_constants_match_debian_trixie_contract():
    assert desktop.DEBIAN_ROOTFS_URL.endswith("/trixie/oci/blobs/rootfs.tar.gz")
    assert desktop.DEBIAN_ROOTFS_SIZE == 49_778_604
    assert desktop.DEBIAN_ROOTFS_SHA256 == "23b69c48ce5c2a6fb0681d959fa700427ad2a7cf7e6be5d25249170a1853d7ad"
    assert desktop.DEFAULT_PROFILE == "labwc"
    assert desktop.PROFILE_PACKAGES["labwc"].startswith("labwc")
    assert "xfce4" in desktop.PROFILE_PACKAGES["xfce"]
    assert "lxde-core" in desktop.PROFILE_PACKAGES["lxde"]
    assert "lxqt-core" in desktop.PROFILE_PACKAGES["lxqt"]
    assert "icewm" in desktop.PROFILE_PACKAGES["icewm"]
    assert "fluxbox" in desktop.PROFILE_PACKAGES["fluxbox"]
    assert "openbox" in desktop.PROFILE_PACKAGES["openbox"]
    assert desktop.MIN_FREE_BYTES > desktop.DESKTOP_IMAGE_BYTES


def test_desktop_config_includes_global_m_quick_panel_for_both_backends(tmp_path):
    import subprocess
    import xml.etree.ElementTree as ET

    desktop._write_guest_configuration(tmp_path)
    quick_panel = tmp_path / "usr/local/bin/comet-quick-panel"
    x11_session = tmp_path / "usr/local/bin/comet-session-x11"
    rc_xml = tmp_path / "root/.config/labwc/rc.xml"
    xbindkeys = tmp_path / "root/.xbindkeysrc"

    assert quick_panel.is_file()
    assert quick_panel.stat().st_mode & 0o111
    assert "wofi --style /root/.config/wofi/style.css --dmenu" in quick_panel.read_text()
    assert "dmenu -i" in quick_panel.read_text()
    assert "comet-return.request" in quick_panel.read_text()
    wofi_style = tmp_path / "root/.config/wofi/style.css"
    assert wofi_style.is_file()
    assert "#3bdde5" in wofi_style.read_text()
    assert 'key="m"' in rc_xml.read_text()
    assert "comet-quick-panel" in xbindkeys.read_text()
    assert "xbindkeys" in x11_session.read_text()
    ET.parse(rc_xml)

    subprocess.run(["sh", "-n", str(quick_panel)], check=True)
    subprocess.run(["sh", "-n", str(x11_session)], check=True)


def test_x11_profiles_install_the_global_quick_panel_hotkey_tools():
    for profile in ("xfce", "lxde", "lxqt", "icewm", "fluxbox", "openbox"):
        packages = desktop.PROFILE_PACKAGES[profile].split()
        assert "xbindkeys" in packages
        assert "dmenu" in packages


def test_desktop_config_revision_is_explicit_for_safe_in_place_migration():
    assert desktop.DESKTOP_CONFIG_REVISION == 2


def test_stop_process_group_terminates_the_owned_session_process():
    import subprocess

    process = subprocess.Popen(["sleep", "30"], start_new_session=True)
    desktop.stop_process_group(process, grace_seconds=0.2)
    assert process.poll() is not None


def test_config_revision_marker_is_atomic_and_matches_guest_manifest_revision(tmp_path):
    desktop.write_app_config_revision(tmp_path)
    marker = tmp_path / "data" / "desktop-config-revision"
    assert marker.read_text(encoding="ascii") == "2\n"
    assert not marker.with_suffix(".tmp").exists()


def _mock_menu_binary(directory, name):
    import os

    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / name
    binary.write_text("#!/bin/sh\nprintf '%s\\n' 'Return to Comet Desk'\n", encoding="utf-8")
    binary.chmod(binary.stat().st_mode | 0o111)
    return binary


def test_x11_quick_panel_writes_clean_return_request(tmp_path):
    import os
    import subprocess

    desktop._write_guest_configuration(tmp_path / "guest")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    bin_dir = tmp_path / "bin"
    _mock_menu_binary(bin_dir, "dmenu")
    _mock_menu_binary(bin_dir, "dmenu_run")
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env.pop("WAYLAND_DISPLAY", None)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    quick_panel = tmp_path / "guest/usr/local/bin/comet-quick-panel"
    subprocess.run([str(quick_panel)], env=env, check=True)
    assert (runtime / "comet-return.request").is_file()


def test_wayland_quick_panel_uses_wofi_and_writes_return_request(tmp_path):
    import os
    import socket
    import subprocess

    guest = tmp_path / "guest"
    desktop._write_guest_configuration(guest)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    socket_path = runtime / "wayland-0"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.close()

    bin_dir = tmp_path / "bin"
    _mock_menu_binary(bin_dir, "wofi")
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env.pop("WAYLAND_DISPLAY", None)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    quick_panel = guest / "usr/local/bin/comet-quick-panel"
    subprocess.run([str(quick_panel)], env=env, check=True)
    assert (runtime / "comet-return.request").is_file()



def test_apt_status_event_decodes_dpkg_and_download_progress():
    assert desktop.apt_status_event("pmstatus:base:42:Unpacking base") == (
        42.0, "Unpacking base"
    )
    event = desktop.apt_status_event("dlstatus:https://mirror/pkg.deb:25:100")
    assert event == (25.0, "Downloading Debian packages")
    assert desktop.apt_status_event("pmerror:base:10:failed") is None


def test_apt_progress_runner_reports_status_fd_events(tmp_path):
    import os

    fake_apt = tmp_path / "apt-get"
    fake_apt.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "fd = int(next(arg.split('=', 1)[1] for arg in sys.argv "
        "if arg.startswith('APT::Status-Fd=')))\n"
        "os.write(fd, b'pmstatus:base:42:Unpacking base\\n')\n"
        "os.write(fd, b'pmstatus:base:100:Installed base\\n')\n",
        encoding="utf-8",
    )
    fake_apt.chmod(0o755)
    events = []
    with (tmp_path / "apt.log").open("ab") as log:
        desktop.run_apt_with_progress(
            [str(fake_apt), "install", "base"], log=log, timeout=5,
            on_progress=lambda percent, message: events.append((percent, message)),
        )
    assert events == [(42, "Unpacking base"), (100, "Installed base")]




def test_first_boot_is_a_light_desktop_baseline_and_dev_tools_are_optional():
    from service.forge_apt import CATALOG

    base = set(desktop.BASE_PACKAGES.split())
    forge = {row[1] for row in CATALOG}
    assert {"apt", "dbus", "gvfs", "e2fsprogs", "seatd"} <= base
    optional = {
        "git", "curl", "wget", "python3-venv", "python3-pip",
        "build-essential", "cmake", "ninja-build", "pkg-config",
        "file", "unzip", "zip",
    }
    assert base.isdisjoint(optional)
    assert optional <= forge



def test_operation_lock_probe_distinguishes_stale_file_from_active_worker(tmp_path):
    import fcntl

    lock_path = tmp_path / "data" / "debian-system.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.touch()

    # A leftover lock file after a crash is harmless once flock ownership is gone.
    assert desktop.operation_lock_busy(tmp_path) is False
    assert lock_path.exists()

    with lock_path.open("a+") as active:
        fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert desktop.operation_lock_busy(tmp_path) is True

    # Exiting the worker releases the kernel lock without needing to delete the file.
    assert desktop.operation_lock_busy(tmp_path) is False



def test_desktop_environment_check_action_writes_machine_readable_lock_state(tmp_path):
    import fcntl
    import subprocess
    import sys

    script = desktop.__file__
    command = [
        sys.executable, script, "check", "--slot", "tf1",
        "--profile", "labwc", "--app-dir", str(tmp_path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "IDLE"
    assert (tmp_path / "data" / "debian-lock.status").read_text().splitlines() == ["IDLE"]

    lock_path = tmp_path / "data" / "debian-system.lock"
    with lock_path.open("a+") as active:
        fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
        busy = subprocess.run(command, check=True, capture_output=True, text=True)
        assert busy.stdout.strip() == "BUSY"
        assert (tmp_path / "data" / "debian-lock.status").read_text().splitlines() == ["BUSY"]
