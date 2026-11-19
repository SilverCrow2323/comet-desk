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
    assert "--hwdec=auto-safe" in command
    assert "--osc=yes" in command
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


def test_radio_favourite_can_be_toggled_on_and_off(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "build_catalogue", lambda *args, **kwargs: {"ok": True})
    media.load_config(tmp_path)
    first = media.toggle_favourite(tmp_path, "radio", "radio-deejay")
    assert first is False
    config = media.load_config(tmp_path)
    assert "radio:radio-deejay" not in config["favorites"]

    second = media.toggle_favourite(tmp_path, "radio", "radio-deejay")
    assert second is True
    assert "radio:radio-deejay" in media.load_config(tmp_path)["favorites"]


def test_media_playlist_tv_catalogue_exports_favourite_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "load_playlist", lambda *args, **kwargs: {
        "channels": [{
            "id": "abc123", "name": "Channel One", "group": "News",
            "url": "https://example.org/tv.m3u8", "tvg_id": "channel.one"
        }],
        "groups": ["News"], "epg_urls": []
    })
    config = media.load_config(tmp_path)
    config["favorites"] = ["tv:abc123"]
    media.save_config(tmp_path, config)
    media.build_catalogue(tmp_path)
    rows = media.data_paths(tmp_path)["catalogue"].read_text().splitlines()
    assert "TV|abc123|Channel One|News|https://example.org/tv.m3u8|channel.one|1|e30" in rows


def test_epg_sync_exports_compact_now_next_rows_and_status(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = (now - timedelta(minutes=5)).strftime("%Y%m%d%H%M%S +0000")
    stop = (now + timedelta(minutes=25)).strftime("%Y%m%d%H%M%S +0000")
    next_start = (now + timedelta(minutes=25)).strftime("%Y%m%d%H%M%S +0000")
    next_stop = (now + timedelta(minutes=55)).strftime("%Y%m%d%H%M%S +0000")
    xml = (
        '<tv><channel id="test.channel"><display-name>Test Channel</display-name></channel>'
        '<programme start="' + start + '" stop="' + stop + '" channel="test.channel">'
        '<title>Current Show</title></programme>'
        '<programme start="' + next_start + '" stop="' + next_stop + '" channel="test.channel">'
        '<title>Next Show</title></programme></tv>'
    ).encode()
    monkeypatch.setattr(media, "fetch_bytes", lambda *args, **kwargs: xml)
    monkeypatch.setattr(media, "load_playlist", lambda *args, **kwargs: {
        "channels": [{
            "id": "stream-1", "name": "Test Channel", "tvg_id": "test.channel",
            "tvg_name": "Test Channel", "url": "https://example.org/live.m3u8"
        }],
        "groups": ["News"], "epg_urls": []
    })
    config = {
        "epg_urls": ["https://example.org/guide.xml"],
        "playlists": [{"id": "test", "name": "Test", "source": "https://example.org/list.m3u"}],
        "active_playlist": "test",
        "last_epg_sync": 0,
    }
    result = media.sync_epg(tmp_path, config, force=True)

    assert len(result["ok"]) == 1
    status = media.data_paths(tmp_path)["epg_status"].read_text().split("|")
    assert status[0] == "READY"
    rows = media.data_paths(tmp_path)["epg_catalogue"].read_text().splitlines()
    assert rows == ["EPG|stream-1|Current Show|Next Show"]


def test_foreground_tv_request_rejects_symbolic_link(tmp_path):
    paths = media.data_paths(tmp_path)
    paths["data"].mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"kind":"tv","url":"https://example.org/live.m3u8"}')
    paths["data"].joinpath("media-session.request").symlink_to(outside)
    with pytest.raises(media.MediaError, match="symbolic-link"):
        media.play_foreground(tmp_path)


def test_local_drop_folder_playlist_is_discovered_and_selectable(tmp_path, monkeypatch):
    folder = media.data_paths(tmp_path)["playlist_imports"]
    folder.mkdir(parents=True)
    (folder / "My Local TV.m3u").write_text(
        "#EXTM3U\n#EXTINF:-1 group-title=\"News\",News One\n"
        "https://example.org/news.m3u8\n",
        encoding="utf-8",
    )
    config = media.load_config(tmp_path)
    media.sync_import_folder(tmp_path, config)
    local = next(row for row in config["playlists"] if row.get("type") == "file")
    assert local["name"] == "My Local TV"
    parsed = media.load_playlist(tmp_path, local)
    assert parsed["channels"][0]["name"] == "News One"

    result = media.activate_playlist(tmp_path, local["id"])
    assert result["channels"] == 1
    assert media.load_config(tmp_path)["active_playlist"] == local["id"]


def test_local_drop_folder_rejects_symbolic_link(tmp_path):
    folder = media.data_paths(tmp_path)["playlist_imports"]
    folder.mkdir(parents=True)
    outside = tmp_path / "outside.m3u"
    outside.write_text("#EXTM3U\nhttps://example.org/live.m3u8\n")
    link = folder / "link.m3u"
    link.symlink_to(outside)
    config = media.load_config(tmp_path)
    media.sync_import_folder(tmp_path, config)
    assert not any(row.get("source") == str(link) for row in config["playlists"])


def test_load_playlist_rejects_configured_symlink_even_when_target_is_inside(tmp_path):
    folder = media.data_paths(tmp_path)["playlist_imports"]
    folder.mkdir(parents=True)
    target = folder / "real.m3u"
    target.write_text("#EXTM3U\nhttps://example.org/live.m3u8\n")
    link = folder / "linked.m3u"
    link.symlink_to(target)
    with pytest.raises(media.MediaError, match="symbolic link"):
        media.load_playlist(tmp_path, {
            "id": "local-link", "type": "file", "source": str(link)
        })


def test_catalogue_preserves_channel_stream_headers_for_player_handoff(tmp_path, monkeypatch):
    import base64

    monkeypatch.setattr(media, "load_playlist", lambda *args, **kwargs: {
        "channels": [{
            "id": "secure-stream", "name": "Secure Stream", "group": "News",
            "url": "https://example.org/live.m3u8", "tvg_id": "secure.id",
            "options": {
                "http-user-agent": "Comet Player/1.0",
                "http-referrer": "https://provider.example/",
                "headers": {"X-Provider-Key": "token-value"},
            },
        }],
        "groups": ["News"], "epg_urls": []
    })
    config = media.load_config(tmp_path)
    media.build_catalogue(tmp_path)
    row = next(line for line in media.data_paths(tmp_path)["catalogue"].read_text().splitlines()
               if line.startswith("TV|"))
    fields = row.split("|")
    options = json.loads(base64.urlsafe_b64decode(
        fields[7] + "=" * ((4 - len(fields[7]) % 4) % 4)
    ))
    assert options["http-user-agent"] == "Comet Player/1.0"
    assert options["http-referrer"] == "https://provider.example/"
    assert options["headers"]["X-Provider-Key"] == "token-value"


def test_channel_options_are_validated_before_reaching_mpv(monkeypatch):
    monkeypatch.setattr(media.shutil, "which",
                        lambda name: "/usr/bin/mpv" if name == "mpv" else None)
    command, player = media._player_command("tv", "https://example.org/live.m3u8", {
        "http-user-agent": "Provider/2.0",
        "http-referrer": "https://provider.example/",
        "headers": {"X-Provider": "value", "Bad Header": "not allowed",
                    "X-Injected": "one\r\n--no-config"},
    })
    assert player == "mpv"
    assert "--user-agent=Provider/2.0" in command
    assert "--referrer=https://provider.example/" in command
    assert "--http-header-fields=X-Provider: value" in command
    assert command.count("--no-config") == 1


def test_player_pid_guard_requires_owned_mpv_or_ffplay_cmdline(tmp_path):
    (tmp_path / "123").mkdir()
    (tmp_path / "123" / "cmdline").write_bytes(b"/usr/bin/mpv\0--fullscreen\0")
    (tmp_path / "124").mkdir()
    (tmp_path / "124" / "cmdline").write_bytes(b"/usr/bin/ssh\0remote\0")
    assert media.player_process_owned(123, tmp_path)
    assert not media.player_process_owned(124, tmp_path)
    assert not media.player_process_owned(999, tmp_path)
    assert not media.player_process_owned(1, tmp_path)
