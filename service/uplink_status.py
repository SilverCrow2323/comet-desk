#!/usr/bin/env python3
"""Comet Desk Uplink status and Rt:Tailscale-M bootstrap for muOS Andromeda."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

RT_URL = "https://github.com/SilverCrow2323/muOS-Rt-Tailscale/releases/download/v0.2.0/RtTailscale-M-0.2.0.muxapp"
RT_SIZE = 40_324_056
RT_SHA256 = "55580f97902e45c7924b901138fa2cb8f6f125d7ba2b49def8f93f735558cad7"
APP_DIRS = (
    Path("/run/muos/storage/application/RtTailscale"),
    Path("/mnt/mmc/MUOS/application/RtTailscale"),
    Path("/mnt/sdcard/MUOS/application/RtTailscale"),
)


def run(args, timeout=4):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, "", ""


def process_running(pattern):
    code, out, _ = run(["pgrep", "-f", pattern])
    return code == 0 and bool(out)


def find_rt(app_dir: Path):
    candidates = [app_dir / "RtTailscale", app_dir / "external" / "rt-tailscale-m" / "app" / "RtTailscale", *APP_DIRS]
    for candidate in candidates:
        if (candidate / "rt").is_file() and (candidate / "ts").is_file():
            return candidate
    return None


def _wireless_interface(name: str, sys_class_net: Path) -> bool:
    if name.startswith(("wlan", "wl", "mlan")):
        return True
    interface = sys_class_net / name
    return (interface / "wireless").exists() or (interface / "phy80211").exists()


def _interface_value(sys_class_net: Path, name: str, field: str) -> str:
    try:
        return (sys_class_net / name / field).read_text(encoding="ascii").strip().lower()
    except OSError:
        return ""


def network_snapshot(app_dir: Path, *, sys_class_net: Path | None = None):
    sys_class_net = sys_class_net or Path("/sys/class/net")
    interfaces = []
    try:
        interfaces = sorted(p.name for p in sys_class_net.iterdir() if p.name != "lo")
    except OSError:
        pass
    wifi_if = next((n for n in interfaces if _wireless_interface(n, sys_class_net)), "")
    connected, ssid, ip = False, "", ""
    if wifi_if:
        _, link, _ = run(["iw", "dev", wifi_if, "link"])
        associated = bool(re.search(r"Connected to\s+[0-9a-f:]+", link, re.I))
        match = re.search(r"SSID:\s*(.+)", link)
        ssid = match.group(1).strip() if match else ""

        # muOS builds do not all expose the same wireless CLI. Fall back to
        # wpa_supplicant and iwgetid instead of interpreting missing iw output
        # as a disconnected radio.
        _, wpa_state, _ = run(["wpa_cli", "-i", wifi_if, "status"])
        values = dict(
            line.split("=", 1) for line in wpa_state.splitlines() if "=" in line
        )
        wpa_connected = values.get("wpa_state", "").upper() == "COMPLETED"
        if not ssid:
            ssid = values.get("ssid", "").strip()
        if not ssid:
            _, iwgetid_ssid, _ = run(["iwgetid", "-r", wifi_if])
            ssid = iwgetid_ssid.strip()

        _, addr, _ = run(["ip", "-o", "-4", "addr", "show", "dev", wifi_if])
        m = re.search(r"inet\s+([0-9.]+)", addr)
        ip = m.group(1) if m else ""
        operstate = _interface_value(sys_class_net, wifi_if, "operstate")
        connected = associated or wpa_connected or bool(ssid) or bool(ip and operstate == "up")
    hotspot_if = ""
    for name in interfaces:
        _, info, _ = run(["iw", "dev", name, "info"])
        if "type AP" in info:
            hotspot_if = name
            break
    hotspot = bool(hotspot_if and process_running("hostapd"))
    bt_powered = False
    _, bt_info, _ = run(["bluetoothctl", "show"])
    bt_powered = bool(re.search(r"Powered:\s*yes", bt_info, re.I))
    _, paired, _ = run(["bluetoothctl", "devices", "Paired"])
    bt_devices = len([x for x in paired.splitlines() if x.startswith("Device ")])
    _, sockets, _ = run(["ss", "-ltn"])
    _, processes, _ = run(["ps", "-eo", "comm,args"])
    ports = set(re.findall(r":(\d+)\s", sockets))
    services = {
        "dns": process_running("dnsmasq|unbound|dnscrypt"),
        "dashboard": "80" in ports or "8080" in ports or "muxwebserv" in processes,
        "ssh": "sshd" in processes,
        "sftp": "sshd" in processes,
        "terminal": "ttyd" in processes or "ttyd" in processes,
        "syncthing": process_running("syncthing"),
    }
    rt = find_rt(app_dir)
    tailscale = {"installed": bool(rt), "online": False, "backend": "NOT INSTALLED",
                 "peers": 0, "ip": ""}
    if rt:
        _, summary, _ = run([str(rt / "rt"), "summary"], timeout=5)
        values = dict(line.split("=", 1) for line in summary.splitlines() if "=" in line)
        _, raw, _ = run([str(rt / "ts"), "status", "--json"], timeout=6)
        try:
            status = json.loads(raw)
        except (ValueError, TypeError):
            status = {}
        self_node = status.get("Self") or {}
        peers = status.get("Peer") or {}
        ips = self_node.get("TailscaleIPs") or []
        tailscale.update({
            "online": status.get("BackendState") == "Running",
            "backend": status.get("BackendState") or values.get("backend", "INSTALLED"),
            "peers": sum(1 for peer in peers.values() if peer.get("Online")),
            "ip": ips[0] if ips else "",
        })
    return {
        "wifi_connected": connected, "wifi_ssid": ssid, "wifi_ip": ip,
        "hotspot_active": hotspot, "hotspot_ssid": "", "hotspot_interface": hotspot_if,
        "bt_powered": bt_powered, "bt_devices": bt_devices,
        "services": services, "tailscale": tailscale,
    }


def write_status(path: Path, data):
    def flag(value): return "1" if value else "0"
    sv, ts = data["services"], data["tailscale"]
    fields = [
        flag(data["wifi_connected"]), data["wifi_ssid"].replace("|", "/"), data["wifi_ip"],
        flag(data["hotspot_active"]), data["hotspot_ssid"], data["hotspot_interface"],
        flag(data["bt_powered"]), str(data["bt_devices"]),
        *[flag(sv[k]) for k in ("dns", "dashboard", "ssh", "sftp", "terminal", "syncthing")],
        flag(ts["installed"]), flag(ts["online"]), ts["backend"].replace("|", "/"),
        str(ts["peers"]), ts["ip"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text("|".join(fields) + "\n", encoding="utf-8")
    os.replace(temp, path)


def install_rt():
    targets = [Path("/mnt/mmc/MUOS/application"), Path("/mnt/sdcard/MUOS/application")]
    target = next((p for p in targets if p.is_dir() and os.access(p, os.W_OK)), None)
    if target is None:
        raise RuntimeError("No writable muOS application directory found on TF1 or TF2")
    destination = target / "RtTailscale"
    required_free = RT_SIZE * 2 + 16 * 1024 * 1024
    if shutil.disk_usage(target).free < required_free:
        raise RuntimeError("Not enough free space to stage and install Rt:Tailscale-M")
    if destination.exists():
        raise RuntimeError("Rt:Tailscale-M already exists; refresh status instead of overwriting it")
    with tempfile.TemporaryDirectory(prefix=".comet-rt-", dir=target) as temporary:
        temp = Path(temporary)
        archive = temp / "rttailscale.muxapp"
        request = urllib.request.Request(RT_URL, headers={"User-Agent": "CometDesk-Uplink"})
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as out:
            while True:
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > RT_SIZE:
                    raise RuntimeError("Rt:Tailscale-M download exceeded pinned size")
                digest.update(chunk)
                out.write(chunk)
        if size != RT_SIZE or digest.hexdigest() != RT_SHA256:
            raise RuntimeError("Rt:Tailscale-M package size/checksum mismatch")
        staging = temp / "staging"
        staging.mkdir()
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                rel = PurePosixPath(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if rel.is_absolute() or ".." in rel.parts or "\\\\" in info.filename or mode == 0o120000:
                    raise RuntimeError("Unsafe path in Rt:Tailscale-M package")
                zf.extract(info, staging)
        root = staging / "RtTailscale"
        if not all((root / p).is_file() for p in ("mux_launch.sh", "rt", "ts", "bin/tailscale", "bin/tailscaled")):
            raise RuntimeError("Rt:Tailscale-M archive has an unexpected layout")
        os.replace(root, destination)
    for name in ("rt", "ts", "watchdog", "mux_launch.sh", "bin/tailscale", "bin/tailscaled"):
        path = destination / name
        if path.exists():
            path.chmod(path.stat().st_mode | 0o111)
    code, out, err = run([str(destination / "rt"), "install"], timeout=120)
    if code != 0:
        raise RuntimeError(err or out or "Rt:Tailscale-M initialisation failed")
    run([str(destination / "rt"), "ensure"], timeout=30)
    return str(destination)


def main():
    app_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    action = sys.argv[2] if len(sys.argv) > 2 else "status"
    output = app_dir / "data" / "uplink.status"
    try:
        if action == "install":
            install_rt()
        elif action == "start":
            rt = find_rt(app_dir)
            if rt is None:
                raise RuntimeError("Rt:Tailscale-M is not installed")
            code, out, err = run([str(rt / "rt"), "install"], timeout=120)
            if code != 0:
                raise RuntimeError(err or out or "Rt:Tailscale-M repair failed")
            run([str(rt / "rt"), "ensure"], timeout=30)
        data = network_snapshot(app_dir)
        write_status(output, data)
    except Exception as exc:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("ERROR|" + str(exc).replace("|", "/") + "\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
