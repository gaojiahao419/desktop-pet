from pathlib import Path

from main import STATE_LABELS


def test_main_does_not_start_shell_command_console():
    source = Path("main.py").read_text(encoding="utf-8")

    assert "ConsoleBridge" not in source
    assert "parse_command" not in source


def test_main_supported_material_states_include_sleep():
    assert list(STATE_LABELS) == ["idle", "happy", "angry", "sleep"]


def test_main_wires_new_material_controls_and_panel_shortcut():
    source = Path("main.py").read_text(encoding="utf-8")

    assert "api_signals.state_playback_speed_requested.connect(set_state_playback_speed)" in source
    assert "api_signals.state_loop_mode_requested.connect(set_state_loop_mode)" in source
    assert "window.control_panel_requested.connect(show_control_panel)" in source


def test_main_uses_local_http_and_electron_control_panel():
    source = Path("main.py").read_text(encoding="utf-8")

    assert "from control_api import ControlApiServer, ControlApiSignals, ControlApiStateStore" in source
    assert "from electron_control import ElectronControlLauncher" in source
    assert "ControlPanelWindow" not in source
    assert "api_server.start()" in source
    assert "control_launcher.show(api_server.url)" in source


def test_main_debounces_slider_setting_saves():
    source = Path("main.py").read_text(encoding="utf-8")

    assert "settings_save_timer = QTimer(app)" in source
    assert "settings_save_timer.start(350)" in source
    assert "app.aboutToQuit.connect(save_current_settings)" in source
    assert "schedule_settings_save()" in source
