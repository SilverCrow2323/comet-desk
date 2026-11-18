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
        "/dev/mmcblk0p1 /mnt/mmc exfat rw,nosuid,nodev 0 0\\n"
        "/dev/mmcblk1p1 /mnt/sdcard exfat ro,nosuid,nodev 0 0\\n"
    )
    assert rows == [
        ("/dev/mmcblk0p1", "/mnt/mmc", "rw,nosuid,nodev"),
        ("/dev/mmcblk1p1", "/mnt/sdcard", "ro,nosuid,nodev"),
    ]


def test_guest_profile_constants_match_voiddesk_xfce_contract():
    assert "xfce4-session" in desktop.PACKAGES
    assert "xserver-xorg-video-fbdev" in desktop.PACKAGES
    assert desktop.IMAGE_SEED_URL.startswith("https://raw.githubusercontent.com/")
    assert desktop.UBUNTU_BASE_SHA256 == "7b2dced6dd56ad5e4a813fa25c8de307b655fdabc6ea9213175a92c48dabb048"
    assert desktop.UBUNTU_BASE_SIZE == 29_865_086
    assert desktop.UBUNTU_BASE_URL.endswith("ubuntu-base-24.04.3-base-arm64.tar.gz")
