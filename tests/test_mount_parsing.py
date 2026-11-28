import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "service" / "device_probe.py"
SPEC = importlib.util.spec_from_file_location("device_probe_mount_tests", MODULE)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_mount_fields_decode_linux_space_and_backslash_escapes():
    assert probe._unescape_mount_field(r"/mnt/My\040Card") == "/mnt/My Card"
    assert probe._unescape_mount_field(r"/dev/disk\134image") == "/dev/disk\\image"


def test_invalid_octal_escape_is_preserved_instead_of_becoming_invalid_unicode():
    assert probe._unescape_mount_field(r"/mnt/card\777") == r"/mnt/card\777"


def test_storage_inventory_reads_block_capacity_once_per_mount(monkeypatch):
    monkeypatch.setattr(
        probe,
        "_mounts",
        lambda: [{
            "source": "/dev/mmcblk0p1",
            "mount_point": "/mnt/mmc",
            "filesystem": "ext4",
            "options": "ro,relatime",
        }],
    )
    monkeypatch.setattr(
        probe,
        "_filesystem_stats",
        lambda _path: {
            "total_bytes": 60,
            "used_bytes": 10,
            "available_bytes": 45,
        },
    )
    calls = []
    monkeypatch.setattr(
        probe,
        "_block_size_bytes",
        lambda source: calls.append(source) or 64,
    )

    result = probe.storage_inventory()

    assert calls == ["/dev/mmcblk0p1"]
    assert result[0]["block_device_capacity_bytes"] == 64
    assert result[0]["capacity_note"] == (
        "Block-device and filesystem capacity are reported separately."
    )
    assert result[0]["read_only"] is True
