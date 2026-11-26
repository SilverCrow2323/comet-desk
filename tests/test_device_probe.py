import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "service" / "device_probe.py"
SPEC = importlib.util.spec_from_file_location("device_probe", MODULE)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_reference_profile_has_rg35xx_h_baseline():
    assert probe.REFERENCE["device"] == "Anbernic RG35XX H"
    assert probe.REFERENCE["soc"] == "Allwinner H700"
    assert probe.REFERENCE["display"] == {"width": 640, "height": 480}
    assert probe.REFERENCE["tf1_nominal_bytes"] == 64_000_000_000


def test_memory_parser_keeps_unknown_as_none(monkeypatch):
    monkeypatch.setattr(probe, "read_text", lambda _path: "MemFree: 12 kB")
    assert probe.parse_meminfo() == {"total_bytes": None}


def test_memory_parser_reads_memtotal(monkeypatch):
    monkeypatch.setattr(
        probe, "read_text", lambda _path: "MemTotal:       1024000 kB\nMemFree: 1 kB"
    )
    assert probe.parse_meminfo()["total_bytes"] == 1024000 * 1024


def test_device_tree_identity_is_not_guessed(monkeypatch):
    monkeypatch.setattr(probe, "read_text", lambda _path: None)
    monkeypatch.setattr(probe.platform, "machine", lambda: "aarch64")
    result = probe.device_identity()
    assert result["rg35xx_h_match"] is False
    assert result["h700_match"] is False
    assert result["confidence"] == "architecture-only"


def test_storage_is_empty_when_candidate_mounts_absent(monkeypatch):
    monkeypatch.setattr(probe, "_mounts", lambda: [])
    assert probe.storage_inventory() == []


def test_probe_is_read_only_and_includes_live_storage(monkeypatch):
    monkeypatch.setattr(probe, "device_identity", lambda: {"model": None})
    monkeypatch.setattr(probe, "parse_meminfo", lambda: {"total_bytes": 1024})
    monkeypatch.setattr(probe, "firmware_info", lambda: {"release": None})
    monkeypatch.setattr(probe, "storage_inventory", lambda: [])
    result = probe.probe()
    assert result["read_only"] is True
    assert result["storage"] == []
    assert result["memory"]["total_bytes"] == 1024


def test_mount_parser_unescapes_spaces_without_merging_fields(monkeypatch):
    monkeypatch.setattr(
        probe, "read_text",
        lambda _path: "/dev/mmcblk0p1 /mnt/my\\040card ext4 rw,noatime 0 0",
    )
    mounts = probe._mounts()
    assert mounts == [{
        "source": "/dev/mmcblk0p1",
        "mount_point": "/mnt/my card",
        "filesystem": "ext4",
        "options": "rw,noatime",
    }]


def test_storage_inventory_reports_live_read_only_state_and_capacity(monkeypatch):
    monkeypatch.setattr(probe, "_mounts", lambda: [{
        "source": "/dev/mmcblk0p1",
        "mount_point": "/mnt/mmc",
        "filesystem": "ext4",
        "options": "ro,noatime",
    }])
    monkeypatch.setattr(probe, "_filesystem_stats", lambda _path: {
        "total_bytes": 64_000_000_000,
        "used_bytes": 20_000_000_000,
        "available_bytes": 40_000_000_000,
    })
    monkeypatch.setattr(probe, "_block_size_bytes", lambda _source: 128_000_000_000)
    inventory = probe.storage_inventory()
    assert len(inventory) == 1
    assert inventory[0]["read_only"] is True
    assert inventory[0]["filesystem_capacity_bytes"] == 64_000_000_000
    assert inventory[0]["block_device_capacity_bytes"] == 128_000_000_000


def test_storage_inventory_does_not_invent_block_device_capacity(monkeypatch):
    monkeypatch.setattr(probe, "_mounts", lambda: [{
        "source": "/dev/mapper/storage",
        "mount_point": "/mnt/mmc",
        "filesystem": "ext4",
        "options": "rw",
    }])
    monkeypatch.setattr(probe, "_filesystem_stats", lambda _path: {
        "total_bytes": 32_000_000_000,
        "used_bytes": 1_000_000_000,
        "available_bytes": 30_000_000_000,
    })
    monkeypatch.setattr(probe, "_block_size_bytes", lambda _source: None)
    item = probe.storage_inventory()[0]
    assert item["block_device_capacity_bytes"] is None
    assert item["capacity_note"] == "Block-device size is unavailable; filesystem capacity shown."
