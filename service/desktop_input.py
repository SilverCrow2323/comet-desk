#!/usr/bin/env python3
"""Comet Desk controller-to-desktop bridge for the muOS host.

Reads one explicitly identified evdev gamepad, grabs only that gamepad, and
emits a virtual keyboard/mouse through /dev/uinput. No pygame, evdev or other
third-party Python package is required on muOS.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import select
import signal
import struct
import sys
import time
from pathlib import Path
from typing import Iterable

EV_SYN, EV_KEY, EV_REL, EV_ABS = 0, 1, 2, 3
SYN_REPORT, SYN_DROPPED = 0, 3
REL_X, REL_Y, REL_HWHEEL, REL_WHEEL = 0, 1, 6, 8
ABS_X, ABS_Y, ABS_RX, ABS_RY, ABS_HAT0X, ABS_HAT0Y = 0, 1, 3, 4, 16, 17

BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST = 304, 305, 307, 308
BTN_TL, BTN_TR, BTN_SELECT, BTN_START = 310, 311, 314, 315
BTN_DPAD_UP, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT = 544, 545, 546, 547

KEY_ESC, KEY_TAB, KEY_ENTER, KEY_BACKSPACE = 1, 15, 28, 14
KEY_LEFTCTRL, KEY_LEFTALT, KEY_SPACE, KEY_LEFTMETA = 29, 56, 57, 125
KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_M = 103, 105, 106, 108, 50

UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
BUS_USB = 0x03
EVENT_STRUCT = struct.Struct("@llHHi")
EVENT_SIZE = EVENT_STRUCT.size

DEFAULT_CONFIG = {
    "schema_version": 1,
    "enabled": True,
    "device": "auto",
    "pointer_speed": 900,
    "scroll_speed": 9,
    "deadzone": 0.18,
    "acceleration": 1.65,
    "bindings": {
        "a": "enter",
        "b": "escape",
        "l1+a": "mouse_left",
        "l1+b": "mouse_right",
        "x": "backspace",
        "y": "tab",
        "r1+x": "alt_tab",
        "start": "super",
        "select": "comet_panel",
    },
}


class InputError(RuntimeError):
    pass


def _ioc(direction: int, kind: int, number: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (kind << 8) | number


def _ior(number: int, size: int) -> int:
    return _ioc(2, ord("E"), number, size)


def _eviocgbit(event_type: int, size: int) -> int:
    return _ior(0x20 + event_type, size)


def _bit_set(bits: bytes, code: int) -> bool:
    byte = code // 8
    return byte < len(bits) and bool(bits[byte] & (1 << (code % 8)))


def _normalise_axis(value: int, minimum: int, maximum: int) -> float:
    if maximum <= minimum:
        return 0.0
    centre = (minimum + maximum) / 2.0
    half = max(1.0, (maximum - minimum) / 2.0)
    return max(-1.0, min(1.0, (value - centre) / half))


def load_config(path: Path | None) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path and path.is_file():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InputError("desktop input configuration is invalid: {}".format(exc)) from exc
        if not isinstance(stored, dict):
            raise InputError("desktop input configuration must be a JSON object")
        for key in ("enabled", "device", "pointer_speed", "scroll_speed",
                    "deadzone", "acceleration"):
            if key in stored:
                config[key] = stored[key]
        if "bindings" in stored and isinstance(stored["bindings"], dict):
            config["bindings"].update(stored["bindings"])
    config["pointer_speed"] = max(200, min(2200, int(config["pointer_speed"])))
    config["scroll_speed"] = max(2, min(24, int(config["scroll_speed"])))
    config["deadzone"] = max(0.08, min(0.42, float(config["deadzone"])))
    config["acceleration"] = max(1.0, min(2.6, float(config["acceleration"])))
    return config


def write_default_config(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class ControllerMapper:
    """Pure input mapper; unit-tested without a handheld or /dev/uinput."""

    def __init__(self, config: dict | None = None,
                 axis_ranges: dict[int, tuple[int, int]] | None = None):
        self.config = load_config(None)
        if config:
            self.config.update(config)
        self.axis_ranges = axis_ranges or {}
        self.down: set[int] = set()
        self.axes = {ABS_X: 0.0, ABS_Y: 0.0, ABS_RX: 0.0, ABS_RY: 0.0}
        self.axis_fraction = {REL_X: 0.0, REL_Y: 0.0,
                              REL_WHEEL: 0.0, REL_HWHEEL: 0.0}
        self.held_actions: dict[int, str] = {}
        self.hat = {ABS_HAT0X: 0, ABS_HAT0Y: 0}
        self.dpad_keys: set[int] = set()

    @staticmethod
    def _key(code: int, value: int) -> list[tuple[int, int, int]]:
        return [(EV_KEY, code, value)]

    @staticmethod
    def _tap(code: int) -> list[tuple[int, int, int]]:
        return [(EV_KEY, code, 1), (EV_KEY, code, 0)]

    def _command(self, name: str, pressed: bool) -> list[tuple[int, int, int]]:
        value = 1 if pressed else 0
        if name == "enter":
            return self._key(KEY_ENTER, value)
        if name == "escape":
            return self._key(KEY_ESC, value)
        if name == "backspace":
            return self._key(KEY_BACKSPACE, value)
        if name == "tab":
            return self._key(KEY_TAB, value)
        if name == "space":
            return self._key(KEY_SPACE, value)
        if name == "mouse_left":
            return self._key(272, value)
        if name == "mouse_right":
            return self._key(273, value)
        if name == "super":
            return self._key(KEY_LEFTMETA, value)
        if name == "comet_panel":
            return self._key(KEY_M, value)
        if name == "alt_tab":
            return self._tap_combo(KEY_LEFTALT, KEY_TAB) if pressed else []
        if name == "ctrl_escape":
            return self._tap_combo(KEY_LEFTCTRL, KEY_ESC) if pressed else []
        return []

    def _tap_combo(self, modifier: int, key: int) -> list[tuple[int, int, int]]:
        return [(EV_KEY, modifier, 1), (EV_KEY, key, 1),
                (EV_KEY, key, 0), (EV_KEY, modifier, 0)]

    def _button_name(self, code: int) -> str | None:
        return {
            BTN_SOUTH: "a", BTN_EAST: "b", BTN_WEST: "x",
            BTN_NORTH: "y", BTN_TL: "l1", BTN_TR: "r1",
            BTN_START: "start", BTN_SELECT: "select",
        }.get(code)

    def _update_dpad(self) -> list[tuple[int, int, int]]:
        wanted = set()
        if self.hat[ABS_HAT0Y] < 0 or BTN_DPAD_UP in self.down:
            wanted.add(KEY_UP)
        if self.hat[ABS_HAT0Y] > 0 or BTN_DPAD_DOWN in self.down:
            wanted.add(KEY_DOWN)
        if self.hat[ABS_HAT0X] < 0 or BTN_DPAD_LEFT in self.down:
            wanted.add(KEY_LEFT)
        if self.hat[ABS_HAT0X] > 0 or BTN_DPAD_RIGHT in self.down:
            wanted.add(KEY_RIGHT)
        events = []
        for code in sorted(self.dpad_keys - wanted):
            events.extend(self._key(code, 0))
        for code in sorted(wanted - self.dpad_keys):
            events.extend(self._key(code, 1))
        self.dpad_keys = wanted
        return events

    def feed(self, event_type: int, code: int, value: int) -> list[tuple[int, int, int]]:
        """Convert one Linux input event to uinput output events."""
        if event_type == EV_ABS:
            if code in self.axes:
                minimum, maximum = self.axis_ranges.get(code, (-32768, 32767))
                self.axes[code] = _normalise_axis(value, minimum, maximum)
                return []
            if code in self.hat:
                self.hat[code] = max(-1, min(1, value))
                return self._update_dpad()
            return []
        if event_type != EV_KEY:
            return []
        if value == 2:  # ignore kernel key-repeat; desktop owns its own repeat
            return []
        if value not in (0, 1):
            return []

        name = self._button_name(code)
        if name is None:
            if code in (BTN_DPAD_UP, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT):
                if value:
                    self.down.add(code)
                else:
                    self.down.discard(code)
                return self._update_dpad()
            return []

        if value:
            self.down.add(code)
        else:
            self.down.discard(code)

        if name in ("l1", "r1"):
            return []

        if value:
            action_key = name
            if BTN_TL in self.down and name in ("a", "b"):
                action_key = "l1+" + name
            elif BTN_TR in self.down and name == "x":
                action_key = "r1+x"
            action = self.config.get("bindings", {}).get(action_key)
            if not action:
                return []
            self.held_actions[code] = action
            return self._command(action, True)

        action = self.held_actions.pop(code, None)
        return self._command(action, False) if action else []

    def _shape(self, value: float) -> float:
        magnitude = abs(value)
        deadzone = float(self.config["deadzone"])
        if magnitude <= deadzone:
            return 0.0
        scaled = (magnitude - deadzone) / (1.0 - deadzone)
        return (1.0 if value >= 0 else -1.0) * (scaled ** float(self.config["acceleration"]))

    def tick(self, dt: float) -> list[tuple[int, int, int]]:
        """Generate smooth relative pointer/scroll movement at the frame cadence."""
        dt = max(0.0, min(0.1, float(dt)))
        speed = float(self.config["pointer_speed"])
        scroll = float(self.config["scroll_speed"])
        events = []
        for output, axis in ((REL_X, ABS_X), (REL_Y, ABS_Y)):
            self.axis_fraction[output] += self._shape(self.axes[axis]) * speed * dt
            fraction = self.axis_fraction[output]
            amount = int(math.copysign(math.floor(abs(fraction) + 0.5), fraction)) if fraction else 0
            if amount:
                self.axis_fraction[output] -= amount
                events.append((EV_REL, output, amount))
        # Positive right-stick Y means down; Linux wheel positive means up.
        for output, axis, sign in (
            (REL_WHEEL, ABS_RY, -1.0), (REL_HWHEEL, ABS_RX, 1.0)
        ):
            self.axis_fraction[output] += self._shape(self.axes[axis]) * scroll * dt * sign
            fraction = self.axis_fraction[output]
            amount = int(math.copysign(math.floor(abs(fraction) + 0.5), fraction)) if fraction else 0
            if amount:
                self.axis_fraction[output] -= amount
                events.append((EV_REL, output, amount))
        return events

    def release_all(self) -> list[tuple[int, int, int]]:
        events = []
        for action in list(self.held_actions.values()):
            events.extend(self._command(action, False))
        self.held_actions.clear()
        for code in sorted(self.dpad_keys):
            events.extend(self._key(code, 0))
        self.dpad_keys.clear()
        self.down.clear()
        return events


def _device_info(fd: int) -> tuple[str, bytes, bytes]:
    name_buf = bytearray(256)
    fcntl.ioctl(fd, _ior(0x06, len(name_buf)), name_buf, True)
    name = bytes(name_buf).split(b"\0", 1)[0].decode("utf-8", "replace")
    key_bits = bytearray(96)
    abs_bits = bytearray(16)
    fcntl.ioctl(fd, _eviocgbit(EV_KEY, len(key_bits)), key_bits, True)
    fcntl.ioctl(fd, _eviocgbit(EV_ABS, len(abs_bits)), abs_bits, True)
    return name, bytes(key_bits), bytes(abs_bits)


def discover_controller(device: str = "auto") -> tuple[int, str, dict[int, tuple[int, int]]]:
    candidates = []
    paths = [device] if device != "auto" else sorted(
        str(Path("/dev/input") / name) for name in os.listdir("/dev/input")
        if name.startswith("event")
    ) if Path("/dev/input").is_dir() else []
    for path in paths:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            name, key_bits, abs_bits = _device_info(fd)
            is_pad = (
                _bit_set(key_bits, BTN_SOUTH)
                and _bit_set(key_bits, BTN_EAST)
                and _bit_set(abs_bits, ABS_X)
                and _bit_set(abs_bits, ABS_Y)
            )
            if not is_pad:
                os.close(fd)
                continue
            score = 0
            lowered = name.lower()
            if any(part in lowered for part in ("gamepad", "joystick", "controller", "retrogame")):
                score += 10
            if _bit_set(key_bits, BTN_TL) and _bit_set(key_bits, BTN_TR):
                score += 3
            candidates.append((score, path, fd, name))
        except OSError:
            continue
    if not candidates:
        raise InputError("no compatible evdev gamepad found (need BTN_SOUTH/EAST and ABS_X/Y)")
    candidates.sort(key=lambda row: (-row[0], row[1]))
    _, path, fd, name = candidates[0]
    ranges = {}
    for code in (ABS_X, ABS_Y, ABS_RX, ABS_RY):
        raw = bytearray(24)
        try:
            fcntl.ioctl(fd, _ior(0x40 + code, 24), raw, True)
            info = struct.unpack("iiiiii", raw)
            ranges[code] = (info[1], info[2])
        except OSError:
            ranges[code] = (-32768, 32767)
    try:
        fcntl.ioctl(fd, 0x40044590, struct.pack("i", 1))  # EVIOCGRAB
    except OSError as exc:
        os.close(fd)
        raise InputError("cannot exclusively claim {}: {}".format(path, exc)) from exc
    return fd, "{} // {}".format(path, name), ranges


class UInputDevice:
    def __init__(self, path: str = "/dev/uinput"):
        try:
            self.fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as exc:
            raise InputError("cannot open {}: {}".format(path, exc)) from exc
        self.created = False
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
            for code in (
                KEY_ESC, KEY_TAB, KEY_ENTER, KEY_BACKSPACE, KEY_LEFTCTRL,
                KEY_LEFTALT, KEY_SPACE, KEY_LEFTMETA, KEY_UP, KEY_DOWN,
                KEY_LEFT, KEY_RIGHT, KEY_M, 272, 273,
            ):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            for code in (REL_X, REL_Y, REL_HWHEEL, REL_WHEEL):
                fcntl.ioctl(self.fd, UI_SET_RELBIT, code)
            name = b"Comet Desk Virtual Keyboard Mouse"
            device_id = struct.pack("HHHH", BUS_USB, 0xCAFE, 0x0C07, 1)
            arrays = bytes(64 * 4 * 4)
            payload = name.ljust(80, b"\0") + device_id + struct.pack("I", 0) + arrays
            os.write(self.fd, payload)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
            self.created = True
            time.sleep(0.15)
        except Exception:
            os.close(self.fd)
            raise

    def emit(self, events: Iterable[tuple[int, int, int]]) -> None:
        rows = list(events)
        if not rows:
            return
        sec = int(time.time())
        usec = int((time.time() - sec) * 1_000_000)
        try:
            for event_type, code, value in rows:
                os.write(self.fd, EVENT_STRUCT.pack(sec, usec, event_type, code, value))
            os.write(self.fd, EVENT_STRUCT.pack(sec, usec, EV_SYN, SYN_REPORT, 0))
        except OSError as exc:
            raise InputError("uinput write failed: {}".format(exc)) from exc

    def close(self) -> None:
        if getattr(self, "fd", -1) < 0:
            return
        if self.created:
            try:
                fcntl.ioctl(self.fd, UI_DEV_DESTROY)
            except OSError:
                pass
        os.close(self.fd)
        self.fd = -1
        self.created = False


def write_status(app_dir: Path, state: str, detail: str = "") -> None:
    path = app_dir / "data" / "desktop-input.status"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text("{}|{}\n".format(state, detail.replace("|", "/")[:180]),
                         encoding="utf-8")
    os.replace(temporary, path)


def run(app_dir: Path, config_path: Path | None = None, device: str | None = None) -> int:
    config_path = config_path or app_dir / "data" / "desktop-input.json"
    write_default_config(config_path)
    config = load_config(config_path)
    if not config["enabled"]:
        write_status(app_dir, "DISABLED", "controller mouse bridge disabled in settings")
        return 0

    fd = -1
    uinput = None
    old_handlers = {}
    stopping = False

    def stop(_signum=None, _frame=None):
        nonlocal stopping
        stopping = True

    for signum in (signal.SIGTERM, signal.SIGINT):
        old_handlers[signum] = signal.signal(signum, stop)

    try:
        target = device or str(config.get("device", "auto"))
        fd, label, ranges = discover_controller(target)
        uinput = UInputDevice()
        mapper = ControllerMapper(config, ranges)
        write_status(app_dir, "READY", label)
        last = time.monotonic()
        while not stopping:
            readable, _, _ = select.select([fd], [], [], 0.012)
            now = time.monotonic()
            if readable:
                try:
                    payload = os.read(fd, EVENT_SIZE * 64)
                except BlockingIOError:
                    payload = b""
                size = len(payload) - (len(payload) % EVENT_SIZE)
                for offset in range(0, size, EVENT_SIZE):
                    _, _, event_type, code, value = EVENT_STRUCT.unpack_from(payload, offset)
                    if event_type == EV_SYN and code == SYN_DROPPED:
                        uinput.emit(mapper.release_all())
                        continue
                    uinput.emit(mapper.feed(event_type, code, value))
            dt = now - last
            last = now
            uinput.emit(mapper.tick(dt))
        uinput.emit(mapper.release_all())
        write_status(app_dir, "STOPPED", "desktop controller bridge stopped")
        return 0
    except (OSError, InputError) as exc:
        write_status(app_dir, "UNAVAILABLE", str(exc))
        print("[comet-input] {}".format(exc), file=sys.stderr)
        return 1
    finally:
        if fd >= 0:
            try:
                fcntl.ioctl(fd, 0x40044590, struct.pack("i", 0))
            except OSError:
                pass
            os.close(fd)
        if uinput is not None:
            uinput.close()
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", default=os.environ.get("COMET_DESK_APP_DIR", ""))
    parser.add_argument("--config", default="")
    parser.add_argument("--device", default="")
    args = parser.parse_args()
    if not args.app_dir:
        parser.error("--app-dir or COMET_DESK_APP_DIR is required")
    return run(Path(args.app_dir), Path(args.config) if args.config else None,
               args.device or None)


if __name__ == "__main__":
    raise SystemExit(main())
