from __future__ import annotations

import hashlib
import io

import pytest

from service.desktop_image_download import (
    IMAGE_NAME,
    OS_TAG_PREFIX,
    ImageReleaseUnavailable,
    mounted_slot,
    select_os_asset,
    stream_download,
)


def _release(name=IMAGE_NAME, tag="voiddesk-os-v0.1.0-alpha",
             digest="sha256:" + "a" * 64, size=1234):
    return {
        "draft": False,
        "tag_name": tag,
        "html_url": "https://github.com/SilverCrow2323/Void-Desk-Project/releases/tag/" + tag,
        "assets": [{
            "name": name,
            "size": size,
            "digest": digest,
            "browser_download_url": (
                "https://github.com/SilverCrow2323/Void-Desk-Project/releases/download/"
                + tag + "/" + name
            ),
        }],
    }


def test_asset_selector_accepts_only_exact_os_disk_image():
    asset = select_os_asset([_release()])
    assert asset["name"] == IMAGE_NAME
    assert asset["tag"].startswith(OS_TAG_PREFIX)
    assert asset["sha256"] == "a" * 64


def test_asset_selector_never_accepts_void_desk_muxapp():
    release = _release(name="VoidDesk_v10.2.0.muxapp")
    with pytest.raises(ImageReleaseUnavailable):
        select_os_asset([release])


def test_asset_selector_requires_os_release_tag_and_digest():
    with pytest.raises(ImageReleaseUnavailable):
        select_os_asset([_release(tag="v10.2.0")])
    with pytest.raises(ImageReleaseUnavailable):
        select_os_asset([_release(digest="")])
    with pytest.raises(ImageReleaseUnavailable):
        select_os_asset([_release(digest="sha256:bad")])


def test_mounted_slot_requires_exact_mount_and_writable_option(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("service.desktop_image_download", fromlist=["SLOTS"]).SLOTS,
                        "tf1", tmp_path / "tf1")
    monkeypatch.setitem(__import__("service.desktop_image_download", fromlist=["SLOTS"]).SLOTS,
                        "tf2", tmp_path / "tf2")
    mounts = tmp_path / "mounts"
    mounts.write_text(
        "{} /mnt/mmc exfat rw,nosuid,nodev 0 0\\n".format(tmp_path / "tf1")
        + "{} /mnt/sdcard exfat ro,nosuid,nodev 0 0\\n".format(tmp_path / "tf2"),
        encoding="utf-8",
    )
    # Mount-table parsing is exact; changing the configured root does not make
    # unrelated host paths eligible.
    assert mounted_slot("tf1", str(mounts)) == (False, True)
    assert mounted_slot("tf2", str(mounts)) == (False, True)


def test_stream_download_keeps_partial_until_verified(tmp_path):
    payload = b"Debian Trixie ARM64 labwc disk image"
    digest = hashlib.sha256(payload).hexdigest()
    target = tmp_path / IMAGE_NAME
    status = tmp_path / "status.txt"
    stream_download(io.BytesIO(payload), target, len(payload), digest, status)
    assert not target.exists()
    assert (tmp_path / (IMAGE_NAME + ".part")).read_bytes() == payload
    assert status.read_text().startswith("DOWNLOADING|100|")


def test_stream_download_rejects_bad_checksum_and_removes_partial(tmp_path):
    target = tmp_path / IMAGE_NAME
    with pytest.raises(ValueError, match="SHA-256"):
        stream_download(io.BytesIO(b"not the image"), target, 12, "0" * 64,
                        tmp_path / "status.txt")
    assert not (tmp_path / (IMAGE_NAME + ".part")).exists()


def test_stream_download_rejects_truncated_image(tmp_path):
    target = tmp_path / IMAGE_NAME
    with pytest.raises(ValueError, match="size mismatch"):
        stream_download(io.BytesIO(b"tiny"), target, 10, "0" * 64,
                        tmp_path / "status.txt")
    assert not (tmp_path / (IMAGE_NAME + ".part")).exists()
