# Desktop Pet MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable Python desktop pet with a transparent always-on-top window, console control, left-click action switching, right-click dialogue menu, and local preset replies.

**Architecture:** Keep deterministic logic outside the PyQt window so it can be tested with `pytest`. The PyQt layer owns only desktop-window behavior, mouse events, menu display, timers, and safe signal handling from the console thread.

**Tech Stack:** Python 3.9, PyQt5, Pillow, pytest.

---

## Scope Check

The approved spec is one coherent MVP: a local Windows desktop pet. The work does not need to be split into separate specs because the subsystems are tightly connected and can be delivered as one runnable program.

## File Structure

- Create `requirements.txt`: documents runtime and test dependencies.
- Create `dialogue.py`: local keyword replies and right-click menu replies.
- Create `command_console.py`: command parser, help text, and console input bridge.
- Create `pet_animator.py`: state names, click-cycle logic, frame parameters, and speech timing.
- Create `pet_renderer.py`: Pillow-based transparent pet image rendering.
- Create `pet_window.py`: PyQt transparent always-on-top window, mouse interactions, right-click menu, and drawing.
- Create `main.py`: application wiring and command dispatch.
- Create `README.md`: installation, running, commands, and manual verification.
- Create `tests/test_dialogue.py`: unit tests for local replies.
- Create `tests/test_command_console.py`: unit tests for command parsing.
- Create `tests/test_pet_animator.py`: unit tests for state transitions.
- Create `tests/test_pet_renderer.py`: unit tests for generated image shape and transparency.

---

### Task 1: Project Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create dependency file**

Write `requirements.txt`:

```text
PyQt5
Pillow
pytest
```

- [ ] **Step 2: Create test package marker**

Write `tests/__init__.py` as an empty file so test imports are stable on Windows.

- [ ] **Step 3: Verify dependency imports**

Run:

```powershell
python -c "import PyQt5, PIL, pytest; print('dependencies ok')"
```

Expected:

```text
dependencies ok
```

- [ ] **Step 4: Commit**

```powershell
git add requirements.txt tests/__init__.py
git commit -m "chore: add desktop pet dependencies"
```

---

### Task 2: Local Dialogue Engine

**Files:**
- Create: `dialogue.py`
- Create: `tests/test_dialogue.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_dialogue.py`:

```python
from dialogue import LocalDialogue


def test_keyword_greeting_reply():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_text("你好呀")
    assert reply in dialogue.categories["greeting"]


def test_keyword_encouragement_reply():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_text("今天有点累")
    assert reply in dialogue.categories["encouragement"]


def test_menu_status_uses_current_state():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_menu("status", current_state="sleep")
    assert "sleep" in reply


def test_unknown_menu_action_returns_default_reply():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_menu("unknown", current_state="idle")
    assert reply in dialogue.categories["default"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_dialogue.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'dialogue'`.

- [ ] **Step 3: Implement dialogue engine**

Write `dialogue.py`:

```python
import random
from typing import Dict, List


class LocalDialogue:
    def __init__(self) -> None:
        self.categories: Dict[str, List[str]] = {
            "greeting": [
                "你好，我在这里。",
                "嗨，今天也一起待一会儿。",
                "你好呀，我刚刚醒来。",
            ],
            "status": [
                "我现在状态不错。",
                "我正在观察桌面。",
                "我有点想动一动。",
            ],
            "companionship": [
                "我陪你待着。",
                "我们一起安静一会儿。",
                "我会在屏幕边上陪你。",
            ],
            "encouragement": [
                "慢慢来，先做眼前这一小步。",
                "辛苦了，可以先缓一缓。",
                "你已经在推进了。",
            ],
            "default": [
                "我听到了。",
                "这个我先记在心里。",
                "嗯，我在看着你操作。",
            ],
        }
        self.keyword_map = {
            "greeting": ("你好", "hello", "hi"),
            "status": ("你好吗", "怎么样"),
            "companionship": ("无聊", "陪我"),
            "encouragement": ("累", "压力", "加油"),
        }
        self.menu_map = {
            "greeting": "greeting",
            "status": "status",
            "company": "companionship",
            "encourage": "encouragement",
            "random": "default",
        }

    def reply_for_text(self, text: str) -> str:
        normalized = text.strip().lower()
        for category, keywords in self.keyword_map.items():
            if any(keyword.lower() in normalized for keyword in keywords):
                return self._pick(category)
        return self._pick("default")

    def reply_for_menu(self, action: str, current_state: str = "idle") -> str:
        if action == "status":
            return f"我现在是 {current_state} 状态。"
        category = self.menu_map.get(action, "default")
        return self._pick(category)

    def _pick(self, category: str) -> str:
        return random.choice(self.categories[category])
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_dialogue.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit**

```powershell
git add dialogue.py tests/test_dialogue.py
git commit -m "feat: add local dialogue replies"
```

---

### Task 3: Console Command Parser

**Files:**
- Create: `command_console.py`
- Create: `tests/test_command_console.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_command_console.py`:

```python
from command_console import Command, parse_command


def test_parse_simple_state_command():
    assert parse_command("happy") == Command(name="happy", text="")


def test_parse_say_command_preserves_text():
    assert parse_command("say 你好 桌面") == Command(name="say", text="你好 桌面")


def test_parse_chat_command_preserves_text():
    assert parse_command("chat 今天怎么样") == Command(name="chat", text="今天怎么样")


def test_parse_quit_alias():
    assert parse_command("exit") == Command(name="quit", text="")


def test_parse_empty_line():
    assert parse_command("   ") == Command(name="empty", text="")


def test_parse_unknown_command():
    assert parse_command("dance now") == Command(name="unknown", text="dance now")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_command_console.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'command_console'`.

- [ ] **Step 3: Implement command parser and console bridge**

Write `command_console.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_command_console.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 5: Commit**

```powershell
git add command_console.py tests/test_command_console.py
git commit -m "feat: add console command parsing"
```

---

### Task 4: Pet Animator State Logic

**Files:**
- Create: `pet_animator.py`
- Create: `tests/test_pet_animator.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_pet_animator.py`:

```python
from pet_animator import PetAnimator


def test_default_state_is_idle():
    animator = PetAnimator()
    assert animator.state == "idle"


def test_click_cycle_from_idle_to_happy():
    animator = PetAnimator()
    animator.next_click_state()
    assert animator.state == "happy"


def test_click_cycle_wraps_through_states():
    animator = PetAnimator()
    seen = []
    for _ in range(4):
        animator.next_click_state()
        seen.append(animator.state)
    assert seen == ["happy", "idle", "walk", "sleep"]


def test_click_while_talking_goes_to_happy():
    animator = PetAnimator()
    animator.say("你好")
    animator.next_click_state()
    assert animator.state == "happy"
    assert animator.speech_text == ""


def test_advance_returns_frame_data():
    animator = PetAnimator()
    frame = animator.advance()
    assert frame.state == "idle"
    assert isinstance(frame.tick, int)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_pet_animator.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pet_animator'`.

- [ ] **Step 3: Implement animator**

Write `pet_animator.py`:

```python
from dataclasses import dataclass
from math import sin
from typing import Optional


VALID_STATES = {"idle", "happy", "sleep", "walk", "talk", "hidden"}
CLICK_SEQUENCE = ["idle", "happy", "idle", "walk", "sleep"]


@dataclass(frozen=True)
class PetFrame:
    state: str
    tick: int
    body_y: int
    eye_closed: bool
    mouth_open: bool
    walk_dx: int


class PetAnimator:
    def __init__(self) -> None:
        self.state = "idle"
        self.tick = 0
        self.speech_text = ""
        self.speech_ticks_left = 0
        self._click_index = 0

    def set_state(self, state: str) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported pet state: {state}")
        self.state = state
        if state != "talk":
            self.clear_speech()

    def say(self, text: str, duration_ticks: int = 80) -> None:
        self.state = "talk"
        self.speech_text = text
        self.speech_ticks_left = duration_ticks

    def clear_speech(self) -> None:
        self.speech_text = ""
        self.speech_ticks_left = 0

    def next_click_state(self) -> str:
        if self.state == "talk":
            self.set_state("happy")
            self._click_index = CLICK_SEQUENCE.index("happy")
            return self.state

        self._click_index = (self._click_index + 1) % len(CLICK_SEQUENCE)
        next_state = CLICK_SEQUENCE[self._click_index]
        self.set_state(next_state)
        return self.state

    def advance(self) -> PetFrame:
        self.tick += 1
        if self.state == "talk" and self.speech_ticks_left > 0:
            self.speech_ticks_left -= 1
            if self.speech_ticks_left == 0:
                self.clear_speech()
                self.state = "idle"

        return PetFrame(
            state=self.state,
            tick=self.tick,
            body_y=self._body_y(),
            eye_closed=self._eye_closed(),
            mouth_open=self._mouth_open(),
            walk_dx=self._walk_dx(),
        )

    def _body_y(self) -> int:
        if self.state == "happy":
            return -6 if (self.tick // 6) % 2 == 0 else 0
        if self.state == "sleep":
            return 2
        return int(sin(self.tick / 8) * 2)

    def _eye_closed(self) -> bool:
        if self.state == "sleep":
            return True
        return self.tick % 90 in (0, 1, 2, 3)

    def _mouth_open(self) -> bool:
        return self.state == "talk" and (self.tick // 8) % 2 == 0

    def _walk_dx(self) -> int:
        if self.state != "walk":
            return 0
        return 2 if (self.tick // 10) % 2 == 0 else -2
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_pet_animator.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit**

```powershell
git add pet_animator.py tests/test_pet_animator.py
git commit -m "feat: add pet animator states"
```

---

### Task 5: Pillow Pet Renderer

**Files:**
- Create: `pet_renderer.py`
- Create: `tests/test_pet_renderer.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_pet_renderer.py`:

```python
from pet_animator import PetFrame
from pet_renderer import PetRenderer


def test_renderer_returns_transparent_rgba_image():
    renderer = PetRenderer()
    frame = PetFrame("idle", 1, 0, False, False, 0)
    image = renderer.render(frame)
    assert image.mode == "RGBA"
    assert image.size == (220, 220)
    assert image.getpixel((0, 0))[3] == 0


def test_renderer_draws_nontransparent_pet_pixels():
    renderer = PetRenderer()
    frame = PetFrame("happy", 1, -4, False, False, 0)
    image = renderer.render(frame)
    assert image.getbbox() is not None


def test_renderer_can_draw_speech_bubble():
    renderer = PetRenderer()
    frame = PetFrame("talk", 1, 0, False, True, 0)
    image = renderer.render(frame, speech_text="你好")
    assert image.getbbox() is not None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_pet_renderer.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pet_renderer'`.

- [ ] **Step 3: Implement renderer**

Write `pet_renderer.py`:

```python
from PIL import Image, ImageDraw

from pet_animator import PetFrame


class PetRenderer:
    def __init__(self, size: int = 220) -> None:
        self.size = size

    def render(self, frame: PetFrame, speech_text: str = "") -> Image.Image:
        image = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        cx = self.size // 2 + frame.walk_dx
        cy = 130 + frame.body_y
        body_color = self._body_color(frame.state)

        draw.ellipse((cx - 48, cy - 55, cx + 48, cy + 45), fill=body_color, outline=(70, 56, 48, 255), width=3)
        draw.polygon([(cx - 40, cy - 40), (cx - 62, cy - 82), (cx - 18, cy - 58)], fill=body_color, outline=(70, 56, 48, 255))
        draw.polygon([(cx + 40, cy - 40), (cx + 62, cy - 82), (cx + 18, cy - 58)], fill=body_color, outline=(70, 56, 48, 255))

        self._draw_face(draw, frame, cx, cy)
        self._draw_feet(draw, frame, cx, cy)

        if frame.state == "sleep":
            draw.text((cx + 44, cy - 80), "Z", fill=(55, 55, 70, 230))
            draw.text((cx + 60, cy - 96), "z", fill=(55, 55, 70, 200))

        if speech_text:
            self._draw_bubble(draw, speech_text)

        return image

    def _body_color(self, state: str) -> tuple:
        if state == "happy":
            return (255, 205, 111, 255)
        if state == "sleep":
            return (190, 204, 232, 255)
        if state == "walk":
            return (151, 215, 181, 255)
        if state == "talk":
            return (255, 185, 198, 255)
        return (246, 196, 132, 255)

    def _draw_face(self, draw: ImageDraw.ImageDraw, frame: PetFrame, cx: int, cy: int) -> None:
        if frame.eye_closed:
            draw.arc((cx - 31, cy - 20, cx - 13, cy - 4), 0, 180, fill=(40, 40, 40, 255), width=3)
            draw.arc((cx + 13, cy - 20, cx + 31, cy - 4), 0, 180, fill=(40, 40, 40, 255), width=3)
        else:
            draw.ellipse((cx - 30, cy - 25, cx - 16, cy - 9), fill=(30, 30, 35, 255))
            draw.ellipse((cx + 16, cy - 25, cx + 30, cy - 9), fill=(30, 30, 35, 255))

        if frame.mouth_open:
            draw.ellipse((cx - 8, cy + 4, cx + 8, cy + 20), fill=(90, 45, 55, 255))
        elif frame.state == "happy":
            draw.arc((cx - 12, cy, cx + 12, cy + 18), 0, 180, fill=(90, 45, 55, 255), width=3)
        else:
            draw.line((cx - 8, cy + 10, cx + 8, cy + 10), fill=(90, 45, 55, 255), width=3)

    def _draw_feet(self, draw: ImageDraw.ImageDraw, frame: PetFrame, cx: int, cy: int) -> None:
        offset = 4 if frame.state == "walk" and frame.walk_dx > 0 else 0
        draw.ellipse((cx - 36 - offset, cy + 35, cx - 8 - offset, cy + 52), fill=(88, 92, 84, 255))
        draw.ellipse((cx + 8 + offset, cy + 35, cx + 36 + offset, cy + 52), fill=(88, 92, 84, 255))

    def _draw_bubble(self, draw: ImageDraw.ImageDraw, text: str) -> None:
        clean_text = text[:18]
        draw.rounded_rectangle((18, 14, 202, 58), radius=12, fill=(255, 255, 255, 235), outline=(65, 65, 70, 230), width=2)
        draw.text((30, 28), clean_text, fill=(35, 35, 40, 255))
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_pet_renderer.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```powershell
git add pet_renderer.py tests/test_pet_renderer.py
git commit -m "feat: render generated pet frames"
```

---

### Task 6: PyQt Window and Application Wiring

**Files:**
- Create: `pet_window.py`
- Create: `main.py`

- [ ] **Step 1: Implement transparent always-on-top pet window**

Write `pet_window.py`:

```python
from typing import Callable

from PIL.ImageQt import ImageQt
from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QAction, QMenu, QWidget, QLabel, QVBoxLayout

from dialogue import LocalDialogue
from pet_animator import PetAnimator
from pet_renderer import PetRenderer


class PetWindow(QWidget):
    def __init__(self, animator: PetAnimator, dialogue: LocalDialogue) -> None:
        super().__init__()
        self.animator = animator
        self.dialogue = dialogue
        self.renderer = PetRenderer()
        self.image_label = QLabel(self)
        self.image_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.drag_start = QPoint()
        self.dragging = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(220, 220)
        self.move(1200, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.image_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_frame)
        self.timer.start(60)
        self.refresh_frame()

    def refresh_frame(self) -> None:
        frame = self.animator.advance()
        image = self.renderer.render(frame, self.animator.speech_text)
        qimage = ImageQt(image)
        self.image_label.setPixmap(QPixmap.fromImage(qimage))

        if frame.state == "walk":
            pos = self.pos()
            next_x = pos.x() + frame.walk_dx
            if next_x < 20:
                next_x = 20
            self.move(next_x, pos.y())

    def set_state(self, state: str) -> None:
        self.animator.set_state(state)
        self.show()

    def say(self, text: str) -> None:
        self.animator.say(text)
        self.show()

    def show_pet(self) -> None:
        self.animator.set_state("idle") if self.animator.state == "hidden" else None
        self.show()
        self.raise_()

    def hide_pet(self) -> None:
        self.animator.set_state("hidden")
        self.hide()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPos() - self.frameGeometry().topLeft()
            self.dragging = False
            event.accept()
        elif event.button() == Qt.RightButton:
            self._show_dialogue_menu(event.globalPos())
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            delta = event.globalPos() - self.frameGeometry().topLeft() - self.drag_start
            if abs(delta.x()) > 3 or abs(delta.y()) > 3:
                self.dragging = True
            self.move(event.globalPos() - self.drag_start)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self.dragging:
            self.animator.next_click_state()
            event.accept()

    def _show_dialogue_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        actions = [
            ("打招呼", lambda: self._menu_reply("greeting")),
            ("问问状态", lambda: self._menu_reply("status")),
            ("陪我一下", lambda: self._menu_reply("company")),
            ("鼓励我", lambda: self._menu_reply("encourage")),
            ("随机聊天", lambda: self._menu_reply("random")),
        ]
        for label, callback in actions:
            action = QAction(label, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        menu.exec_(global_pos)

    def _menu_reply(self, action: str) -> None:
        reply = self.dialogue.reply_for_menu(action, self.animator.state)
        print(f"宠物: {reply}")
        self.say(reply)
```

- [ ] **Step 2: Implement main app command dispatch**

Write `main.py`:

```python
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
```

- [ ] **Step 3: Run import smoke check**

Run:

```powershell
python -c "from pet_window import PetWindow; from main import main; print('app imports ok')"
```

Expected:

```text
app imports ok
```

- [ ] **Step 4: Run all unit tests**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add pet_window.py main.py
git commit -m "feat: add desktop pet window"
```

---

### Task 7: README and Manual Verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

Write `README.md`:

```markdown
# Python 桌面宠物

这是一个 Windows Python 桌面宠物第一版。它使用 PyQt5 创建透明、无边框、始终置顶的窗口，使用 Pillow 绘制内置动态宠物。

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

启动后会出现一个桌面宠物窗口。控制台会显示可用命令。

## 鼠标交互

- 左键点击宠物：切换动作，不显示额外文字。
- 左键拖拽宠物：移动位置。
- 右键点击宠物：打开对话选择菜单。

## 控制台命令

```text
help
idle
happy
sleep
walk
say <文本>
chat <文本>
hide
show
quit
exit
```

## 手动验收

1. 运行 `python main.py`。
2. 确认宠物窗口透明、无边框、置顶。
3. 左键点击宠物，确认动作切换且没有文字反馈。
4. 左键拖拽宠物，确认只移动位置。
5. 右键点击宠物，确认出现对话选择菜单。
6. 在控制台输入 `say 你好`，确认宠物显示文字气泡。
7. 在控制台输入 `chat 今天有点累`，确认宠物本地回复。
8. 输入 `hide` 后宠物隐藏，输入 `show` 后恢复。
9. 输入 `quit` 后程序退出。

## 自动检查

```powershell
python -m pytest -q
python -m compileall .
```
```

- [ ] **Step 2: Run syntax check**

Run:

```powershell
python -m compileall .
```

Expected: command exits with status 0.

- [ ] **Step 3: Run all tests**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Launch manual smoke test**

Run:

```powershell
python main.py
```

Expected:

- A transparent pet window appears.
- The window stays above other apps.
- The console prints help text.
- Entering `quit` closes the app.

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "docs: add desktop pet usage guide"
```

---

## Plan Self-Review

Spec coverage:

- Always-on-top transparent desktop window: Task 6.
- Console control: Tasks 3 and 6.
- Left-click action switching without text: Tasks 4 and 6.
- Right-click dialogue menu: Tasks 2 and 6.
- Local preset replies: Task 2.
- Generated dynamic pet visuals: Tasks 4 and 5.
- Hide, show, quit, say, chat commands: Tasks 3 and 6.
- Basic automated checks and manual verification: Task 7.

Placeholder scan:

- The plan contains no unresolved placeholder markers and no incomplete implementation step.
- Every code-writing step names the exact file and includes concrete code.

Type consistency:

- `Command(name, text)` is defined in Task 3 and used by tests and `main.py`.
- `PetAnimator.say`, `set_state`, `next_click_state`, and `advance` are defined in Task 4 and used by `pet_window.py`.
- `PetRenderer.render(frame, speech_text)` is defined in Task 5 and used by `pet_window.py`.
