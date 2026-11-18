from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from service.desktop_download import mounted_slot, stream_download


def test_mounted_slot_requires_exact_mount_and_writable_option(tmp_path):
    mounts = tmp_path / "mounts"
    mounts.write_text(
        "/dev/mmcblk0p1 /mnt/mmc exfat rw,nosuid,nodev 0 0\n"
        "/dev/mmcblk1p1 /mnt/sdcard exfat ro,nosuid,nodev 0 0\n",
        encoding="utf-8",
    )
    assert mounted_slot("tf1", str(mounts)) == (True, False)
    assert mounted_slot("tf2", str(mounts)) == (True, True)
    assert mounted_slot("unknown", str(mounts)) == (False, True)


def test_stream_download_keeps_verified_data_in_partial_until_activation(tmp_path):
    payload = b"Comet Desk verified installer payload"
    expected = hashlib.sha256(payload).hexdigest()
    target = tmp_path / "VoidDesk.muxapp"
    status = tmp_path / "status.txt"
    stream_download(io.BytesIO(payload), target, len(payload), expected, status)
    assert not target.exists()
    assert (tmp_path / "VoidDesk.muxapp.part").read_bytes() == payload
    assert status.read_text().startswith("DOWNLOADING|100|")


def test_stream_download_rejects_bad_checksum_and_removes_partial(tmp_path):
    payload = b"not the pinned installer"
    target = tmp_path / "VoidDesk.muxapp"
    status = tmp_path / "status.txt"
    with pytest.raises(ValueError, match="SHA-256"):
        stream_download(io.BytesIO(payload), target, len(payload), "0" * 64, status)
    assert not target.exists()
    assert not (tmp_path / "VoidDesk.muxapp.part").exists()


def test_stream_download_rejects_truncated_file(tmp_path):
    target = tmp_path / "VoidDesk.muxapp"
    status = tmp_path / "status.txt"
    with pytest.raises(ValueError, match="size mismatch"):
        stream_download(io.BytesIO(b"tiny"), target, 10, "0" * 64, status)
    assert not (tmp_path / "VoidDesk.muxapp.part").exists()
