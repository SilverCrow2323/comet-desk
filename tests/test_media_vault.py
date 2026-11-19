from __future__ import annotations

import gzip
import json
import time

import pytest

import service.media_vault as media


def test_m3u_parser_keeps_channel_metadata_groups_epg_and_headers():
    playlist = media.parse_m3u(
        '#EXTM3U url-tvg="https://example.org/guide.xml.gz"\n'
        '#EXTINF:-1 tvg-id="news.one" tvg-name="News One" '
        'tvg-logo="https://example.org/logo.png" group-title="News",News One HD\n'
        '#EXTVLCOPT:http-user-agent=CometTest/1\n'
        '#EXTVLCOPT:http-referrer=https://example.org/\n'
        'https://stream.example.org/live.m3u8\n'
    )
    assert playlist["epg_urls"] == ["https://example.org/guide.xml.gz"]
    channel = playlist["channels"][0]
    assert channel["name"] == "News One HD"
    assert channel["group"] == "News"
    assert channel["tvg_id"] == "news.one"
    assert channel["options"]["http-user-agent"] == "CometTest/1"
    assert channel["options"]["http-referrer"] == "https://example.org/"


def test_m3u_parser_rejects_non_http_streams_and_continues():
    playlist = media.parse_m3u(
        "#EXTM3U\n"
        "#EXTINF:-1 group-title=\"Bad\",Local file\n"
        "file:///etc/passwd\n"
        "#EXTINF:-1 group-title=\"Good\",Public stream\n"
        "https://example.org/live.m3u8\n"
    )
    assert [row["name"] for row in playlist["channels"]] == ["Public stream"]


def test_url_guard_rejects_local_and_credentialed_urls():
    with pytest.raises(media.MediaError):
        media.safe_url("file:///etc/passwd")
    with pytest.raises(media.MediaError):
        media.safe_url("https://user:password@example.org/live")


def test_default_library_has_one_iptv_preset_and_multiple_radio_presets(tmp_path):
    config = media.load_config(tmp_path)
    assert config["active_playlist"] == "iptv-org-it"
    assert config["playlists"][0]["source"].endswith("/countries/it.m3u")
    assert {row["name"] for row in config["radios"]} >= {
        "Rai Radio 1", "Radio Deejay", "Radio Italia", "Radio 24"
    }
    assert len(config["epg_urls"]) >= 2


def test_playlist_import_is_deduplicated_and_becomes_active(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "build_catalogue", lambda *args, **kwargs: {"ok": True})
    media.load_config(tmp_path)
    first = media.add_playlist(tmp_path, "My playlist", "https://example.org/list.m3u")
    second = media.add_playlist(tmp_path, "Renamed", "https://example.org/list.m3u")
    config = media.load_config(tmp_path)
    assert first == {"ok": True}
    assert second == {"ok": True}
    assert len([r for r in config["playlists"] if r["source"] == "https://example.org/list.m3u"]) == 1
    assert config["playlists"][-1]["name"] == "Renamed"
    assert config["active_playlist"] == config["playlists"][-1]["id"]


def test_xmltv_time_and_multi_key_now_next():
    now = media.parse_xmltv_time("20261119110000 +0100")
    assert now is not None
    index = {
        "rai1.it": [
            {"start": now - 60, "stop": now + 1200, "title": "News", "description": ""},
            {"start": now + 1200, "stop": now + 2400, "title": "Sport", "description": ""},
        ]
    }
    current, following = media.now_next(index, {
        "tvg_id": "Rai1.it", "tvg_name": "Rai 1", "name": "Rai Uno"
    }, now=now)
    assert current["title"] == "News"
    assert following["title"] == "Sport"


def test_epg_parser_handles_gzip_and_indexes_display_names():
    xml = (
        b'<?xml version="1.0"?><tv>'
        b'<channel id="rai1.it"><display-name>Rai 1</display-name></channel>'
        b'<programme start="20261119110000 +0100" stop="20261119120000 +0100" channel="rai1.it">'
        b'<title>News</title><desc>Daily news</desc></programme></tv>'
    )
    index = media.parse_epg(gzip.compress(xml))
    assert "rai1.it" in index
    assert "rai 1" in index
    assert index["rai1.it"][0]["title"] == "News"


def test_player_command_prefers_mpv_and_disables_video_for_radio(monkeypatch):
    monkeypatch.setattr(media.shutil, "which",
                        lambda name: "/usr/bin/mpv" if name == "mpv" else None)
    command, player = media._player_command("radio", "https://example.org/live.mp3")
    assert player == "mpv"
    assert "--no-video" in command
    assert command[-1] == "https://example.org/live.mp3"


def test_media_status_is_machine_readable(tmp_path):
    media.write_status(tmp_path, "PLAYING", "radio", "Rai Radio 1", "mpv")
    assert media.read_status(tmp_path) == {
        "state": "PLAYING", "kind": "radio", "title": "Rai Radio 1", "player": "mpv"
    }


def test_media_request_validates_urls_and_writes_atomic_command(tmp_path):
    media.write_command(tmp_path, "play", kind="radio",
                        url="https://example.org/live.mp3", title="Radio")
    payload = json.loads(media.data_paths(tmp_path)["command"].read_text())
    assert payload["action"] == "play"
    assert payload["kind"] == "radio"
    assert payload["url"] == "https://example.org/live.mp3"
    assert payload["title"] == "Radio"
    with pytest.raises(media.MediaError):
        media.write_command(tmp_path, "play", kind="tv",
                            url="file:///etc/passwd", title="bad")


def test_heartbeat_touch_updates_timestamp(tmp_path):
    path = media.data_paths(tmp_path)["heartbeat"]
    media.heartbeat(tmp_path)
    assert path.is_file()
    assert abs(time.time() - path.stat().st_mtime) < 2
