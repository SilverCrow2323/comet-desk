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
    app = tmp_path / "application"
    rt = app / "RtTailscale"
    rt.mkdir(parents=True)
    (rt / "rt").write_text("#!/bin/sh\n")
    assert uplink.find_rt(tmp_path) is None
    (rt / "ts").write_text("#!/bin/sh\n")
    assert uplink.find_rt(tmp_path) == rt
