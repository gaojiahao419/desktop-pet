import sys

from PyQt5.QtWidgets import QApplication

from command_console import HELP_TEXT, ConsoleBridge, parse_command
from dialogue import LocalDialogue
from pet_animator import PetAnimator
from pet_window import PetWindow


def main() -> int:
    app = QApplication(sys.argv)
    dialogue = LocalDialogue()
    animator = PetAnimator()
    window = PetWindow(animator, dialogue)
    window.show()

    console = ConsoleBridge()

    def handle_line(line: str) -> None:
        command = parse_command(line)
        if command.name == "empty":
            return
        if command.name == "help":
            print(HELP_TEXT)
            return
        if command.name in {"idle", "happy", "sleep", "walk"}:
            window.set_state(command.name)
            print(f"状态已切换: {command.name}")
            return
        if command.name == "say":
            if not command.text:
                print("用法: say <文本>")
                return
            window.say(command.text)
            print(f"你让宠物说: {command.text}")
            return
        if command.name == "chat":
            if not command.text:
                print("用法: chat <文本>")
                return
            reply = dialogue.reply_for_text(command.text)
            window.say(reply)
            print(f"宠物: {reply}")
            return
        if command.name == "hide":
            window.hide_pet()
            print("宠物已隐藏，输入 show 可恢复。")
            return
        if command.name == "show":
            window.show_pet()
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
