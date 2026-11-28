from pathlib import Path

import pytest

from service.diagnostic_report import (
    DiagnosticReportError,
    build_diagnostic_report,
    write_diagnostic_report,
)


def snapshot():
    return {
        "schema_version": 1,
        "probe": "comet-device-probe",
        "read_only": True,
        "device": {
            "model": "Anbernic RG35XX H",
            "serial_number": "DEVICE-SERIAL",
            "mac_address": "00:11:22:33:44:55",
        },
        "network": {
            "ip_address": "192.0.2.10",
            "access_token": "do-not-export",
        },
        "storage": [{"mount_point": "/mnt/mmc", "available_bytes": 1024}],
    }


def test_report_redacts_identifiers_and_credentials_recursively():
    report = build_diagnostic_report(snapshot(), generated_at="2026-11-28T15:00:00Z")
    device = report["snapshot"]["device"]
    network = report["snapshot"]["network"]

    assert device["model"] == "Anbernic RG35XX H"
    assert device["serial_number"] == "[REDACTED]"
    assert device["mac_address"] == "[REDACTED]"
    assert network["ip_address"] == "[REDACTED]"
    assert network["access_token"] == "[REDACTED]"


def test_report_refuses_non_read_only_or_unknown_probe_data():
    invalid = snapshot()
    invalid["read_only"] = False
    with pytest.raises(DiagnosticReportError, match="read-only"):
        build_diagnostic_report(invalid)

    invalid = snapshot()
    invalid["schema_version"] = 2
    with pytest.raises(DiagnosticReportError, match="schema"):
        build_diagnostic_report(invalid)


def test_report_export_is_atomic_and_does_not_overwrite_by_default(tmp_path):
    destination = tmp_path / "comet-report.json"
    written = write_diagnostic_report(
        destination,
        snapshot(),
        generated_at="2026-11-28T15:00:00Z",
    )
    assert written == destination
    first = destination.read_text(encoding="utf-8")
    assert "DEVICE-SERIAL" not in first
    assert "[REDACTED]" in first

    with pytest.raises(DiagnosticReportError, match="already exists"):
        write_diagnostic_report(destination, snapshot())

    write_diagnostic_report(destination, snapshot(), overwrite=True)
    assert destination.exists()


def test_report_export_rejects_symlinked_destination_ancestor(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)

    with pytest.raises(DiagnosticReportError, match="symbolic link"):
        write_diagnostic_report(alias / "report.json", snapshot())

    assert not (real / "report.json").exists()
