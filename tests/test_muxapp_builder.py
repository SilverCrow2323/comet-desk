from pathlib import Path
import stat
import zipfile

from tools.build_muxapp import validate_archive


def _archive(path: Path, entries: dict[str, bytes], executable=()):
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            info = zipfile.ZipInfo(name)
            mode = stat.S_IFREG | (0o755 if name in executable else 0o644)
            info.external_attr = mode << 16
            archive.writestr(info, payload)


def _png(width, height):
    return b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00\\x00\\x00\\x0dIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\\x08\\x06\\x00\\x00\\x00"


def _elf():
    data = bytearray(64)
    data[:4] = b"\x7fELF"
    data[4:6] = b"\x02\x01"
    data[18:20] = (183).to_bytes(2, "little")
    return bytes(data)


def _valid_entries():
    entries = {
        "CometDesk/mux_launch.sh": b"#!/bin/sh\n",
        "CometDesk/love/main.lua": b"function love.draw() end\n",
        "CometDesk/love/conf.lua": b"function love.conf(t) end\n",
        "CometDesk/love/device_probe.lua": b"return {}\n",
        "CometDesk/love/diagnostics_report.lua": b"return {}\n",
        "CometDesk/love/theme.lua": b"return {}\n",
        "CometDesk/assets/backgrounds/comet-dashboard-640x480.png": _png(320, 240),
        "CometDesk/assets/icons/comet-desk-atlas.png": _png(288, 48),
        "CometDesk/lib/love": _elf(),
        "CometDesk/lib/liblove-11.5.so": _elf(),
        "CometDesk/lib/libluajit-5.1.so.2": _elf(),
    }
    return entries


def test_accepts_complete_muxapp(tmp_path):
    path = tmp_path / "CometDesk.muxapp"
    _archive(path, _valid_entries(), executable={"CometDesk/mux_launch.sh"})
    assert validate_archive(path) == []


def test_rejects_path_traversal(tmp_path):
    path = tmp_path / "unsafe.muxapp"
    entries = _valid_entries()
    entries["CometDesk/../../outside"] = b"nope"
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("unsafe archive path" in error for error in validate_archive(path))


def test_rejects_missing_runtime(tmp_path):
    path = tmp_path / "incomplete.muxapp"
    entries = _valid_entries()
    del entries["CometDesk/lib/libluajit-5.1.so.2"]
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("runtime file missing" in error for error in validate_archive(path))


def test_rejects_non_executable_launcher(tmp_path):
    path = tmp_path / "not-executable.muxapp"
    _archive(path, _valid_entries())
    assert any("not executable" in error for error in validate_archive(path))


def test_rejects_wrong_artwork_dimensions(tmp_path):
    path = tmp_path / "wrong-artwork.muxapp"
    entries = _valid_entries()
    entries["CometDesk/assets/icons/comet-desk-atlas.png"] = _png(256, 64)
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("unexpected PNG dimensions" in error for error in validate_archive(path))
