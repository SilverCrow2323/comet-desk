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
