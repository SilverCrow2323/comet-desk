from __future__ import annotations

from service import forge_apt


def test_catalog_is_curated_and_input_leap_is_not_installable_from_apt():
    names = {entry[1] for entry in forge_apt.CATALOG}
    assert "qjoypad" in names
    assert "evtest" in names
    assert "libsdl2-dev" in names
    assert "build-essential" in names
    assert "input-leap" not in names
    assert any(entry[1] == "input-leap" for entry in forge_apt.SPECIAL)


def test_catalog_does_not_offer_host_or_boot_critical_packages():
    names = {entry[1] for entry in forge_apt.CATALOG}
    forbidden = {
        "systemd", "systemd-sysv", "linux-image-arm64", "grub-efi-arm64",
        "u-boot-tools", "initramfs-tools", "firmware-linux", "packagekit",
        "gnome-software", "discover", "flatpak", "snapd",
    }
    assert names.isdisjoint(forbidden)


def test_catalog_sections_have_ui_labels():
    names = {entry[0] for entry in forge_apt.CATALOG}
    assert names == {"INPUT", "DESKTOP", "DEVELOPMENT", "MEDIA", "NETWORK", "UTILITIES"}
    assert set(forge_apt.CATEGORIES) == {"ALL"} | names


def test_catalog_writer_escapes_delimiters_and_writes_atomic_file(tmp_path):
    rows = [{
        "category": "INPUT",
        "package": "evtest",
        "title": "Input | Event Monitor",
        "summary": "Line one\nLine two",
        "installed": False,
        "available": True,
        "size": "1.0 MB",
        "tag": "H700",
    }]
    forge_apt.write_catalog(tmp_path, rows, "Curated | catalogue")
    target = tmp_path / "data" / "forge-catalog.txt"
    assert target.is_file()
    lines = target.read_text().splitlines()
    assert lines[0].startswith("META|")
    assert lines[1] == "PKG|INPUT|evtest|Input / Event Monitor|Line one Line two|0|1|1.0 MB|H700"
    assert not target.with_suffix(".tmp").exists()


def test_package_catalog_has_no_arbitrary_package_injection():
    allowed = {entry[1] for entry in forge_apt.CATALOG}
    assert "evtest;rm -rf /" not in allowed
    assert "apt-get" not in allowed
