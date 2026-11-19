from __future__ import annotations

import json

import service.desktop_input as bridge


def config():
    return bridge.load_config(None)


def test_default_mapping_matches_comet_desktop_recommendation():
    cfg = config()
    assert cfg["bindings"]["a"] == "enter"
    assert cfg["bindings"]["b"] == "escape"
    assert cfg["bindings"]["l1+a"] == "mouse_left"
    assert cfg["bindings"]["l1+b"] == "mouse_right"
    assert cfg["pointer_speed"] == 900
    assert cfg["scroll_speed"] == 9


def test_a_and_b_send_enter_and_escape_when_l1_is_not_held():
    mapper = bridge.ControllerMapper(config())
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_SOUTH, 1) == [
        (bridge.EV_KEY, bridge.KEY_ENTER, 1)
    ]
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_SOUTH, 0) == [
        (bridge.EV_KEY, bridge.KEY_ENTER, 0)
    ]
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_EAST, 1) == [
        (bridge.EV_KEY, bridge.KEY_ESC, 1)
    ]
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_EAST, 0) == [
        (bridge.EV_KEY, bridge.KEY_ESC, 0)
    ]


def test_l1_plus_a_and_b_are_mouse_clicks_without_keyboard_activation():
    mapper = bridge.ControllerMapper(config())
    mapper.feed(bridge.EV_KEY, bridge.BTN_TL, 1)
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_SOUTH, 1) == [
        (bridge.EV_KEY, 272, 1)
    ]
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_SOUTH, 0) == [
        (bridge.EV_KEY, 272, 0)
    ]
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_EAST, 1) == [
        (bridge.EV_KEY, 273, 1)
    ]
    assert mapper.feed(bridge.EV_KEY, bridge.BTN_EAST, 0) == [
        (bridge.EV_KEY, 273, 0)
    ]


def test_dpad_hat_emits_key_edges_only():
    mapper = bridge.ControllerMapper(config())
    assert mapper.feed(bridge.EV_ABS, bridge.ABS_HAT0X, -1) == [
        (bridge.EV_KEY, bridge.KEY_LEFT, 1)
    ]
    assert mapper.feed(bridge.EV_ABS, bridge.ABS_HAT0Y, -1) == [
        (bridge.EV_KEY, bridge.KEY_LEFT, 1),
        (bridge.EV_KEY, bridge.KEY_UP, 1),
    ]
    assert mapper.feed(bridge.EV_ABS, bridge.ABS_HAT0X, 0) == [
        (bridge.EV_KEY, bridge.KEY_LEFT, 0)
    ]
    assert mapper.feed(bridge.EV_ABS, bridge.ABS_HAT0Y, 0) == [
        (bridge.EV_KEY, bridge.KEY_UP, 0)
    ]


def test_left_stick_moves_pointer_with_deadzone_and_smooth_accumulator():
    mapper = bridge.ControllerMapper(config(), {
        bridge.ABS_X: (-100, 100), bridge.ABS_Y: (-100, 100)
    })
    mapper.feed(bridge.EV_ABS, bridge.ABS_X, 0)
    assert mapper.tick(1 / 60) == []
    mapper.feed(bridge.EV_ABS, bridge.ABS_X, 100)
    events = mapper.tick(1 / 60)
    assert events
    assert events[0][0:2] == (bridge.EV_REL, bridge.REL_X)
    assert events[0][2] > 0


def test_right_stick_scrolls_and_uses_expected_direction():
    mapper = bridge.ControllerMapper(config(), {
        bridge.ABS_RY: (-100, 100)
    })
    mapper.feed(bridge.EV_ABS, bridge.ABS_RY, 100)
    down = mapper.tick(0.1)
    assert down == [(bridge.EV_REL, bridge.REL_WHEEL, -1)]
    mapper.feed(bridge.EV_ABS, bridge.ABS_RY, -100)
    up = mapper.tick(0.1)
    assert up == [(bridge.EV_REL, bridge.REL_WHEEL, 1)]


def test_config_is_clamped_and_default_file_is_not_overwritten(tmp_path):
    path = tmp_path / "data" / "desktop-input.json"
    bridge.write_default_config(path)
    original = path.read_text()
    path.write_text(json.dumps({
        "enabled": True, "pointer_speed": 9000, "scroll_speed": 0,
        "deadzone": 0.01, "acceleration": 9.0
    }))
    result = bridge.load_config(path)
    assert result["pointer_speed"] == 2200
    assert result["scroll_speed"] == 2
    assert result["deadzone"] == 0.08
    assert result["acceleration"] == 2.6
    bridge.write_default_config(path)
    assert path.read_text() != original  # existing user settings are preserved
    assert json.loads(path.read_text())["pointer_speed"] == 9000
