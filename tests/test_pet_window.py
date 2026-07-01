import pet_window
from PyQt5.QtCore import QPoint
from video_pet_source import playback_interval_ms


class FakeVideoSource:
    def __init__(self, fps=30.0):
        self.fps = fps

    def frame_interval_ms(self, playback_speed=1.0):
        return playback_interval_ms(self.fps, playback_speed=playback_speed)


def test_select_video_source_prefers_source_bound_to_active_state():
    fallback = FakeVideoSource()
    idle_source = FakeVideoSource()
    happy_source = FakeVideoSource()

    source = pet_window.select_video_source_for_state(
        "happy",
        {"idle": idle_source, "happy": happy_source},
        fallback,
    )

    assert source is happy_source


def test_select_video_source_falls_back_to_default_source():
    fallback = FakeVideoSource()
    idle_source = FakeVideoSource()

    source = pet_window.select_video_source_for_state(
        "sleep",
        {"idle": idle_source},
        fallback,
    )

    assert source is fallback


def test_scaled_dimensions_preserve_video_aspect_ratio():
    assert pet_window.scaled_dimensions((800, 600), 1.0) == (800, 600)
    assert pet_window.scaled_dimensions((800, 600), 0.5) == (400, 300)
    assert pet_window.scaled_dimensions((800, 600), 0.0) == (1, 1)


def test_display_dimension_allows_zero_scale_without_zero_sized_window():
    assert pet_window.display_dimension(220, 0.0) == 1
    assert pet_window.display_dimension(220, 0.5) == 110


def test_select_scale_for_state_uses_per_state_scale():
    state_scales = {"idle": 0.8, "happy": 1.4}

    assert pet_window.select_scale_for_state("idle", state_scales, 1.0) == 0.8
    assert pet_window.select_scale_for_state("happy", state_scales, 1.0) == 1.4
    assert pet_window.select_scale_for_state("sleep", state_scales, 1.0) == 1.0


def test_select_playback_speed_and_loop_mode_for_state():
    speeds = {"idle": 0.75, "happy": 1.5}
    loop_modes = {"idle": "loop", "happy": "once", "bad": "invalid"}

    assert pet_window.select_playback_speed_for_state("idle", speeds, 1.0) == 0.75
    assert pet_window.select_playback_speed_for_state("missing", speeds, 1.0) == 1.0
    assert pet_window.select_loop_mode_for_state("happy", loop_modes, "loop") == "once"
    assert pet_window.select_loop_mode_for_state("bad", loop_modes, "loop") == "loop"


def test_timer_interval_uses_video_fps_when_source_is_active():
    assert pet_window.timer_interval_for_source(FakeVideoSource(30.0)) == 33
    assert pet_window.timer_interval_for_source(FakeVideoSource(24.0)) == 42
    assert pet_window.timer_interval_for_source(FakeVideoSource(30.0), playback_speed=2.0) == 17


def test_timer_interval_uses_default_for_drawn_pet():
    assert pet_window.timer_interval_for_source(None) == 60


def test_right_click_menu_uses_fade_and_slide_animation():
    config = pet_window.right_click_menu_animation_config()

    assert config["duration_ms"] == 180
    assert config["start_opacity"] == 0.0
    assert config["end_opacity"] == 1.0
    assert config["slide_offset_y"] == 12


def test_right_click_menu_design_tokens_define_action_and_dialogue_roles():
    tokens = pet_window.right_click_menu_design_tokens()

    assert tokens["panel"] == "#f8fbff"
    assert tokens["line"] == "#bfdbfe"
    assert tokens["button"] == "#ffffff"
    assert tokens["action_accent"] == "#2563eb"
    assert tokens["dialogue_accent"] == "#2563eb"
    assert tokens["utility_accent"] == "#2563eb"
    assert tokens["text"] == "#0f172a"


def test_right_click_menu_position_stays_inside_screen():
    position = pet_window.clamp_popup_position(
        point=(790, 590),
        popup_size=(220, 330),
        screen_rect=(0, 0, 800, 600),
    )

    assert position == (568, 258)


def test_right_click_menu_anchor_tracks_pet_window_movement():
    anchor = pet_window.popup_anchor_offset(pet_position=(1200, 620), popup_position=(1280, 700))

    assert anchor == (80, 80)
    assert pet_window.popup_position_from_anchor(pet_position=(1220, 650), anchor_offset=anchor) == (1300, 730)


def test_chat_dialog_position_follows_pet_and_flips_when_needed():
    assert pet_window.chat_dialog_position_for_pet(
        pet_position=(100, 200),
        pet_size=(220, 220),
        dialog_size=(560, 640),
        screen_rect=(0, 0, 1600, 1000),
    ) == (336, 16)

    assert pet_window.chat_dialog_position_for_pet(
        pet_position=(1300, 200),
        pet_size=(220, 220),
        dialog_size=(560, 640),
        screen_rect=(0, 0, 1600, 1000),
    ) == (724, 16)


def test_second_right_click_closes_existing_menu_without_creating_duplicate(monkeypatch):
    created_menus = []

    class ExistingMenu:
        def __init__(self):
            self.closed = False

        def isVisible(self):
            return True

        def close(self):
            self.closed = True

    class FakeMenu:
        def __init__(self, *_args):
            created_menus.append(self)

    class WindowStub:
        def __init__(self):
            self._right_click_menu = ExistingMenu()
            self._right_click_menu_anchor = (0, 0)

        def _menu_state_action(self, state):
            raise AssertionError(state)

        def _menu_reply(self, action):
            raise AssertionError(action)

    window = WindowStub()
    monkeypatch.setattr(pet_window, "AnimatedRightClickMenu", FakeMenu)

    pet_window.PetWindow._show_dialogue_menu(window, QPoint(20, 20))

    assert window._right_click_menu is None
    assert window._right_click_menu_anchor is None
    assert created_menus == []


def test_right_click_state_actions_match_available_control_actions():
    states = [state for _label, state in pet_window.RIGHT_CLICK_STATE_ACTIONS]

    assert states == []


def test_right_click_dialogue_actions_are_dialogue_only():
    actions = [action for _label, action in pet_window.RIGHT_CLICK_DIALOGUE_ACTIONS]

    assert actions == []


def test_right_click_utility_actions_include_open_control_panel():
    actions = [action for _label, action in pet_window.RIGHT_CLICK_UTILITY_ACTIONS]

    assert actions == ["open_chat", "open_control_panel"]


def test_menu_reply_does_not_write_chat_to_terminal(capsys):
    class DialogueStub:
        def reply_for_menu(self, action, current_state):
            return f"reply for {action} in {current_state}"

    class AnimatorStub:
        state = "happy"

    class WindowStub:
        dialogue = DialogueStub()
        animator = AnimatorStub()
        spoken = None

        def say(self, text, preserve_state=True):
            self.spoken = (text, preserve_state)

    window = WindowStub()

    pet_window.PetWindow._menu_reply(window, "greeting")

    assert capsys.readouterr().out == ""
    assert window.spoken == ("reply for greeting in happy", True)


def test_open_chat_utility_action_opens_chat_dialog():
    class WindowStub:
        chat_opened = False

        def _show_chat_dialog(self):
            self.chat_opened = True

    window = WindowStub()

    pet_window.PetWindow._menu_utility_action(window, "open_chat")

    assert window.chat_opened is True


def test_receive_chat_reply_appends_to_open_chat_dialog():
    class ChatDialogStub:
        received = None

        def append_assistant_message(self, text):
            self.received = text

    class WindowStub:
        _chat_dialog = ChatDialogStub()

    window = WindowStub()

    pet_window.PetWindow.receive_chat_reply(window, "你好呀")

    assert window._chat_dialog.received == "你好呀"
