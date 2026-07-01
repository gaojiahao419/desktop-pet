from control_panel import (
    ACTION_BUTTONS,
    LOOP_MODE_OPTIONS,
    SCALE_DEFAULT_PERCENT,
    SCALE_MAX_PERCENT,
    SCALE_MIN_PERCENT,
    SPEED_DEFAULT_PERCENT,
    SPEED_MAX_PERCENT,
    SPEED_MIN_PERCENT,
    STATE_MATERIALS,
    control_panel_design_tokens,
    next_preview_frame_index,
    preview_frame_label,
    speed_float_to_percent,
    speed_percent_to_float,
    scale_float_to_percent,
    scale_percent_to_float,
)


def test_scale_slider_range_starts_at_zero_percent():
    assert SCALE_MIN_PERCENT == 0
    assert SCALE_DEFAULT_PERCENT == 100
    assert SCALE_MAX_PERCENT == 250


def test_scale_percent_conversion():
    assert scale_percent_to_float(125) == 1.25
    assert scale_percent_to_float(-10) == 0.0
    assert scale_percent_to_float(300) == 2.5
    assert scale_float_to_percent(1.25) == 125


def test_speed_slider_range_and_conversion():
    assert SPEED_MIN_PERCENT == 25
    assert SPEED_DEFAULT_PERCENT == 100
    assert SPEED_MAX_PERCENT == 300
    assert speed_percent_to_float(150) == 1.5
    assert speed_percent_to_float(10) == 0.25
    assert speed_percent_to_float(400) == 3.0
    assert speed_float_to_percent(1.5) == 150


def test_loop_mode_options_are_labeled_for_users():
    assert LOOP_MODE_OPTIONS == [
        ("循环播放", "loop"),
        ("单次定格", "once"),
    ]


def test_preview_frame_helpers_support_loop_and_once_modes():
    assert preview_frame_label(0, 10) == "当前帧：1 / 10"
    assert preview_frame_label(9, 10) == "当前帧：10 / 10"
    assert next_preview_frame_index(9, 10, "loop") == 0
    assert next_preview_frame_index(9, 10, "once") == 9
    assert next_preview_frame_index(2, 10, "once") == 3


def test_material_library_includes_sleep_action():
    states = [state for state, _title, _hint in STATE_MATERIALS]

    assert states == ["idle", "happy", "angry", "sleep"]


def test_action_buttons_include_sleep_and_exclude_walk():
    states = [state for _label, state, _object_name in ACTION_BUTTONS]

    assert "sleep" in states
    assert "walk" not in states
    assert states == ["idle", "happy", "angry", "sleep", "hide", "show"]


def test_control_panel_design_tokens_define_clear_visual_roles():
    tokens = control_panel_design_tokens()

    assert tokens["shell"] == "#0b0f10"
    assert tokens["panel"] == "#14201e"
    assert tokens["accent"] == "#f2763d"
    assert tokens["success"] == "#7ec8a4"
    assert tokens["danger"] == "#ff8b7b"
    assert tokens["secondary"] == "#84a59d"
    assert tokens["amber"] == "#f3b562"
    assert len({tokens["shell"], tokens["panel"], tokens["card"], tokens["accent"], tokens["success"]}) == 5
