#!/usr/bin/env python3
"""Comet Desk Media Vault: IPTV playlists, XMLTV EPG, web radio and one player owner.

This service is deliberately host-side. It uses only Python's standard library
and the player already present on muOS (mpv preferred, ffplay as fallback).
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import gzip
import hashlib
import json
import os
import re
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

APP_VERSION = "0.1.0"
MAX_PLAYLIST_BYTES = 16 * 1024 * 1024
MAX_EPG_BYTES = 64 * 1024 * 1024
MAX_CHANNELS = 4000
HEARTBEAT_TIMEOUT = 8.0
USER_AGENT = "CometDesk-MediaVault/0.1 (+https://github.com/SilverCrow2323/comet-desk)"
ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)="(.*?)"')

DEFAULT_CONFIG = {
    "schema_version": 1,
    "active_playlist": "iptv-org-it",
    "playlists": [
        {
            "id": "iptv-org-it",
            "name": "IPTV-org // ITALIA",
            "type": "url",
            "source": "https://iptv-org.github.io/iptv/countries/it.m3u",
            "enabled": True,
        }
    ],
    "epg_urls": [
        "https://epg-guide.com/wltv.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/it.xml.gz",
    ],
    "radios": [
        {
            "id": "rai-radio-1",
            "name": "Rai Radio 1",
            "genre": "News / Talk",
            "country": "Italy",
            "url": "http://icestreaming.rai.it/1.mp3",
            "homepage": "https://www.raiplaysound.it/",
            "favorite": False,
        },
        {
            "id": "radio-deejay",
            "name": "Radio Deejay",
            "genre": "Pop",
            "country": "Italy",
            "url": "https://4c4b867c89244861ac216426883d1ad0.msvdn.net/radiodeejay/radiodeejay/master_ma.m3u8",
            "homepage": "https://www.deejay.it/",
            "favorite": False,
        },
        {
            "id": "radio-italia",
            "name": "Radio Italia",
            "genre": "Italian Pop",
            "country": "Italy",
            "url": "https://radioitaliasmi.akamaized.net/hls/live/2093120/RISMI/master.m3u8",
            "homepage": "https://www.radioitalia.it/",
            "favorite": False,
        },
        {
            "id": "radio-24",
            "name": "Radio 24",
            "genre": "News / Talk",
            "country": "Italy",
            "url": "https://ilsole24ore-radio.akamaized.net/hls/live/2035301/radio24/playlist-48000.m3u8",
            "homepage": "https://www.radio24.ilsole24ore.com/",
            "favorite": False,
        },
    ],
    "favorites": [
        "radio:rai-radio-1", "radio:radio-deejay",
        "radio:radio-italia", "radio:radio-24",
    ],
    "player": "auto",
    "last_playlist_sync": {},
    "last_epg_sync": 0,
}


class MediaError(RuntimeError):
    pass


def clean(value: Any, limit: int = 180) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").replace("\r", " ").strip()[:limit]


def data_paths(app_dir: Path) -> dict[str, Path]:
    data = app_dir / "data"
    return {
        "data": data,
        "config": data / "media-vault.json",
        "catalogue": data / "media-vault.catalog",
        "status": data / "media-player.status",
        "command": data / "media-player.command",
        "heartbeat": data / "media-player.heartbeat",
        "supervisor_lock": data / "media-player.lock",
        "catalogue_lock": data / "media-catalogue.lock",
        "supervisor_pid": data / "media-player.supervisor.pid",
        "player_pid": data / "media-player.pid",
        "log": data / "media-player.log",
        "playlists": data / "media" / "playlists" / "cache",
        "playlist_imports": data / "media" / "playlists" / "imports",
        "epg_cache": data / "media" / "epg",
        "epg_status": data / "media-epg.status",
        "epg_catalogue": data / "media-vault.epg",
        "recordings": data / "media" / "recordings",
    }


def atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_config(app_dir: Path) -> dict:
    paths = data_paths(app_dir)
    path = paths["config"]
    if not path.exists():
        save_config(app_dir, json.loads(json.dumps(DEFAULT_CONFIG)))
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MediaError("Media Vault configuration is unreadable: {}".format(exc)) from exc
    if not isinstance(stored, dict):
        raise MediaError("Media Vault configuration must be a JSON object")
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for key, value in stored.items():
        if key in ("playlists", "epg_urls", "radios", "favorites", "last_playlist_sync"):
            if isinstance(value, list) or isinstance(value, dict):
                merged[key] = value
        elif key in ("active_playlist", "player", "last_epg_sync", "schema_version"):
            merged[key] = value
    merged["playlists"] = [row for row in merged["playlists"]
                           if isinstance(row, dict) and row.get("id") and row.get("source")]
    merged["radios"] = [row for row in merged["radios"]
                        if isinstance(row, dict) and row.get("id") and row.get("url")]
    return merged


def save_config(app_dir: Path, config: dict) -> None:
    atomic_write(data_paths(app_dir)["config"],
                 json.dumps(config, indent=2, ensure_ascii=False) + "\n")


def with_catalogue_lock(app_dir: Path, callback):
    path = data_paths(app_dir)["catalogue_lock"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise MediaError("refusing symbolic-link Media Vault catalogue lock")
    with path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return callback()
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def safe_url(value: str) -> str:
    url = str(value or "").strip()
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise MediaError("only HTTP/HTTPS media URLs are supported")
    if parts.username or parts.password:
        raise MediaError("credentials embedded in media URLs are not accepted")
    if any(ord(ch) < 32 for ch in url):
        raise MediaError("media URL contains control characters")
    return url


def fetch_bytes(url: str, max_bytes: int, timeout: int = 35) -> bytes:
    url = safe_url(url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*",
                 "Accept-Encoding": "gzip"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise MediaError("server returned HTTP {}".format(status))
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise MediaError("remote media index exceeds the size limit")
            data = response.read(max_bytes + 1)
    except (OSError, ValueError) as exc:
        raise MediaError("download failed: {}".format(exc)) from exc
    if len(data) > max_bytes:
        raise MediaError("remote media index exceeds the size limit")
    if data[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=__import__("io").BytesIO(data)) as stream:
                data = stream.read(max_bytes + 1)
        except OSError as exc:
            raise MediaError("gzip media index is invalid: {}".format(exc)) from exc
        if len(data) > max_bytes:
            raise MediaError("decompressed media index exceeds the size limit")
    return data


def decode_text(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", "replace")


def parse_m3u(text: str) -> dict:
    """Parse M3U/M3U8 metadata and return channels plus EPG URL declarations."""
    channels, epg_urls = [], []
    pending = None
    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            attrs = dict(ATTR_RE.findall(line))
            for key in ("url-tvg", "x-tvg-url", "tvg-url"):
                for url in attrs.get(key, "").split(","):
                    url = url.strip()
                    if url and url not in epg_urls:
                        try:
                            epg_urls.append(safe_url(url))
                        except MediaError:
                            continue
            continue
        if line.startswith("#EXTINF"):
            attrs = dict(ATTR_RE.findall(line))
            name = line.rsplit(",", 1)[1].strip() if "," in line else ""
            pending = {
                "name": name or attrs.get("tvg-name") or "Untitled channel",
                "tvg_id": attrs.get("tvg-id", ""),
                "tvg_name": attrs.get("tvg-name", ""),
                "logo": attrs.get("tvg-logo", ""),
                "group": attrs.get("group-title", "Other"),
                "options": {},
            }
            continue
        if line.startswith("#EXTVLCOPT:") and pending is not None:
            body = line.split(":", 1)[1]
            if "=" in body:
                key, value = (part.strip() for part in body.split("=", 1))
                key = key.lower()
                if key in ("http-user-agent", "http-referrer", "http-referer", "http-origin"):
                    pending["options"][key] = value[:300]
            continue
        if line.startswith("#EXTHTTP:") and pending is not None:
            try:
                headers = json.loads(line.split(":", 1)[1])
                if isinstance(headers, dict):
                    pending["options"]["headers"] = {
                        str(k)[:80]: str(v)[:300] for k, v in headers.items()
                    }
            except ValueError:
                pass
            continue
        if line.startswith("#"):
            continue
        try:
            url = safe_url(line)
        except MediaError:
            pending = None
            continue
        if pending is None:
            pending = {"name": urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1] or "Stream",
                       "tvg_id": "", "tvg_name": "", "logo": "",
                       "group": "Other", "options": {}}
        pending.update({"url": url, "id": hashlib.sha1(url.encode()).hexdigest()[:16]})
        channels.append(pending)
        pending = None
        if len(channels) >= MAX_CHANNELS:
            break
    groups = list(dict.fromkeys(item["group"] for item in channels))
    return {"channels": channels, "epg_urls": epg_urls, "groups": groups}


def playlist_cache_path(app_dir: Path, url: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return data_paths(app_dir)["playlists"] / (key + ".m3u")


def sync_import_folder(app_dir: Path, config: dict) -> bool:
    """Discover user-copied .m3u/.m3u8 files without mixing them with URL cache."""
    folder = data_paths(app_dir)["playlist_imports"]
    folder.mkdir(parents=True, exist_ok=True)
    changed = False
    for path in sorted(folder.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix.lower() not in (".m3u", ".m3u8"):
            continue
        try:
            size = path.stat().st_size
            if size <= 0 or size > MAX_PLAYLIST_BYTES:
                continue
            resolved = path.resolve(strict=True)
            if folder.resolve() not in resolved.parents:
                continue
        except OSError:
            continue
        entry_id = "local-" + hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
        existing = next((row for row in config["playlists"] if row.get("id") == entry_id), None)
        name = path.stem.replace("_", " ").replace("-", " ").strip() or "Local IPTV"
        row = {"id": entry_id, "name": clean(name, 80), "type": "file",
               "source": str(resolved), "enabled": True}
        if existing is None:
            if len(config["playlists"]) >= 24:
                continue
            config["playlists"].append(row)
            changed = True
        elif existing != row:
            existing.update(row)
            changed = True
    if changed:
        save_config(app_dir, config)
    return changed


def load_playlist(app_dir: Path, entry: dict, force: bool = False) -> dict:
    paths = data_paths(app_dir)
    source = entry.get("source", "")
    if entry.get("type") == "file":
        source_path = Path(source)
        if source_path.is_symlink():
            raise MediaError("local playlist must not be a symbolic link")
        target = source_path.resolve()
        root = paths["playlist_imports"].resolve()
        if target == root or root not in target.parents:
            raise MediaError("local playlist must live inside the Media Vault imports folder")
        if not target.is_file() or target.stat().st_size > MAX_PLAYLIST_BYTES:
            raise MediaError("local playlist is unavailable or exceeds the size limit")
        payload = target.read_bytes()
    else:
        source = safe_url(source)
        cached = playlist_cache_path(app_dir, source)
        config = load_config(app_dir)
        last_sync = config.get("last_playlist_sync", {}).get(entry.get("id"), 0)
        if cached.is_file() and not force and time.time() - float(last_sync or 0) < 6 * 3600:
            payload = cached.read_bytes()
        else:
            payload = fetch_bytes(source, MAX_PLAYLIST_BYTES)
            cached.parent.mkdir(parents=True, exist_ok=True)
            temporary = cached.with_suffix(".tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, cached)
            config.setdefault("last_playlist_sync", {})[entry.get("id")] = time.time()
            save_config(app_dir, config)
    result = parse_m3u(decode_text(payload))
    if not result["channels"]:
        raise MediaError("playlist contains no supported HTTP/HTTPS channels")
    return result


def parse_xmltv_time(value: str | None) -> float | None:
    if not value:
        return None
    parts = value.strip().split()
    base = parts[0][:14].ljust(14, "0")
    try:
        dt = datetime.strptime(base, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    offset = timedelta(0)
    if len(parts) > 1 and len(parts[1]) == 5 and parts[1][0] in "+-":
        try:
            offset = timedelta(hours=int(parts[1][1:3]),
                               minutes=int(parts[1][3:5]))
            if parts[1][0] == "-":
                offset = -offset
        except ValueError:
            pass
    return (dt - offset).replace(tzinfo=timezone.utc).timestamp()


def parse_epg(payload: bytes, max_programmes: int = 60_000) -> dict[str, list[dict]]:
    if payload[:2] == b"\x1f\x8b":
        import io
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
                payload = stream.read(MAX_EPG_BYTES + 1)
        except OSError as exc:
            raise MediaError("EPG gzip payload is invalid: {}".format(exc)) from exc
    if len(payload) > MAX_EPG_BYTES:
        raise MediaError("EPG document exceeds the size limit")
    import io
    names: dict[str, list[str]] = {}
    index: dict[str, list[dict]] = {}
    total = 0
    try:
        for _, element in ET.iterparse(io.BytesIO(payload), events=("end",)):
            tag = element.tag.split("}")[-1]
            if tag == "channel":
                channel_id = (element.get("id") or "").strip().lower()
                labels = [(node.text or "").strip().lower()
                          for node in element.findall("display-name") if node.text]
                if channel_id:
                    names[channel_id] = labels
                element.clear()
            elif tag == "programme":
                channel_id = (element.get("channel") or "").strip().lower()
                start = parse_xmltv_time(element.get("start"))
                stop = parse_xmltv_time(element.get("stop"))
                title_node = element.find("title")
                desc_node = element.find("desc")
                title = (title_node.text or "").strip() if title_node is not None else "?"
                desc = (desc_node.text or "").strip() if desc_node is not None else ""
                if channel_id and start is not None:
                    item = {"start": start, "stop": stop or start + 1800,
                            "title": title[:240], "description": desc[:600]}
                    for key in set([channel_id] + names.get(channel_id, [])):
                        index.setdefault(key, []).append(item)
                    total += 1
                    if total >= max_programmes:
                        break
                element.clear()
    except ET.ParseError as exc:
        raise MediaError("EPG XMLTV parse failed: {}".format(exc)) from exc
    for rows in index.values():
        rows.sort(key=lambda row: row["start"])
    return index


def now_next(index: dict[str, list[dict]], channel: dict, now: float | None = None):
    now = now or time.time()
    keys = [channel.get("tvg_id", "").lower(),
            channel.get("tvg_name", "").lower(),
            channel.get("name", "").lower()]
    programmes = []
    for key in keys:
        if key and index.get(key):
            programmes = index[key]
            break
    current, following = None, None
    for item in programmes:
        if item["start"] <= now < item["stop"]:
            current = item
        elif item["start"] > now:
            following = item
            break
    return current, following


def sync_epg(app_dir: Path, config: dict, force: bool = False) -> dict:
    paths = data_paths(app_dir)
    index: dict[str, list[dict]] = {}
    sources_ok, sources_error = [], []
    paths["epg_cache"].mkdir(parents=True, exist_ok=True)
    for url in config.get("epg_urls", [])[:4]:
        try:
            url = safe_url(url)
            key = hashlib.sha256(url.encode()).hexdigest()[:20]
            cache = paths["epg_cache"] / (key + ".xml")
            if cache.is_file() and not force and time.time() - cache.stat().st_mtime < 12 * 3600:
                payload = cache.read_bytes()
            else:
                payload = fetch_bytes(url, MAX_EPG_BYTES, timeout=70)
                temporary = cache.with_suffix(".tmp")
                temporary.write_bytes(payload)
                os.replace(temporary, cache)
            parsed = parse_epg(payload, max_programmes=60_000)
            for channel_key, programmes in parsed.items():
                index.setdefault(channel_key, []).extend(programmes)
            sources_ok.append(url)
        except Exception as exc:
            sources_error.append((url, str(exc)[:120]))
    for programmes in index.values():
        programmes.sort(key=lambda row: row["start"])
    config["last_epg_sync"] = time.time()
    save_config(app_dir, config)
    # JSON keeps the index reusable by later catalogue refreshes; gzip/cache
    # sources remain untouched and the index is capped by parse_epg().
    atomic_write(paths["data"] / "media-epg-index.json",
                 json.dumps(index, ensure_ascii=False, separators=(",", ":")))

    # Materialise only a small Now/Next view for the active playlist. The TUI
    # does not load the full multi-day XMLTV index into the 1 GB handheld UI.
    epg_rows = []
    active = next((row for row in config.get("playlists", [])
                   if row.get("id") == config.get("active_playlist")), None)
    if active:
        try:
            channels = load_playlist(app_dir, active, force=False)["channels"]
            now = time.time()
            for channel in channels:
                current, following = now_next(index, channel, now=now)
                epg_rows.append("EPG|{}|{}|{}".format(
                    clean(channel.get("id"), 80),
                    clean(current.get("title") if current else "NO CURRENT PROGRAMME", 120),
                    clean(following.get("title") if following else "NO NEXT PROGRAMME", 120),
                ))
        except Exception:
            pass
    atomic_write(paths["epg_catalogue"], "\n".join(epg_rows) + ("\n" if epg_rows else ""))

    state = "READY" if sources_ok and not sources_error else ("DEGRADED" if sources_ok else "FAILED")
    atomic_write(paths["epg_status"], "{}|{}|{}|{}\n".format(
        state, len(sources_ok), len(sources_error), int(time.time())
    ))
    return {"index": index, "ok": sources_ok, "errors": sources_error}


def build_catalogue(app_dir: Path, force: bool = False, include_epg: bool = False) -> dict:
    config = load_config(app_dir)
    sync_import_folder(app_dir, config)
    active = next((row for row in config["playlists"]
                   if row.get("id") == config.get("active_playlist")), None)
    playlist = {"channels": [], "groups": [], "epg_urls": []}
    playlist_error = ""
    if active:
        try:
            playlist = load_playlist(app_dir, active, force=force)
            changed_epg = False
            for url in playlist.get("epg_urls", []):
                if url not in config["epg_urls"] and len(config["epg_urls"]) < 4:
                    config["epg_urls"].append(url)
                    changed_epg = True
            if changed_epg:
                save_config(app_dir, config)
        except Exception as exc:
            playlist_error = str(exc)
    radios = config["radios"]
    favourites = set(config.get("favorites", []))
    channels = playlist["channels"]
    rows = [
        "META|{}|{}|{}|{}|{}".format(
            len(config["playlists"]), len(channels), len(radios),
            clean(active.get("name", "") if active else "NO PLAYLIST", 80),
            clean(playlist_error, 160),
        )
    ]
    for item in config["playlists"]:
        rows.append("PLAYLIST|{}|{}|{}".format(
            clean(item.get("id"), 80), clean(item.get("name"), 100),
            "1" if item.get("id") == config.get("active_playlist") else "0",
        ))
    for radio in radios:
        rows.append("RADIO|{}|{}|{}|{}|{}".format(
            clean(radio["id"], 80), clean(radio.get("name"), 100),
            clean(radio.get("genre"), 60), clean(radio.get("url"), 600),
            "1" if ("radio:" + radio["id"]) in favourites or radio.get("favorite") else "0",
        ))
    for channel in channels:
        option_blob = base64.urlsafe_b64encode(
            json.dumps(channel.get("options", {}), ensure_ascii=True,
                       separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        rows.append("TV|{}|{}|{}|{}|{}|{}|{}".format(
            clean(channel["id"], 80), clean(channel["name"], 100),
            clean(channel.get("group"), 80), clean(channel["url"], 600),
            clean(channel.get("tvg_id"), 120),
            "1" if ("tv:" + channel["id"]) in favourites else "0",
            option_blob,
        ))
    atomic_write(data_paths(app_dir)["catalogue"], "\n".join(rows) + "\n")
    return {"playlists": len(config["playlists"]), "channels": len(channels),
            "radios": len(radios), "error": playlist_error}


def activate_playlist(app_dir: Path, playlist_id: str) -> dict:
    config = load_config(app_dir)
    sync_import_folder(app_dir, config)
    selected = next((row for row in config["playlists"]
                     if row.get("id") == playlist_id), None)
    if selected is None or not selected.get("enabled", True):
        raise MediaError("playlist is unavailable or disabled")
    # Validate and parse before changing the active source. A broken playlist
    # must never replace a working library entry.
    parsed = load_playlist(app_dir, selected, force=False)
    if not parsed["channels"]:
        raise MediaError("selected playlist has no supported channels")
    config["active_playlist"] = playlist_id
    save_config(app_dir, config)
    return build_catalogue(app_dir, force=False)


def add_playlist(app_dir: Path, name: str, url: str) -> dict:
    url = safe_url(url)
    config = load_config(app_dir)
    digest = hashlib.sha1(url.encode()).hexdigest()[:10]
    entry_id = "custom-" + digest
    existing = next((row for row in config["playlists"] if row.get("id") == entry_id), None)
    if existing:
        existing["name"] = clean(name, 80) or "Custom IPTV"
    else:
        if len(config["playlists"]) >= 24:
            raise MediaError("Media Vault supports up to 24 playlists")
        config["playlists"].append({
            "id": entry_id, "name": clean(name, 80) or "Custom IPTV",
            "type": "url", "source": url, "enabled": True,
        })
    config["active_playlist"] = entry_id
    save_config(app_dir, config)
    return build_catalogue(app_dir, force=True)


def toggle_favourite(app_dir: Path, kind: str, item_id: str) -> bool:
    if kind not in ("radio", "tv"):
        raise MediaError("favourite type must be radio or tv")
    config = load_config(app_dir)
    candidates = config["radios"] if kind == "radio" else []
    if kind == "tv":
        playlist = next((row for row in config["playlists"]
                         if row.get("id") == config.get("active_playlist")), None)
        if playlist:
            candidates = load_playlist(app_dir, playlist)["channels"]
    if not any(row.get("id") == item_id for row in candidates):
        raise MediaError("selected media item was not found in the active catalogue")
    key = kind + ":" + item_id
    favourites = set(config.get("favorites", []))
    active = key not in favourites
    if active:
        favourites.add(key)
    else:
        favourites.discard(key)
    config["favorites"] = sorted(favourites)
    save_config(app_dir, config)
    build_catalogue(app_dir, force=False)
    return active


def discover_radios(query: str, country: str = "Italy", limit: int = 50) -> list[dict]:
    params = urllib.parse.urlencode({
        "name": query[:80], "country": country[:60],
        "hidebroken": "true", "order": "votes", "reverse": "true",
        "limit": max(1, min(100, int(limit))),
    })
    url = "https://de1.api.radio-browser.info/json/stations/search?" + params
    payload = fetch_bytes(url, 4 * 1024 * 1024, timeout=20)
    try:
        results = json.loads(decode_text(payload))
    except ValueError as exc:
        raise MediaError("radio directory returned invalid JSON") from exc
    stations = []
    for row in results:
        try:
            stream = safe_url(row.get("url_resolved") or row.get("url"))
        except MediaError:
            continue
        stations.append({
            "id": row.get("stationuuid") or hashlib.sha1(stream.encode()).hexdigest()[:16],
            "name": clean(row.get("name"), 100),
            "genre": clean(row.get("tags"), 100),
            "country": clean(row.get("country"), 60),
            "url": stream,
            "homepage": clean(row.get("homepage"), 300),
            "favorite": False,
        })
    return stations


def write_status(app_dir: Path, state: str, kind: str = "",
                 title: str = "", player: str = "") -> None:
    payload = "{}|{}|{}|{}\n".format(
        clean(state, 30), clean(kind, 20), clean(title, 160), clean(player, 40)
    )
    atomic_write(data_paths(app_dir)["status"], payload)


def read_status(app_dir: Path) -> dict:
    path = data_paths(app_dir)["status"]
    try:
        fields = path.read_text(encoding="utf-8").splitlines()[0].split("|", 3)
    except (OSError, IndexError):
        return {"state": "STOPPED", "kind": "", "title": "", "player": ""}
    fields += [""] * (4 - len(fields))
    return {"state": fields[0], "kind": fields[1], "title": fields[2], "player": fields[3]}


def write_command(app_dir: Path, action: str, *, kind: str = "",
                  url: str = "", title: str = "") -> None:
    if action not in ("play", "stop", "toggle", "shutdown"):
        raise MediaError("unknown Media Vault player command")
    payload = {"action": action, "kind": kind, "url": safe_url(url) if url else "",
               "title": clean(title, 160), "nonce": "{}-{}".format(os.getpid(), time.time_ns())}
    atomic_write(data_paths(app_dir)["command"],
                 json.dumps(payload, ensure_ascii=False) + "\n")


def heartbeat(app_dir: Path) -> None:
    path = data_paths(app_dir)["heartbeat"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def decode_channel_options(encoded: str) -> dict:
    """Decode the bounded URL-safe M3U option payload sent by the Comet UI."""
    if not isinstance(encoded, str) or len(encoded) > 8192:
        return {}
    try:
        padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return {}
    return _safe_stream_options(value)


def _safe_stream_options(options: dict | None) -> dict:
    if not isinstance(options, dict):
        return {}
    result = {}
    for key in ("http-user-agent", "http-referrer", "http-referer", "http-origin"):
        value = options.get(key)
        if isinstance(value, str) and value and len(value) <= 300 and not any(
            ch in value for ch in ("\r", "\n", chr(0))
        ):
            result[key] = value
    headers = options.get("headers")
    if isinstance(headers, dict):
        safe_headers = {}
        for key, value in list(headers.items())[:24]:
            key = str(key)[:80]
            value = str(value)[:300]
            if (re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_\x60|~-]+", key)
                    and not any(ch in value for ch in ("\r", "\n", chr(0)))):
                safe_headers[key] = value
        if safe_headers:
            result["headers"] = safe_headers
    return result


def _player_command(kind: str, url: str, options: dict | None = None) -> tuple[list[str], str]:
    options = _safe_stream_options(options)
    headers = dict(options.get("headers", {}))
    if options.get("http-origin"):
        headers["Origin"] = options["http-origin"]
    user_agent = options.get("http-user-agent")
    referrer = options.get("http-referrer") or options.get("http-referer")

    mpv = shutil.which("mpv")
    ffplay = shutil.which("ffplay")
    if mpv:
        command = [mpv, "--no-config", "--no-terminal", "--really-quiet",
                   "--network-timeout=12", "--cache=yes", "--cache-secs=5",
                   "--hwdec=auto-safe", "--osc=yes", "--input-cursor=yes"]
        if kind == "radio":
            command += ["--no-video", "--audio-display=no"]
        else:
            command += ["--fullscreen", "--keep-open=no"]
        if user_agent:
            command.append("--user-agent=" + user_agent)
        if referrer:
            command.append("--referrer=" + referrer)
        if headers:
            values = [key + ": " + value for key, value in headers.items()]
            command.append("--http-header-fields=" + ",".join(values))
        command.append(url)
        return command, "mpv"
    if ffplay:
        command = [ffplay, "-loglevel", "warning", "-autoexit"]
        if kind == "radio":
            command.append("-nodisp")
        else:
            command.append("-fs")
        if user_agent:
            command += ["-user_agent", user_agent]
        if referrer:
            command += ["-referer", referrer]
        if headers:
            values = "".join(key + ": " + value + "\r\n" for key, value in headers.items())
            command += ["-headers", values]
        command += ["-i", url]
        return command, "ffplay"
    raise MediaError("no media player found (mpv or ffplay)")


def _terminate(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=4)
    except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _supervisor(app_dir: Path) -> int:
    paths = data_paths(app_dir)
    paths["data"].mkdir(parents=True, exist_ok=True)
    lock = paths["supervisor_lock"].open("a+")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        atomic_write(paths["supervisor_pid"], str(os.getpid()) + "\n")
        started = time.monotonic()
        last_nonce = ""
        process: subprocess.Popen | None = None
        current_kind, current_title, current_player = "", "", ""
        stopping = False

        def request_stop(_signum=None, _frame=None):
            nonlocal stopping
            stopping = True

        old_handlers = {}
        for signum in (signal.SIGTERM, signal.SIGINT):
            old_handlers[signum] = signal.signal(signum, request_stop)

        try:
            write_status(app_dir, "STOPPED")
            while not stopping:
                try:
                    request = json.loads(paths["command"].read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    request = {}
                nonce = request.get("nonce", "") if isinstance(request, dict) else ""
                if nonce and nonce != last_nonce:
                    last_nonce = nonce
                    action = request.get("action")
                    if action in ("stop", "shutdown"):
                        _terminate(process)
                        process = None
                        write_status(app_dir, "STOPPED")
                        if action == "shutdown":
                            stopping = True
                    elif action == "play":
                        _terminate(process)
                        process = None
                        try:
                            kind = request.get("kind", "radio")
                            if kind not in ("radio", "tv"):
                                raise MediaError("unsupported media type")
                            url = safe_url(request.get("url", ""))
                            command, player_name = _player_command(kind, url)
                            log_path = paths["log"]
                            with log_path.open("ab") as log:
                                log.write(("\n=== PLAY {} // {} ===\n".format(
                                    kind.upper(), clean(request.get("title"), 100)
                                )).encode("utf-8", "replace"))
                                process = subprocess.Popen(
                                    command, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True,
                                    env={k: v for k, v in os.environ.items()
                                         if k not in ("LD_PRELOAD", "LD_AUDIT")},
                                )
                            current_kind = kind
                            current_title = clean(request.get("title"), 160)
                            current_player = player_name
                            atomic_write(paths["player_pid"], str(process.pid) + "\n")
                            write_status(app_dir, "PLAYING", kind, current_title, player_name)
                        except (OSError, MediaError) as exc:
                            process = None
                            write_status(app_dir, "FAILED", kind, str(exc), "")
                    elif action == "toggle" and process is not None and process.poll() is None:
                        status = read_status(app_dir)["state"]
                        try:
                            os.killpg(process.pid, signal.SIGCONT if status == "PAUSED" else signal.SIGSTOP)
                            write_status(app_dir, "PLAYING" if status == "PAUSED" else "PAUSED",
                                         current_kind, current_title, current_player)
                        except OSError:
                            pass

                if process is not None and process.poll() is not None:
                    code = process.returncode
                    process = None
                    try:
                        paths["player_pid"].unlink(missing_ok=True)
                    except OSError:
                        pass
                    write_status(app_dir, "STOPPED" if code == 0 else "ENDED",
                                 current_kind, current_title, current_player)

                try:
                    age = time.time() - paths["heartbeat"].stat().st_mtime
                except OSError:
                    age = HEARTBEAT_TIMEOUT + 1
                if time.monotonic() - started > HEARTBEAT_TIMEOUT and age > HEARTBEAT_TIMEOUT:
                    _terminate(process)
                    process = None
                    write_status(app_dir, "STOPPED")
                    stopping = True
                time.sleep(0.12)
        finally:
            _terminate(process)
            try:
                paths["player_pid"].unlink(missing_ok=True)
                paths["supervisor_pid"].unlink(missing_ok=True)
            except OSError:
                pass
            write_status(app_dir, "STOPPED")
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
    finally:
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
        finally:
            lock.close()
    return 0


def ensure_supervisor(app_dir: Path) -> None:
    paths = data_paths(app_dir)
    paths["data"].mkdir(parents=True, exist_ok=True)
    try:
        pid = int(paths["supervisor_pid"].read_text().strip())
        os.kill(pid, 0)
        command_line = Path("/proc/{}/cmdline".format(pid)).read_bytes()
        if b"media_vault.py" in command_line and b"supervisor" in command_line:
            return
    except (OSError, ValueError):
        pass

    # Never replay a stale PLAY command after a frontend crash or reboot.
    # queue_play writes the new command only after this supervisor is spawned.
    paths["supervisor_pid"].unlink(missing_ok=True)
    paths["command"].unlink(missing_ok=True)
    script = Path(__file__).resolve()
    log_path = paths["log"]
    with log_path.open("ab") as log:
        subprocess.Popen(
            [sys.executable, str(script), "supervisor", "--app-dir", str(app_dir)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
            env={k: v for k, v in os.environ.items()
                 if k not in ("LD_PRELOAD", "LD_AUDIT")},
        )


def stop_playback(app_dir: Path, timeout: float = 3.0) -> None:
    paths = data_paths(app_dir)
    try:
        supervisor_pid = int(paths["supervisor_pid"].read_text().strip())
    except (OSError, ValueError):
        supervisor_pid = None
    try:
        write_command(app_dir, "shutdown")
    except OSError:
        pass

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            current = int(paths["supervisor_pid"].read_text().strip())
            os.kill(current, 0)
            time.sleep(0.08)
        except (OSError, ValueError):
            supervisor_pid = None
            break

    # If the cooperative shutdown was not honoured, terminate only a process
    # whose cmdline still identifies it as our supervisor (not a recycled PID).
    if supervisor_pid is not None:
        try:
            command_line = Path("/proc/{}/cmdline".format(supervisor_pid)).read_bytes()
            if b"media_vault.py" in command_line and b"supervisor" in command_line:
                os.killpg(supervisor_pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    try:
        player_pid = int(paths["player_pid"].read_text().strip())
        os.killpg(player_pid, signal.SIGTERM)
    except (OSError, ValueError, ProcessLookupError):
        pass
    try:
        paths["player_pid"].unlink(missing_ok=True)
        paths["supervisor_pid"].unlink(missing_ok=True)
    except OSError:
        pass
    write_status(app_dir, "STOPPED")


def queue_play(app_dir: Path, kind: str, url: str, title: str) -> None:
    heartbeat(app_dir)
    ensure_supervisor(app_dir)
    write_command(app_dir, "play", kind=kind, url=url, title=title)


def queue_toggle(app_dir: Path) -> None:
    heartbeat(app_dir)
    ensure_supervisor(app_dir)
    write_command(app_dir, "toggle")


def play_foreground(app_dir: Path) -> int:
    """Play one TV stream while the Comet UI is suspended by mux_launch.sh."""
    paths = data_paths(app_dir)
    request_path = paths["data"] / "media-session.request"
    if request_path.is_symlink():
        raise MediaError("refusing symbolic-link media session request")
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MediaError("media session request is missing or invalid") from exc
    request_path.unlink(missing_ok=True)
    stop_playback(app_dir)
    kind = request.get("kind", "tv")
    if kind != "tv":
        raise MediaError("foreground handoff is reserved for IPTV video")
    url = safe_url(request.get("url", ""))
    title = clean(request.get("title", "IPTV channel"), 160)
    encoded_options = request.get("options", "")
    options = decode_channel_options(encoded_options)
    command, player_name = _player_command("tv", url, options)
    input_process = None
    input_script = Path(__file__).with_name("desktop_input.py")
    try:
        if input_script.is_file():
            try:
                input_process = subprocess.Popen(
                    [sys.executable, str(input_script), "--app-dir", str(app_dir),
                     "--profile", "media"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True,
                    env={k: v for k, v in os.environ.items()
                         if k not in ("LD_PRELOAD", "LD_AUDIT")},
                )
                time.sleep(0.08)
                if input_process.poll() is not None:
                    input_process = None
            except OSError:
                input_process = None

        with paths["log"].open("ab") as log:
            log.write(("\n=== TV PLAY // {} ===\n".format(title)).encode("utf-8", "replace"))
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
                env={k: v for k, v in os.environ.items()
                     if k not in ("LD_PRELOAD", "LD_AUDIT")},
            )
            atomic_write(paths["player_pid"], str(process.pid) + "\n")
            write_status(app_dir, "PLAYING", "tv", title, player_name)
            try:
                while process.poll() is None:
                    time.sleep(0.15)
            except KeyboardInterrupt:
                _terminate(process)
            finally:
                paths["player_pid"].unlink(missing_ok=True)
                write_status(app_dir, "STOPPED", "tv", title, player_name)
            return process.returncode or 0
    finally:
        if input_process is not None:
            _terminate(input_process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "init", "catalogue", "import-playlist", "activate-playlist", "refresh-epg",
        "play-radio", "play-tv", "stop", "toggle", "toggle-favourite", "supervisor", "playback",
    ))
    parser.add_argument("--app-dir", default=os.environ.get("COMET_DESK_APP_DIR", ""))
    parser.add_argument("--name", default="Custom IPTV")
    parser.add_argument("--url", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--query", default="")
    parser.add_argument("--kind", choices=("radio", "tv"), default="radio")
    args = parser.parse_args()
    if not args.app_dir:
        parser.error("--app-dir or COMET_DESK_APP_DIR is required")
    app_dir = Path(args.app_dir).resolve()
    try:
        if args.action == "supervisor":
            return _supervisor(app_dir)
        if args.action == "init":
            config = load_config(app_dir)
            result = with_catalogue_lock(app_dir, lambda: build_catalogue(app_dir, force=False))
            print(json.dumps(result))
            return 0
        if args.action == "catalogue":
            result = with_catalogue_lock(app_dir, lambda: build_catalogue(app_dir, force=args.force))
            print(json.dumps(result))
            return 0
        if args.action == "import-playlist":
            result = with_catalogue_lock(app_dir, lambda: add_playlist(app_dir, args.name, args.url))
            print(json.dumps(result))
            return 0
        if args.action == "activate-playlist":
            result = with_catalogue_lock(app_dir, lambda: activate_playlist(app_dir, args.query))
            print(json.dumps(result))
            return 0
        if args.action == "refresh-epg":
            config = load_config(app_dir)
            result = with_catalogue_lock(app_dir, lambda: sync_epg(app_dir, config, force=True))
            print(json.dumps({"sources_ok": len(result["ok"]),
                              "sources_error": len(result["errors"])}))
            return 0
        if args.action == "toggle-favourite":
            active = with_catalogue_lock(app_dir, lambda: toggle_favourite(app_dir, args.kind, args.query))
            print("FAVOURITE|{}".format("1" if active else "0"))
            return 0
        if args.action == "play-radio":
            config = load_config(app_dir)
            station = next((row for row in config["radios"]
                            if row.get("id") == args.query), None)
            if station is None:
                raise MediaError("radio station not found")
            queue_play(app_dir, "radio", station["url"], station["name"])
            return 0
        if args.action == "play-tv":
            if not args.url:
                raise MediaError("TV stream URL is required")
            paths = data_paths(app_dir)
            atomic_write(paths["data"] / "media-session.request",
                         json.dumps({"kind": "tv", "url": safe_url(args.url),
                                     "title": clean(args.name, 160)}) + "\n")
            return 0
        if args.action == "stop":
            stop_playback(app_dir)
            return 0
        if args.action == "toggle":
            queue_toggle(app_dir)
            return 0
        if args.action == "playback":
            return play_foreground(app_dir)
    except (MediaError, OSError, ValueError, json.JSONDecodeError) as exc:
        write_status(app_dir, "FAILED", "", str(exc), "")
        print("[media-vault] ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
