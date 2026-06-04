from dataclasses import dataclass
from threading import Thread

from PyQt5.QtCore import QObject, pyqtSignal


STATE_COMMANDS = {"idle", "happy", "sleep", "walk"}
SIMPLE_COMMANDS = STATE_COMMANDS | {"help", "hide", "show", "quit"}

HELP_TEXT = """可用命令:
  help              显示帮助
  idle              切换到待机
  happy             切换到开心
  sleep             切换到睡觉
  walk              切换到走动
  say <文本>        让宠物显示一句话
  chat <文本>       和宠物本地对话
  hide              隐藏宠物
  show              显示宠物
  quit / exit       退出程序
"""


@dataclass(frozen=True)
class Command:
    name: str
    text: str = ""


def parse_command(line: str) -> Command:
    raw = line.strip()
    if not raw:
        return Command("empty")

    name, _, rest = raw.partition(" ")
    normalized = name.lower()
    text = rest.strip()

    if normalized == "exit":
        return Command("quit")
    if normalized in SIMPLE_COMMANDS:
        return Command(normalized)
    if normalized in {"say", "chat"}:
        return Command(normalized, text)
    return Command("unknown", raw)


class ConsoleBridge(QObject):
    line_received = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._thread = Thread(target=self._read_loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _read_loop(self) -> None:
        while True:
            try:
                line = input("> ")
            except EOFError:
                break
            self.line_received.emit(line)
