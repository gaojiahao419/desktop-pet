import sys
from pathlib import Path
from threading import Thread

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

from control_api import ControlApiServer, ControlApiSignals, ControlApiStateStore
from dialogue import LocalDialogue
from pet_ai_client import PetAiClient
from electron_control import ElectronControlLauncher
from pet_animator import PetAnimator
from pet_settings import SETTINGS_PATH, PetSettings, load_settings, save_settings
from pet_window import PetWindow
from video_pet_source import VideoPetSource


STATE_LABELS = {
    "idle": "待机动作",
    "happy": "高兴动作",
    "angry": "生气动作",
    "sleep": "睡觉动作",
}


class VideoLoadSignals(QObject):
    state_loaded = pyqtSignal(str, str, object, bool)
    state_failed = pyqtSignal(str, str, str)

class AiChatSignals(QObject):
    reply_ready = pyqtSignal(str)

def main() -> int:
    app = QApplication(sys.argv)
    settings = load_settings()
    state_material_paths = {
        state: path for state, path in settings.state_materials.items() if state in STATE_LABELS
    }
    state_scales = {state: scale for state, scale in settings.state_scales.items() if state in STATE_LABELS}
    for state in STATE_LABELS:
        state_scales.setdefault(state, settings.scale)
    state_playback_speeds = {
        state: speed for state, speed in settings.state_playback_speeds.items() if state in STATE_LABELS
    }
    for state in STATE_LABELS:
        state_playback_speeds.setdefault(state, 1.0)
    state_loop_modes = {
        state: loop_mode for state, loop_mode in settings.state_loop_modes.items() if state in STATE_LABELS
    }
    for state in STATE_LABELS:
        state_loop_modes.setdefault(state, "loop")
    dialogue = LocalDialogue()
    ai_client = PetAiClient()
    animator = PetAnimator()
    window = PetWindow(animator, dialogue)
    window.set_scale(settings.scale)
    window.set_state_scales(state_scales)
    window.set_state_playback_speeds(state_playback_speeds)
    window.set_state_loop_modes(state_loop_modes)
    window.show()

    api_store = ControlApiStateStore()
    api_store.apply_settings(
        settings.scale,
        settings.black_background_transparent,
        state_material_paths,
        state_scales,
        state_playback_speeds,
        state_loop_modes,
    )
    api_signals = ControlApiSignals()
    api_server = ControlApiServer(api_store, api_signals)
    api_server.start()
    control_launcher = ElectronControlLauncher()

    loader_signals = VideoLoadSignals()
    chat_signals = AiChatSignals()
    loader_threads = []
    chat_threads = []
    preview_timer = QTimer(app)
    settings_save_timer = QTimer(app)
    settings_save_timer.setSingleShot(True)

    def apply_state(name: str) -> None:
        if name == "hide":
            window.hide_pet()
            return
        if name == "show":
            window.show_pet()
            return
        window.set_state(name)
        source = window.video_source_for_state(name)
        if source is not None:
            api_store.set_preview_source(source, name)

    def show_control_panel() -> None:
        try:
            control_launcher.show(api_server.url)
        except FileNotFoundError as exc:
            api_store.set_status(f"{exc}，请先运行 npm install")

    def save_current_settings() -> None:
        save_settings(
            SETTINGS_PATH,
            PetSettings(
                scale=settings.scale,
                black_background_transparent=api_store.black_background_transparent,
                state_materials=state_material_paths.copy(),
                state_scales=state_scales.copy(),

                state_playback_speeds=state_playback_speeds.copy(),
                state_loop_modes=state_loop_modes.copy(),
            ),
        )

    settings_save_timer.timeout.connect(save_current_settings)
    app.aboutToQuit.connect(save_current_settings)
    app.aboutToQuit.connect(api_server.stop)
    app.aboutToQuit.connect(control_launcher.stop)

    def schedule_settings_save() -> None:
        settings_save_timer.start(350)

    def say_text(text: str) -> None:
        if text:
            window.say(text)

    def chat_text(text: str) -> None:
        if not text:
            return

        window.say("我想一下。")

        def ask_ai() -> None:
            try:
                reply = ai_client.reply(text)
            except Exception:
                reply = dialogue.reply_for_text(text)
            chat_signals.reply_ready.emit(reply)

        thread = Thread(target=ask_ai, daemon=True)
        chat_threads.append(thread)
        thread.start()

    def load_state_video(
        state: str,
        path: str,
        black_background_transparent: bool,
        activate: bool = True,
    ) -> None:
        def load() -> None:
            try:
                source = VideoPetSource.from_path(
                    path,
                    black_background_transparent=black_background_transparent,
                )
            except Exception as exc:
                loader_signals.state_failed.emit(state, path, str(exc))
                return
            loader_signals.state_loaded.emit(state, path, source, activate)

        thread = Thread(target=load, daemon=True)
        loader_threads.append(thread)
        thread.start()

    def on_state_video_loaded(state: str, path: str, source: VideoPetSource, activate: bool) -> None:
        window.set_state_video_source(state, source)
        if activate:
            window.set_state(state)
        state_material_paths[state] = path
        api_store.set_state_material_loaded(state, path, source.has_transparency)
        api_store.set_preview_source(source, state)
        if api_store.preview_playing():
            preview_timer.start(api_store.preview_interval_ms())
        save_current_settings()

    def on_state_video_failed(state: str, path: str, error: str) -> None:
        api_store.set_state_material_failed(state, path, error)

    def reset_state_video(state: str) -> None:
        window.clear_state_video_source(state)
        state_material_paths.pop(state, None)
        api_store.set_preview_message("上传素材后显示首帧预览")
        save_current_settings()

    def set_state_scale(state: str, scale: float) -> None:
        state_scales[state] = scale
        window.set_state_scale(state, scale)
        schedule_settings_save()

    def set_state_playback_speed(state: str, speed: float) -> None:
        state_playback_speeds[state] = speed
        window.set_state_playback_speed(state, speed)
        if api_store.preview_playing():
            preview_timer.start(api_store.preview_interval_ms())
        schedule_settings_save()

    def set_state_loop_mode(state: str, loop_mode: str) -> None:
        state_loop_modes[state] = loop_mode
        window.set_state_loop_mode(state, loop_mode)
        save_current_settings()

    def set_black_background_transparent(enabled: bool) -> None:
        api_store.set_black_background_transparent(enabled)
        save_current_settings()
        for state, path in state_material_paths.copy().items():
            if Path(path).exists():
                api_store.set_state_material_loading(state, path)
                load_state_video(state, path, enabled, activate=False)

    def play_preview() -> None:
        if api_store.preview_playing():
            preview_timer.start(api_store.preview_interval_ms())

    def pause_preview() -> None:
        preview_timer.stop()

    def advance_preview_frame() -> None:
        if not api_store.advance_preview_frame():
            preview_timer.stop()

    preview_timer.timeout.connect(advance_preview_frame)
    chat_signals.reply_ready.connect(window.say)
    chat_signals.reply_ready.connect(window.receive_chat_reply)
    api_signals.state_requested.connect(apply_state)
    api_signals.say_requested.connect(say_text)
    api_signals.chat_requested.connect(chat_text)
    api_signals.state_video_requested.connect(load_state_video)
    api_signals.reset_state_video_requested.connect(reset_state_video)
    api_signals.state_scale_requested.connect(set_state_scale)
    api_signals.state_playback_speed_requested.connect(set_state_playback_speed)
    api_signals.state_loop_mode_requested.connect(set_state_loop_mode)
    api_signals.black_background_requested.connect(set_black_background_transparent)
    api_signals.play_preview_requested.connect(play_preview)
    api_signals.pause_preview_requested.connect(pause_preview)
    api_signals.quit_requested.connect(app.quit)
    window.control_panel_requested.connect(show_control_panel)
    window.chat_requested.connect(chat_text)
    loader_signals.state_loaded.connect(on_state_video_loaded)
    loader_signals.state_failed.connect(on_state_video_failed)

    for state, path in state_material_paths.copy().items():
        if state not in api_store.state_material_names:
            continue
        if Path(path).exists():
            api_store.set_state_material_loading(state, path)
            load_state_video(
                state,
                path,
                api_store.black_background_transparent,
                activate=False,
            )
        else:
            api_store.set_state_material_failed(state, path, "文件不存在")

    show_control_panel()

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
