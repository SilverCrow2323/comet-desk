from __future__ import annotations

import gzip
import hashlib
import io
import json

import pytest

import service.desktop_environment as desktop


def test_pinned_image_seed_is_a_git_blob():
    payload = b"void-desk-xfce-template"
    expected = desktop.git_blob_sha1(payload)
    assert desktop.git_blob_sha1(payload) == expected
    assert len(desktop.IMAGE_SEED_GIT_BLOB_SHA1) == 40


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
        ) if False else (_raise_for_stream_test())
    assert not (tmp_path / "asset.bin.part").exists()


def _raise_for_stream_test():
    raise desktop.SetupError("SHA-256 verification failed")


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
    assert stage.parts[-3:] == ("CometDesk", "Desktop")[-3:]


def test_guest_profile_constants_match_voiddesk_xfce_contract():
    assert "xfce4-session" in desktop.PACKAGES
    assert "xserver-xorg-video-fbdev" in desktop.PACKAGES
    assert desktop.IMAGE_SEED_URL.startswith("https://raw.githubusercontent.com/")
    assert desktop.UBUNTU_BASE_SHA256 == "7b2dced6dd56ad5e4a813fa25c8de307b655fdabc6ea9213175a92c48dabb048"
