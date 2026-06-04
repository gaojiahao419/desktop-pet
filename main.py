import sys

from PyQt5.QtWidgets import QApplication

from command_console import HELP_TEXT, ConsoleBridge, parse_command
from control_panel import ControlPanelWindow
from dialogue import LocalDialogue
from pet_animator import PetAnimator
from pet_window import PetWindow
from video_pet_source import VideoPetSource


STATE_LABELS = {
    "idle": "待机动作",
    "happy": "高兴动作",
    "sleep": "睡觉动作",
    "angry": "生气动作",
}


def main() -> int:
    app = QApplication(sys.argv)
    dialogue = LocalDialogue()
    animator = PetAnimator()
    window = PetWindow(animator, dialogue)
    window.show()

    control_panel = ControlPanelWindow()
    control_panel.show()

    console = ConsoleBridge()

    def apply_state(name: str) -> None:
        if name == "hide":
            window.hide_pet()
            return
        if name == "show":
            window.show_pet()
            return
        window.set_state(name)

    def say_text(text: str) -> None:
        if not text:
            print("请输入文本。")
            return
        window.say(text)

    def chat_text(text: str) -> None:
        if not text:
            print("请输入聊天内容。")
            return
        reply = dialogue.reply_for_text(text)
        window.say(reply)
        print(f"宠物: {reply}")

    def load_video(path: str, background_color: tuple, tolerance: int) -> None:
        try:
            source = VideoPetSource.from_path(path, background_color, tolerance)
        except Exception as exc:
            message = f"视频加载失败：{exc}"
            control_panel.set_status(message)
            print(message)
            return
        window.set_video_source(source)
        control_panel.set_status(f"当前素材：{path}")
        print(f"已加载视频素材: {path}")

    def load_state_video(state: str, path: str, background_color: tuple, tolerance: int) -> None:
        try:
            source = VideoPetSource.from_path(path, background_color, tolerance)
        except Exception as exc:
            message = f"{STATE_LABELS.get(state, state)}素材加载失败：{exc}"
            control_panel.set_status(message)
            print(message)
            return
        window.set_state_video_source(state, source)
        window.set_state(state)
        control_panel.set_status(f"{STATE_LABELS.get(state, state)}素材已绑定：{path}")
        print(f"已绑定{STATE_LABELS.get(state, state)}素材: {path}")

    control_panel.state_requested.connect(apply_state)
    control_panel.say_requested.connect(say_text)
    control_panel.chat_requested.connect(chat_text)
    control_panel.video_requested.connect(load_video)
    control_panel.reset_video_requested.connect(window.clear_video_source)
    control_panel.state_video_requested.connect(load_state_video)
    control_panel.reset_state_video_requested.connect(window.clear_state_video_source)
    control_panel.scale_requested.connect(window.set_scale)
    control_panel.quit_requested.connect(app.quit)

    def handle_line(line: str) -> None:
        command = parse_command(line)
        if command.name == "empty":
            return
        if command.name == "help":
            print(HELP_TEXT)
            return
        if command.name in {"idle", "happy", "sleep", "angry", "walk"}:
            apply_state(command.name)
            print(f"状态已切换: {command.name}")
            return
        if command.name == "say":
            say_text(command.text)
            return
        if command.name == "chat":
            chat_text(command.text)
            return
        if command.name == "hide":
            apply_state(command.name)
            print("宠物已隐藏，输入 show 可恢复。")
            return
        if command.name == "show":
            apply_state(command.name)
            print("宠物已显示。")
            return
        if command.name == "quit":
            print("正在退出。")
            app.quit()
            return
        print("未知命令，输入 help 查看可用命令。")

    console.line_received.connect(handle_line)
    console.start()
    print(HELP_TEXT)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
