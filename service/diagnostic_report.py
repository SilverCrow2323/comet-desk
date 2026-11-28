#!/usr/bin/env python3
"""Build a bounded, redacted diagnostic report from Comet Desk's read-only probe."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_REPORT_BYTES = 256 * 1024
MAX_STRING_LENGTH = 1024
MAX_COLLECTION_ITEMS = 128
SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "serial",
    "macaddress",
    "uuid",
    "ssid",
    "hostname",
    "username",
    "account",
    "ipaddress",
    "authorization",
    "cookie",
    "privatekey",
)


class DiagnosticReportError(ValueError):
    """The diagnostic snapshot cannot be safely exported."""


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redact(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if key and _is_sensitive_key(key):
        return "[REDACTED]"
    if depth > 8:
        return "[DEPTH-LIMIT]"
    if isinstance(value, dict):
        result = {}
        for index, (child_key, child_value) in enumerate(value.items()):
            if index >= MAX_COLLECTION_ITEMS:
                result["_truncated"] = True
                break
            if not isinstance(child_key, str):
                raise DiagnosticReportError("diagnostic object keys must be strings")
            result[child_key] = _redact(child_value, key=child_key, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        result = [
            _redact(item, depth=depth + 1)
            for item in value[:MAX_COLLECTION_ITEMS]
        ]
        if len(value) > MAX_COLLECTION_ITEMS:
            result.append("[TRUNCATED]")
        return result
    if isinstance(value, str):
        clean = value.replace("\x00", "")
        if len(clean) > MAX_STRING_LENGTH:
            return clean[:MAX_STRING_LENGTH] + "[TRUNCATED]"
        return clean
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise DiagnosticReportError("diagnostic numbers must be finite")
        return value
    raise DiagnosticReportError(f"unsupported diagnostic value: {type(value).__name__}")


def build_diagnostic_report(
    snapshot: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a versioned report; never accept an unverified or mutating snapshot."""
    if not isinstance(snapshot, dict):
        raise DiagnosticReportError("probe snapshot must be an object")
    if snapshot.get("schema_version") != 1:
        raise DiagnosticReportError("unsupported device probe schema")
    if snapshot.get("probe") != "comet-device-probe" or snapshot.get("read_only") is not True:
        raise DiagnosticReportError("only the read-only Comet Desk probe can be exported")
    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    if not isinstance(stamp, str) or not stamp or len(stamp) > 64:
        raise DiagnosticReportError("generated_at must be a short non-empty timestamp")
    return {
        "report_schema_version": 1,
        "generated_at": stamp,
        "source": "comet-device-probe",
        "snapshot": _redact(snapshot),
    }


def _reject_symlink_components(path: str | Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        if current.is_symlink():
            raise DiagnosticReportError(f"report path contains a symbolic link: {current}")
    return absolute


def write_diagnostic_report(
    destination: str | Path,
    snapshot: dict[str, Any],
    *,
    overwrite: bool = False,
    generated_at: str | None = None,
) -> Path:
    """Atomically export JSON beside an existing parent directory."""
    target = _reject_symlink_components(destination)
    parent = target.parent
    if not parent.is_dir():
        raise DiagnosticReportError("report parent directory must already exist")
    if target.exists() and not overwrite:
        raise DiagnosticReportError("report already exists; pass overwrite=True to replace it")
    report = build_diagnostic_report(snapshot, generated_at=generated_at)
    payload = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > MAX_REPORT_BYTES:
        raise DiagnosticReportError("diagnostic report exceeds the size limit")

    fd, temporary_name = tempfile.mkstemp(prefix=".comet-report-", suffix=".tmp", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, target)
        else:
            # Hard-link creation is atomic and refuses to replace an existing target.
            os.link(temporary, target)
            temporary.unlink()
        return target
    except FileExistsError as exc:
        raise DiagnosticReportError("report already exists; pass overwrite=True to replace it") from exc
    except OSError as exc:
        raise DiagnosticReportError(f"cannot write diagnostic report: {exc}") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="existing directory destination, e.g. ./comet-report.json")
    parser.add_argument("--force", action="store_true", help="replace an existing report")
    args = parser.parse_args(argv)
    try:
        from service.device_probe import probe

        output = write_diagnostic_report(args.destination, probe(), overwrite=args.force)
    except DiagnosticReportError as exc:
        parser.exit(1, f"[comet-report] ERROR: {exc}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
