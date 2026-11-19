# Media Vault

Media Vault is Comet Desk's native IPTV and web-radio module. It reuses the useful playlist/EPG concepts from VoidCast while keeping the runtime independent of pygame and the VoidDesk desktop.

## Runtime and playback ownership

`service/media_vault.py` runs on the muOS host and uses an already available external player: MPV is preferred, with FFPlay as fallback. Comet does not install host packages or change muOS's package database.

There is exactly one Media Vault playback owner. Starting another radio or TV item first terminates the previous player process group. The supervisor writes an atomic status file and player PID, and receives a heartbeat from the running Comet frontend. If the frontend disappears unexpectedly, the heartbeat watchdog terminates playback.

Playback is also stopped:
- before a Debian desktop session starts;
- when Comet exits normally;
- before handing the display to a new full-screen TV stream;
- when the player finishes or the user selects Stop.

Radio can play in the background while Comet is visible. TV hands the display to a foreground player; when that player exits, the MUX launcher returns to Comet.

## IPTV playlists

The initial remote preset is IPTV-org Italy:

`https://iptv-org.github.io/iptv/countries/it.m3u`

The parser supports M3U/M3U8 channels and the common `tvg-id`, `tvg-name`, `tvg-logo`, `group-title`, `url-tvg` and `x-tvg-url` metadata. Per-channel User-Agent, Referrer, Origin and HTTP-header metadata are retained for supported VLC-style options, validated and passed to MPV/FFPlay.

### Add a local playlist

Copy `.m3u` or `.m3u8` files to:

`data/media/playlists/imports/`

Open Media Vault and refresh the catalogue with **Start**. The files are discovered as local playlist sources and appear in **PLAYLISTS**. Use D-pad left/right to cycle TV, RADIO and PLAYLISTS, up/down to select a source and A to activate it. Local playlist files are confined to that imports directory; symbolic links and files over the size limit are rejected. The remote default and copied local playlists share the same catalogue and EPG pipeline.

### Add a remote playlist

A remote HTTP/HTTPS playlist can also be registered with the service CLI:

```sh
python3 service/media_vault.py import-playlist \
  --app-dir /path/to/CometDesk \
  --name "My IPTV" \
  --url "https://example.org/playlist.m3u"
```

The active source can be changed from the PLAYLISTS view in Comet Desk. The service caches remote playlist bytes and refreshes them on demand or after the cache TTL.

## XMLTV EPG

Media Vault collects XMLTV sources from the configured EPG URL list and from playlist `url-tvg` metadata. It parses gzip XMLTV, resolves channel IDs/display names and creates an indexed programme cache. To keep memory use predictable on a 1 GB handheld, each sync is limited to four sources and 60,000 programmes per source, with a maximum document size.

The current UI displays **Now** and **Next** for the selected TV channel when a reliable ID/name match exists. The parser uses a bounded maximum of four XMLTV sources and 60,000 programmes per source to constrain memory usage. A complete multi-channel grid/timeline and richer channel matching remain planned work, not a claimed current feature.

EPG cache/status:
- `data/media-epg-index.json`
- `data/media-vault.epg` (compact active-playlist Now/Next view)
- `data/media-epg.status`

## Web radio

The default presets include Rai Radio 1, Radio Deejay, Radio Italia and Radio 24. Users can edit the station list in `data/media-vault.json`; the service also has a Radio Browser discovery helper. Favourites are stored in that same configuration and persist between sessions. Station URLs are broadcaster-controlled and may change, so a preset is not a guarantee of uninterrupted service.

Radio streams use audio-only MPV/FFPlay options and can be paused/resumed or stopped from the Comet Quick Panel (M). TV uses the full-screen player handoff.

## Controls

- **M** opens the Comet Quick Panel.
- **A** in the Quick Panel pauses/resumes the current stream.
- **X** in the Quick Panel stops playback.
- **Y** in the Quick Panel opens Media Vault.
- Inside Media Vault, **A** plays the selected radio/TV item or activates a playlist.
- **Y** toggles a radio/TV favourite.
- **X** stops playback.
- **Start** refreshes the playlist catalogue and EPG.
- The dedicated TV player mapping is documented in [Desktop Input](DESKTOP_INPUT.md).

## Files and safety

- Configuration: `data/media-vault.json`
- Playlist catalogue: `data/media-vault.catalog`
- Playback status: `data/media-player.status`
- Playback log: `data/media-player.log`
- Supervisor lock/PIDs/heartbeat: `data/media-player.lock`, `data/media-player.supervisor.pid`, `data/media-player.pid`, `data/media-player.heartbeat`

Only HTTP/HTTPS stream URLs are accepted; embedded URL credentials are rejected. Local playlists must be regular files under the imports folder. The TV session request is atomically written and symbolic-link requests are refused.

CI validates parsers, EPG Now/Next, playlist activation/drop discovery, favourite state, process command selection and request safety. Actual MPV/FFPlay availability, audio output, video decode, hardware acceleration, controller capture, station URLs and IPTV streams still require RG35XX H testing.
