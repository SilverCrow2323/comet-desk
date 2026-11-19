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
