#!/usr/bin/env python3
"""Comet-managed Debian application registry.

Only installed desktop entries whose executable resolves inside the selected
Debian rootfs are exposed. Launch commands are argv arrays, never shell text.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desktop_environment as desktop

APP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,95}$")
SHELLS = {"sh", "bash", "dash", "zsh", "fish", "ksh", "csh", "tcsh"}
LAUNCH_WRAPPERS = {"env", "sudo", "pkexec", "su", "doas"}
SEARCH_DIRS = (
    Path("usr/share/applications"),
    Path("usr/local/share/applications"),
    Path("root/.local/share/applications"),
)
EXEC_DIRS = (
    Path("usr/local/bin"),
    Path("usr/bin"),
    Path("usr/sbin"),
    Path("bin"),
    Path("sbin"),
)
FIELD_CODES = ("%f", "%F", "%u", "%U", "%i", "%c", "%k")
CATEGORY_MAP = (
    ("Development", "DEVELOPMENT"),
    ("Game", "GAMES"),
    ("Graphics", "GRAPHICS"),
    ("AudioVideo", "MEDIA"),
    ("Audio", "MEDIA"),
    ("Video", "MEDIA"),
    ("Network", "NETWORK"),
    ("Office", "OFFICE"),
    ("Settings", "SYSTEM"),
    ("System", "SYSTEM"),
    ("Utility", "UTILITIES"),
    ("FileManager", "FILES"),
)


class RegistryError(RuntimeError):
    pass


def clean(value: str, limit: int = 180) -> str:
    return str(value or "").replace("|", "/").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _unescape(value: str) -> str:
    return (value.replace("\\s", " ").replace("\\n", "\n")
            .replace("\\t", "\t").replace("\\\\", "\\"))


def resolve_executable(root: Path, command: str) -> Path | None:
    candidate = Path(command)
    candidates = [root / command.lstrip("/")] if candidate.is_absolute() else [
        root / directory / command for directory in EXEC_DIRS
    ]
    for item in candidates:
        try:
            if not item.exists():
                continue
            resolved = item.resolve(strict=True)
            resolved.relative_to(root.resolve(strict=True))
            if resolved.is_file() and os.access(resolved, os.X_OK):
                return resolved
        except (OSError, ValueError):
            continue
    return None


def parse_desktop_entry(path: Path, root: Path) -> dict | None:
    """Parse one Desktop Entry and resolve its Exec target inside root."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    values: dict[str, str] = {}
    active = False
    for line in raw.splitlines():
        line = line.strip()
        if line == "[Desktop Entry]":
            active = True
            continue
        if line.startswith("[") and line.endswith("]"):
            if active:
                break
            continue
        if not active or not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if "[" not in key:
            values[key] = _unescape(value)

    if values.get("Type", "Application") != "Application":
        return None
    if values.get("Hidden", "").lower() == "true" or values.get("NoDisplay", "").lower() == "true":
        return None
    if values.get("Terminal", "").lower() == "true":
        return None

    name = clean(values.get("Name", path.stem), 72)
    exec_text = values.get("Exec", "").strip()
    if not name or not exec_text:
        return None
    try:
        tokens = shlex.split(exec_text, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None

    argv: list[str] = []
    for token in tokens:
        if token in FIELD_CODES:
            continue
        token = token.replace("%%", "\0")
        for code in FIELD_CODES:
            token = token.replace(code, "")
        token = token.replace("\0", "%")
        if "%" in token:
            return None
        if token:
            argv.append(token)
    if not argv or Path(argv[0]).name in SHELLS | LAUNCH_WRAPPERS:
        return None

    executable = resolve_executable(root, argv[0])
    if executable is None:
        return None
    argv[0] = "/" + executable.relative_to(root).as_posix()

    try_exec = values.get("TryExec", "").strip()
    if try_exec and resolve_executable(root, try_exec) is None:
        return None

    stable_id = re.sub(r"[^a-z0-9._+-]+", "-", path.stem.lower()).strip(".-")
    if not stable_id:
        return None
    if not APP_ID_RE.fullmatch(stable_id):
        return None

    categories = set(values.get("Categories", "").split(";"))
    category = next((label for marker, label in CATEGORY_MAP if marker in categories), "OTHER")
    return {
        "id": stable_id,
        "name": name,
        "category": category,
        "icon": clean(values.get("Icon", "application-x-executable"), 64),
        "exec": argv,
        "desktop_file": path.relative_to(root).as_posix(),
        "comment": clean(values.get("Comment", ""), 140),
    }


def discover_applications(root: Path, limit: int = 1200) -> list[dict]:
    root = root.resolve(strict=True)
    found: dict[str, dict] = {}
    scanned = 0
    for relative_dir in SEARCH_DIRS:
        directory = root / relative_dir
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in sorted(directory.rglob("*.desktop")):
            if scanned >= limit:
                break
            scanned += 1
            if path.is_symlink() or not path.is_file():
                continue
            try:
                path.resolve(strict=True).relative_to(root)
            except (OSError, ValueError):
                continue
            entry = parse_desktop_entry(path, root)
            if entry and entry["id"] not in found:
                found[entry["id"]] = entry
        if scanned >= limit:
            break
    return sorted(found.values(), key=lambda item: (item["category"], item["name"].casefold(), item["id"]))


def find_application(root: Path, app_id: str) -> dict | None:
    if not APP_ID_RE.fullmatch(app_id or ""):
        raise RegistryError("invalid Comet application id")
    return next((entry for entry in discover_applications(root) if entry["id"] == app_id), None)


def write_status(app_dir: Path, state: str, message: str) -> None:
    path = app_dir / "data" / "app-registry.status"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write("{}|{}\n".format(clean(state, 24), clean(message, 180)))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_catalog(app_dir: Path, rows: list[dict]) -> None:
    path = app_dir / "data" / "app-catalog.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write("META|{}\n".format(len(rows)))
        for row in rows:
            stream.write("APP|{}|{}|{}|{}|{}\n".format(
                clean(row["id"], 96), clean(row["name"], 72),
                clean(row["category"], 24), clean(row["icon"], 64),
                clean(row["exec"][0], 96),
            ))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def catalog(slot: str, app_dir: Path) -> int:
    if os.geteuid() != 0:
        raise RegistryError("Comet's muOS application runner must provide root privileges")
    if slot not in desktop.SLOTS:
        raise RegistryError("unknown storage slot")
    mounted, writable = desktop.mounted_slot(slot)
    if not mounted or not writable:
        raise RegistryError(slot.upper() + " is not mounted writable")
    root = desktop.SLOTS[slot].resolve(strict=True)
    if root != desktop.SLOTS[slot] or not root.is_dir():
        raise RegistryError("selected storage root is not a trusted mount")
    stage = desktop.safe_staging_directory(root)
    image, marker = stage / "debian.img", stage / ".comet-debian-ready"
    if image.is_symlink() or marker.is_symlink() or not image.is_file():
        raise RegistryError("Debian Trixie image is not ready")
    try:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError("install Debian Trixie before opening APP DECK") from exc
    if manifest.get("distribution") != "debian" or manifest.get("codename") != "trixie":
        raise RegistryError("selected image is not a Comet Debian Trixie rootfs")

    mountpoint = app_dir / "data" / "desktop-mnt"
    log_path = app_dir / "data" / "app-registry.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        manager = desktop.ImageMount(image, mountpoint, log)
        write_status(app_dir, "SCANNING", "Inspecting installed Debian applications")
        try:
            manager.mount_image()
            rows = discover_applications(mountpoint)
            write_catalog(app_dir, rows)
            write_status(app_dir, "READY", "{} applications ready in APP DECK".format(len(rows)))
            desktop.write_status(app_dir, "READY", 100,
                                 "{} Debian applications discovered".format(len(rows)),
                                 str(image), manifest.get("selected_profile", ""))
            return 0
        finally:
            if not manager.cleanup():
                write_status(app_dir, "CLEANUP_REQUIRED",
                             "Application scan left a mount requiring cleanup")
                desktop.write_status(app_dir, "CLEANUP_REQUIRED", 0,
                                     "Application registry scan left a mount requiring cleanup",
                                     str(image))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("catalog",))
    parser.add_argument("--slot", required=True, choices=sorted(desktop.SLOTS))
    parser.add_argument("--app-dir", default=os.environ.get("COMET_DESK_APP_DIR", ""))
    args = parser.parse_args()
    if not args.app_dir:
        print("COMET_DESK_APP_DIR is required", file=sys.stderr)
        return 2
    app_dir = Path(args.app_dir).resolve()
    app_dir.joinpath("data").mkdir(parents=True, exist_ok=True)
    lock_path = app_dir / "data" / "debian-system.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            write_status(app_dir, "BUSY", "Another Debian operation is running")
            desktop.write_status(app_dir, "BUSY", 0, "Another Debian operation is running")
            return 1
        try:
            return catalog(args.slot, app_dir)
        except (RegistryError, desktop.SetupError, OSError, subprocess.SubprocessError) as exc:
            write_status(app_dir, "FAILED", str(exc))
            desktop.write_status(app_dir, "FAILED", 0, str(exc))
            print("[app-registry] ERROR: {}".format(exc), file=sys.stderr)
            return 1
        finally:
            try:
                fcntl.flock(lock, fcntl.LOCK_UN)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
