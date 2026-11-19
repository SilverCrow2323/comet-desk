from pathlib import Path
import importlib.util


SPEC = importlib.util.spec_from_file_location(
    "uplink_status", Path(__file__).parents[1] / "service" / "uplink_status.py"
)
uplink = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(uplink)


def _snapshot():
    return {
        "wifi_connected": True, "wifi_ssid": "LAB-WIFI", "wifi_ip": "192.0.2.4",
        "hotspot_active": False, "hotspot_ssid": "", "hotspot_interface": "",
        "bt_powered": True, "bt_devices": 2,
        "services": {
            "dns": True, "dashboard": False, "ssh": True,
            "sftp": True, "terminal": False, "syncthing": True,
        },
        "tailscale": {
            "installed": True, "online": True, "backend": "Running",
            "peers": 3, "ip": "100.64.0.10",
        },
    }


def _wireless_sysfs(root: Path, name: str):
    interface = root / name
    (interface / "wireless").mkdir(parents=True)
    (interface / "operstate").write_text("up\n", encoding="ascii")
    return interface


def test_wifi_connected_falls_back_to_wpa_supplicant_state(tmp_path, monkeypatch):
    sys_net = tmp_path / "sys/class/net"
    _wireless_sysfs(sys_net, "wlan0")

    def fake_run(args, timeout=4):
        if args == ["iw", "dev", "wlan0", "link"]:
            return 127, "", "iw unavailable"
        if args == ["wpa_cli", "-i", "wlan0", "status"]:
            return 0, "wpa_state=COMPLETED\nssid=My Home WiFi\n", ""
        if args[:2] == ["ip", "-o"]:
            return 0, "3: wlan0 inet 192.168.1.44/24 scope global wlan0", ""
        if args[:2] == ["iw", "dev"] and args[-1] == "info":
            return 0, "", ""
        if args[:2] == ["bluetoothctl", "show"]:
            return 0, "Powered: no", ""
        if args[:2] == ["bluetoothctl", "devices"]:
            return 0, "", ""
        if args[:2] == ["ss", "-ltn"]:
            return 0, "", ""
        if args[:2] == ["ps", "-eo"]:
            return 0, "", ""
        return 127, "", "not installed"

    monkeypatch.setattr(uplink, "run", fake_run)
    monkeypatch.setattr(uplink, "process_running", lambda _pattern: False)
    data = uplink.network_snapshot(tmp_path, sys_class_net=sys_net)

    assert data["wifi_connected"] is True
    assert data["wifi_ssid"] == "My Home WiFi"
    assert data["wifi_ip"] == "192.168.1.44"


def test_wifi_device_is_found_by_sysfs_even_with_nonstandard_name(tmp_path, monkeypatch):
    sys_net = tmp_path / "sys/class/net"
    _wireless_sysfs(sys_net, "radio0")

    def fake_run(args, timeout=4):
        if args[:4] == ["iw", "dev", "radio0", "link"]:
            return 0, "Not connected.", ""
        if args[:2] == ["wpa_cli", "-i"] or args[:2] == ["wpa_cli", "-i"]:
            return 127, "", ""
        if args[:3] == ["iwgetid", "-r", "radio0"]:
            return 0, "OfficeNet", ""
        if args[:2] == ["ip", "-o"]:
            return 0, "4: radio0 inet 10.0.0.8/24 scope global radio0", ""
        if args[:2] == ["bluetoothctl", "show"]:
            return 0, "Powered: no", ""
        if args[:2] == ["bluetoothctl", "devices"]:
            return 0, "", ""
        if args[:2] == ["ss", "-ltn"] or args[:2] == ["ps", "-eo"]:
            return 0, "", ""
        if args[:2] == ["iw", "dev"]:
            return 0, "", ""
        return 127, "", ""

    monkeypatch.setattr(uplink, "run", fake_run)
    monkeypatch.setattr(uplink, "process_running", lambda _pattern: False)
    data = uplink.network_snapshot(tmp_path, sys_class_net=sys_net)

    assert data["wifi_connected"] is True
    assert data["wifi_ssid"] == "OfficeNet"


def test_status_writer_publishes_complete_atomic_record(tmp_path):
    path = tmp_path / "uplink.status"
    uplink.write_status(path, _snapshot())
    fields = path.read_text(encoding="utf-8").strip().split("|")
    assert len(fields) == 19
    assert fields[0:3] == ["1", "LAB-WIFI", "192.0.2.4"]
    assert fields[8:14] == ["1", "0", "1", "1", "0", "1"]
    assert fields[14:] == ["1", "1", "Running", "3", "100.64.0.10"]
    assert not path.with_suffix(".tmp").exists()


def test_rt_install_discovery_requires_both_managed_entrypoints(tmp_path):
    rt = tmp_path / "RtTailscale"
    rt.mkdir(parents=True)
    (rt / "rt").write_text("#!/bin/sh\n")
    assert uplink.find_rt(tmp_path) is None
    (rt / "ts").write_text("#!/bin/sh\n")
    assert uplink.find_rt(tmp_path) == rt
