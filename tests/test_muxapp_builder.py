from pathlib import Path
import struct
import stat
import zipfile
import zlib

from tools.build_muxapp import validate_archive


def _archive(path: Path, entries: dict[str, bytes], executable=()):
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            info = zipfile.ZipInfo(name)
            mode = stat.S_IFREG | (0o755 if name in executable else 0o644)
            info.external_attr = mode << 16
            archive.writestr(info, payload)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _png(width, height):
    # Valid 8-bit RGBA PNG with one filter byte per scanline.
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    pixels = b"".join(b"\x00" + bytes(width * 4) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(pixels))
        + _png_chunk(b"IEND", b"")
    )


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
        "CometDesk/love/version.txt": b"0.7.2-dev\n",
        "CometDesk/love/storage_selection.lua": b"return {}\n",
        "CometDesk/service/desktop_environment.py": b"print('Debian desktop manager')\n",
        "CometDesk/service/desktop_input.py": b"print('controller bridge')\n",
        "CometDesk/service/media_vault.py": b"print('IPTV and web radio')\n",
        "CometDesk/service/uplink_status.py": b"print('uplink manager')\n",
        "CometDesk/service/forge_apt.py": b"print('APT software centre')\n",
        "CometDesk/service/app_registry.py": b"print('Comet application registry')\n",
        "CometDesk/assets/backgrounds/comet-dashboard-640x480.png": _png(320, 240),
        "CometDesk/assets/icons/comet-desk-atlas.png": _png(288, 48),
        "CometDesk/assets/branding/comet-desk-logo.png": _png(160, 54),
        "CometDesk/love/assets/backgrounds/comet-dashboard-640x480.png": _png(320, 240),
        "CometDesk/love/assets/icons/comet-desk-atlas.png": _png(288, 48),
        "CometDesk/lib/love": _elf(),
        "CometDesk/lib/liblove-11.5.so": _elf(),
        "CometDesk/lib/libluajit-5.1.so.2": _elf(),
    }
    return entries


def test_accepts_complete_muxapp(tmp_path):
    path = tmp_path / "CometDesk.muxapp"
    _archive(path, _valid_entries(), executable={"CometDesk/mux_launch.sh"})
    assert validate_archive(path) == []


def test_header_uses_the_bundled_application_version():
    source = (Path(__file__).parents[1] / "love" / "main.lua").read_text(encoding="utf-8")
    assert 'text("DEBIAN APT CONTROL DECK  //  v" .. appVersion' in source
    assert "v0.7.0-dev" not in source


def test_rejects_path_traversal(tmp_path):
    path = tmp_path / "unsafe.muxapp"
    entries = _valid_entries()
    entries["CometDesk/../../outside"] = b"nope"
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("unsafe archive path" in error for error in validate_archive(path))


def test_rejects_missing_version_metadata(tmp_path):
    path = tmp_path / "missing-version.muxapp"
    entries = _valid_entries()
    del entries["CometDesk/love/version.txt"]
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("required file missing: love/version.txt" in error for error in validate_archive(path))


def test_rejects_missing_runtime_asset_inside_love_game(tmp_path):
    path = tmp_path / "missing-game-art.muxapp"
    entries = _valid_entries()
    del entries["CometDesk/love/assets/icons/comet-desk-atlas.png"]
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("LÖVE game asset missing: assets/icons/comet-desk-atlas.png" in error
               for error in validate_archive(path))


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
    assert any("expected 288x48" in error for error in validate_archive(path))


def test_rejects_corrupt_artwork_crc(tmp_path):
    path = tmp_path / "corrupt-artwork.muxapp"
    entries = _valid_entries()
    name = "CometDesk/assets/icons/comet-desk-atlas.png"
    damaged = bytearray(entries[name])
    damaged[29] ^= 0x01  # Flip one IHDR data bit without updating its CRC.
    entries[name] = bytes(damaged)
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("CRC mismatch" in error for error in validate_archive(path))


def test_rejects_truncated_artwork_chunk(tmp_path):
    path = tmp_path / "truncated-artwork.muxapp"
    entries = _valid_entries()
    name = "CometDesk/assets/backgrounds/comet-dashboard-640x480.png"
    entries[name] = entries[name][:-7]
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("chunk extends beyond the file" in error or "missing IHDR, IDAT or IEND" in error
               for error in validate_archive(path))


def test_rejects_invalid_artwork_zlib_stream(tmp_path):
    path = tmp_path / "invalid-artwork-zlib.muxapp"
    entries = _valid_entries()
    name = "CometDesk/assets/branding/comet-desk-logo.png"
    data = bytearray(entries[name])
    # Keep the PNG and ZIP CRCs valid while corrupting the compressed IDAT stream.
    idat = data.index(b"IDAT")
    payload_offset = idat + 4
    data[payload_offset] ^= 0xFF
    chunk_length = struct.unpack_from(">I", data, idat - 4)[0]
    chunk_end = idat + 4 + chunk_length
    crc = zlib.crc32(data[idat:chunk_end]) & 0xFFFFFFFF
    struct.pack_into(">I", data, chunk_end, crc)
    entries[name] = bytes(data)
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("invalid IDAT zlib stream" in error or "IDAT data does not match" in error
               for error in validate_archive(path))


def test_rejects_missing_desktop_input_bridge(tmp_path):
    path = tmp_path / "missing-input-bridge.muxapp"
    entries = _valid_entries()
    del entries["CometDesk/service/desktop_input.py"]
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("required file missing: service/desktop_input.py" in error
               for error in validate_archive(path))


def test_rejects_missing_media_vault_service(tmp_path):
    path = tmp_path / "missing-media-vault.muxapp"
    entries = _valid_entries()
    del entries["CometDesk/service/media_vault.py"]
    _archive(path, entries, executable={"CometDesk/mux_launch.sh"})
    assert any("required file missing: service/media_vault.py" in error
               for error in validate_archive(path))
