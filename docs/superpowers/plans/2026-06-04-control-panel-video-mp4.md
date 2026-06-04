# Control Panel Video MP4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visual control panel, MP4 pet素材 upload, alpha-first video playback, chroma-key fallback, and live pet size control.

**Architecture:** Keep video frame processing in a pure module so alpha and chroma-key behavior can be tested without opening PyQt windows. The pet window will choose between the existing generated renderer and an optional video source, while the new control panel sends user actions through PyQt signals.

**Tech Stack:** Python 3.9, PyQt5, Pillow, imageio, imageio-ffmpeg, pytest.

---

## Scope Check

The second-version spec is one incremental feature set on the current desktop pet: visual controls plus optional MP4 rendering. It does not need a separate app or a separate runtime.

## File Structure

- Modify `requirements.txt`: add `imageio` and `imageio-ffmpeg`.
- Create `video_pet_source.py`: scale clamping, frame-to-RGBA conversion, chroma-key fallback, MP4 frame loading, and looped frame retrieval.
- Create `tests/test_video_pet_source.py`: unit tests for alpha preservation, chroma-key conversion, tolerance effect, scale clamping, and frame looping.
- Modify `pet_window.py`: optional `VideoPetSource`, live scaling, uploaded素材 reset, and resized display.
- Create `control_panel.py`: PyQt control panel with upload, reset, background color, tolerance, scale, action buttons, say/chat, hide/show, and quit controls.
- Modify `main.py`: create `ControlPanelWindow` and connect it to `PetWindow`, `PetAnimator`, and `LocalDialogue`.
- Modify `README.md`: document control panel, MP4 upload, transparent MP4 behavior, chroma-key fallback, and size control.

---

### Task 1: Video Frame Processing Core

**Files:**
- Modify: `requirements.txt`
- Create: `video_pet_source.py`
- Create: `tests/test_video_pet_source.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_video_pet_source.py`:

```python
import numpy as np

from video_pet_source import VideoPetSource, clamp_scale, frame_to_rgba_image


def test_four_channel_frame_preserves_alpha():
    frame = np.zeros((2, 2, 4), dtype=np.uint8)
    frame[:, :, 0] = 10
    frame[:, :, 1] = 20
    frame[:, :, 2] = 30
    frame[:, :, 3] = [[0, 64], [128, 255]]

    image = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=35)

    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((1, 0))[3] == 64
    assert image.getpixel((0, 1))[3] == 128
    assert image.getpixel((1, 1))[3] == 255


def test_three_channel_green_background_becomes_transparent():
    frame = np.array(
        [
            [[0, 255, 0], [200, 10, 10]],
            [[0, 250, 0], [30, 40, 50]],
        ],
        dtype=np.uint8,
    )

    image = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=10)

    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((0, 1))[3] == 0
    assert image.getpixel((1, 0))[3] == 255
    assert image.getpixel((1, 1))[3] == 255


def test_tolerance_changes_transparent_pixel_count():
    frame = np.array([[[0, 255, 0], [0, 200, 0], [50, 50, 50]]], dtype=np.uint8)

    strict = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=10)
    loose = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=80)

    strict_alpha = [strict.getpixel((x, 0))[3] for x in range(3)]
    loose_alpha = [loose.getpixel((x, 0))[3] for x in range(3)]
    assert strict_alpha.count(0) == 1
    assert loose_alpha.count(0) == 2


def test_clamp_scale_limits_range():
    assert clamp_scale(0.1) == 0.5
    assert clamp_scale(1.25) == 1.25
    assert clamp_scale(3.0) == 2.5


def test_video_source_loops_frames_from_arrays():
    frames = [
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.full((1, 1, 3), 255, dtype=np.uint8),
    ]
    source = VideoPetSource.from_arrays(frames, background_color=(0, 255, 0), tolerance=35)

    first = source.next_frame()
    second = source.next_frame()
    third = source.next_frame()

    assert first.getpixel((0, 0)) != second.getpixel((0, 0))
    assert third.getpixel((0, 0)) == first.getpixel((0, 0))
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_video_pet_source.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'video_pet_source'`.

- [ ] **Step 3: Add dependencies**

Update `requirements.txt` to exactly:

```text
PyQt5
Pillow
pytest
imageio
imageio-ffmpeg
numpy
```

- [ ] **Step 4: Implement frame processing and video source**

Write `video_pet_source.py`:

```python
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import imageio.v3 as iio
import numpy as np
from PIL import Image


Color = Tuple[int, int, int]


def clamp_scale(value: float) -> float:
    return max(0.5, min(2.5, float(value)))


def clamp_tolerance(value: int) -> int:
    return max(0, min(120, int(value)))


def frame_to_rgba_image(frame: np.ndarray, background_color: Color, tolerance: int) -> Image.Image:
    array = np.asarray(frame, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError(f"Unsupported video frame shape: {array.shape}")

    if array.shape[2] == 4:
        return Image.fromarray(array, mode="RGBA")

    rgb = array[:, :, :3]
    alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    bg = np.array(background_color, dtype=np.int16)
    diff = np.abs(rgb.astype(np.int16) - bg)
    mask = np.max(diff, axis=2) <= clamp_tolerance(tolerance)
    alpha[mask] = 0
    rgba = np.dstack((rgb, alpha))
    return Image.fromarray(rgba, mode="RGBA")


class VideoPetSource:
    def __init__(self, frames: Sequence[Image.Image], source_path: str = "") -> None:
        if not frames:
            raise ValueError("Video source requires at least one frame")
        self.frames: List[Image.Image] = [frame.convert("RGBA") for frame in frames]
        self.source_path = source_path
        self.index = 0

    @classmethod
    def from_path(
        cls,
        path: str,
        background_color: Color = (0, 255, 0),
        tolerance: int = 35,
        max_frames: int = 600,
    ) -> "VideoPetSource":
        video_path = Path(path)
        if video_path.suffix.lower() != ".mp4":
            raise ValueError("请选择 MP4 文件")

        frames = []
        for frame in iio.imiter(video_path):
            frames.append(frame_to_rgba_image(frame, background_color, tolerance))
            if len(frames) >= max_frames:
                break

        if not frames:
            raise ValueError("无法读取视频帧")
        return cls(frames, source_path=str(video_path))

    @classmethod
    def from_arrays(
        cls,
        frames: Iterable[np.ndarray],
        background_color: Color = (0, 255, 0),
        tolerance: int = 35,
    ) -> "VideoPetSource":
        images = [frame_to_rgba_image(frame, background_color, tolerance) for frame in frames]
        return cls(images)

    def next_frame(self) -> Image.Image:
        frame = self.frames[self.index]
        self.index = (self.index + 1) % len(self.frames)
        return frame
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_video_pet_source.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Commit**

```powershell
git add requirements.txt video_pet_source.py tests/test_video_pet_source.py
git commit -m "feat: add video pet source"
```

---

### Task 2: Pet Window Video Source and Scaling

**Files:**
- Modify: `pet_window.py`

- [ ] **Step 1: Modify imports and state**

In `pet_window.py`, add imports:

```python
from PIL import Image
from video_pet_source import VideoPetSource, clamp_scale
```

In `PetWindow.__init__`, add these attributes after `self.renderer = PetRenderer()`:

```python
        self.video_source = None
        self.scale = 1.0
        self.base_size = 220
```

- [ ] **Step 2: Replace fixed sizing with helper**

Add this method to `PetWindow`:

```python
    def _apply_scaled_size(self) -> None:
        display_size = int(self.base_size * self.scale)
        self.setFixedSize(display_size, display_size)
        self.image_label.setFixedSize(display_size, display_size)
```

Replace the two direct `setFixedSize(220, 220)` calls in `__init__` with:

```python
        self._apply_scaled_size()
```

- [ ] **Step 3: Add video and scale public methods**

Add these methods to `PetWindow`:

```python
    def set_video_source(self, source: VideoPetSource) -> None:
        self.video_source = source
        self.show_pet()

    def clear_video_source(self) -> None:
        self.video_source = None
        self.show_pet()

    def set_scale(self, scale: float) -> None:
        old_pos = self.pos()
        self.scale = clamp_scale(scale)
        self._apply_scaled_size()
        self.move(old_pos)
        self.refresh_frame()
```

- [ ] **Step 4: Update frame rendering**

Replace the first four lines of `refresh_frame` with:

```python
        frame = self.animator.advance()
        if self.video_source is not None:
            image = self.video_source.next_frame()
        else:
            image = self.renderer.render(frame, self.animator.speech_text)
        image = self._resize_image(image)
        qimage = self._pil_to_qimage(image)
```

Add:

```python
    def _resize_image(self, image: Image.Image) -> Image.Image:
        display_size = int(self.base_size * self.scale)
        return image.convert("RGBA").resize((display_size, display_size), Image.LANCZOS)
```

- [ ] **Step 5: Run import and tests**

Run:

```powershell
python -c "from pet_window import PetWindow; print('pet window imports ok')"
python -m pytest -q
```

Expected:

```text
pet window imports ok
```

and all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add pet_window.py
git commit -m "feat: support video source scaling"
```

---

### Task 3: Control Panel Window

**Files:**
- Create: `control_panel.py`

- [ ] **Step 1: Implement control panel class**

Write `control_panel.py`:

```python
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class ControlPanelWindow(QWidget):
    state_requested = pyqtSignal(str)
    say_requested = pyqtSignal(str)
    chat_requested = pyqtSignal(str)
    video_requested = pyqtSignal(str, tuple, int)
    reset_video_requested = pyqtSignal()
    scale_requested = pyqtSignal(float)
    quit_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.background_color = (0, 255, 0)
        self.setWindowTitle("桌面宠物控制面板")
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        self.status_label = QLabel("当前素材：内置绘制宠物")
        root.addWidget(self._build_material_group())
        root.addWidget(self._build_transparency_group())
        root.addWidget(self._build_size_group())
        root.addWidget(self._build_action_group())
        root.addWidget(self._build_dialogue_group())
        root.addWidget(self.status_label)

        quit_button = QPushButton("退出程序")
        quit_button.clicked.connect(self.quit_requested.emit)
        root.addWidget(quit_button)

    def _build_material_group(self) -> QGroupBox:
        group = QGroupBox("素材")
        layout = QGridLayout(group)
        upload_button = QPushButton("上传 MP4")
        reset_button = QPushButton("恢复默认宠物")
        upload_button.clicked.connect(self._choose_video)
        reset_button.clicked.connect(self._reset_video)
        layout.addWidget(upload_button, 0, 0)
        layout.addWidget(reset_button, 0, 1)
        return group

    def _build_transparency_group(self) -> QGroupBox:
        group = QGroupBox("透明设置")
        layout = QGridLayout(group)
        green_button = QPushButton("绿色")
        white_button = QPushButton("白色")
        black_button = QPushButton("黑色")
        custom_button = QPushButton("自定义")
        green_button.clicked.connect(lambda: self._set_background_color((0, 255, 0)))
        white_button.clicked.connect(lambda: self._set_background_color((255, 255, 255)))
        black_button.clicked.connect(lambda: self._set_background_color((0, 0, 0)))
        custom_button.clicked.connect(self._choose_color)
        self.tolerance_slider = QSlider(Qt.Horizontal)
        self.tolerance_slider.setRange(0, 120)
        self.tolerance_slider.setValue(35)
        self.tolerance_label = QLabel("容差：35")
        self.tolerance_slider.valueChanged.connect(lambda value: self.tolerance_label.setText(f"容差：{value}"))
        layout.addWidget(green_button, 0, 0)
        layout.addWidget(white_button, 0, 1)
        layout.addWidget(black_button, 0, 2)
        layout.addWidget(custom_button, 0, 3)
        layout.addWidget(self.tolerance_label, 1, 0)
        layout.addWidget(self.tolerance_slider, 1, 1, 1, 3)
        return group

    def _build_size_group(self) -> QGroupBox:
        group = QGroupBox("大小")
        layout = QGridLayout(group)
        self.scale_label = QLabel("大小：100%")
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(50, 250)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self._emit_scale)
        layout.addWidget(self.scale_label, 0, 0)
        layout.addWidget(self.scale_slider, 0, 1)
        return group

    def _build_action_group(self) -> QGroupBox:
        group = QGroupBox("动作")
        layout = QGridLayout(group)
        actions = [("待机", "idle"), ("开心", "happy"), ("睡觉", "sleep"), ("走动", "walk"), ("隐藏", "hide"), ("显示", "show")]
        for index, (label, state) in enumerate(actions):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, value=state: self.state_requested.emit(value))
            layout.addWidget(button, index // 3, index % 3)
        return group

    def _build_dialogue_group(self) -> QGroupBox:
        group = QGroupBox("对话")
        layout = QGridLayout(group)
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("输入要说的话或聊天内容")
        say_button = QPushButton("说话")
        chat_button = QPushButton("聊天")
        say_button.clicked.connect(lambda: self.say_requested.emit(self.text_input.text().strip()))
        chat_button.clicked.connect(lambda: self.chat_requested.emit(self.text_input.text().strip()))
        layout.addWidget(self.text_input, 0, 0, 1, 2)
        layout.addWidget(say_button, 1, 0)
        layout.addWidget(chat_button, 1, 1)
        return group

    def _choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 MP4 素材", "", "MP4 视频 (*.mp4)")
        if not path:
            return
        self.video_requested.emit(path, self.background_color, self.tolerance_slider.value())

    def _reset_video(self) -> None:
        self.status_label.setText("当前素材：内置绘制宠物")
        self.reset_video_requested.emit()

    def _set_background_color(self, color: tuple) -> None:
        self.background_color = color

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(QColor(*self.background_color), self, "选择背景色")
        if color.isValid():
            self.background_color = (color.red(), color.green(), color.blue())

    def _emit_scale(self, value: int) -> None:
        self.scale_label.setText(f"大小：{value}%")
        self.scale_requested.emit(value / 100)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
```

- [ ] **Step 2: Run import check**

Run:

```powershell
python -c "from control_panel import ControlPanelWindow; print('control panel imports ok')"
```

Expected:

```text
control panel imports ok
```

- [ ] **Step 3: Commit**

```powershell
git add control_panel.py
git commit -m "feat: add control panel window"
```

---

### Task 4: Application Wiring

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add imports**

Add:

```python
from control_panel import ControlPanelWindow
from video_pet_source import VideoPetSource
```

- [ ] **Step 2: Create and show control panel**

After `window.show()`, add:

```python
    control_panel = ControlPanelWindow()
    control_panel.show()
```

- [ ] **Step 3: Add shared helper functions inside `main`**

Before the existing `handle_line` function, add:

```python
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
```

- [ ] **Step 4: Connect control panel signals**

After helper functions, add:

```python
    control_panel.state_requested.connect(apply_state)
    control_panel.say_requested.connect(say_text)
    control_panel.chat_requested.connect(chat_text)
    control_panel.video_requested.connect(load_video)
    control_panel.reset_video_requested.connect(window.clear_video_source)
    control_panel.scale_requested.connect(window.set_scale)
    control_panel.quit_requested.connect(app.quit)
```

- [ ] **Step 5: Refactor console dispatch to reuse helpers**

In `handle_line`, replace repeated state, say, and chat logic with:

```python
        if command.name in {"idle", "happy", "sleep", "walk"}:
            apply_state(command.name)
            print(f"状态已切换: {command.name}")
            return
        if command.name == "say":
            say_text(command.text)
            return
        if command.name == "chat":
            chat_text(command.text)
            return
```

Keep `help`, `hide`, `show`, `quit`, and unknown-command branches available. For `hide` and `show`, call `apply_state(command.name)`.

- [ ] **Step 6: Run tests and app import check**

Run:

```powershell
python -c "from main import main; print('main imports ok')"
python -m pytest -q
```

Expected:

```text
main imports ok
```

and all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add main.py
git commit -m "feat: wire control panel"
```

---

### Task 5: README and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add a section after the run command:

```markdown
## 控制面板

运行 `python main.py` 后会出现两个窗口：

- 桌面宠物窗口：透明、置顶、可拖拽。
- 控制面板窗口：用于上传 MP4、调整大小、切换动作和输入对话。

控制面板功能：

- 上传 MP4：选择几秒钟的宠物视频素材。
- 恢复默认宠物：回到内置绘制宠物。
- 透明设置：选择背景色并调整容差。
- 大小：使用 50% 到 250% 滑块调整宠物显示大小。
- 动作：待机、开心、睡觉、走动、隐藏、显示。
- 对话：输入文字后点击“说话”或“聊天”。

MP4 透明说明：

- 如果 MP4 解码后包含 Alpha 通道，程序直接使用 Alpha。
- 如果没有 Alpha，程序会按控制面板中的背景色和容差做纯色背景透明化。
- 如果透明效果不理想，调低或调高容差，或换成纯色背景更干净的视频。
```

Update automatic checks to:

```markdown
python -m pytest -q
python -m compileall .
python -c "from main import main; print('main imports ok')"
```

- [ ] **Step 2: Run dependency import check**

Run:

```powershell
python -c "import imageio, imageio_ffmpeg; print('video dependencies ok')"
```

Expected:

```text
video dependencies ok
```

If this fails, run:

```powershell
python -m pip install -r requirements.txt
```

Then rerun the dependency import check.

- [ ] **Step 3: Run full verification**

Run:

```powershell
python -m pytest -q
python -m compileall .
python -c "from main import main; print('main imports ok')"
"quit" | python main.py
```

Expected:

- pytest exits with all tests passing.
- compileall exits with status 0.
- import check prints `main imports ok`.
- `main.py` prints help text and exits after `quit`.

- [ ] **Step 4: Manual GUI check**

Run:

```powershell
python main.py
```

Expected:

- Pet window appears.
- Control panel appears.
- Size slider changes pet size.
- Action buttons change pet state.
- Upload MP4 opens a file chooser.
- Quit button exits the app.

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "docs: document control panel video upload"
```

---

## Plan Self-Review

Spec coverage:

- Control panel window: Task 3 and Task 4.
- Upload MP4: Task 1, Task 3, and Task 4.
- Alpha-first frame handling: Task 1.
- Chroma-key fallback: Task 1 and Task 3.
- Background color and tolerance controls: Task 3.
- Size control from 50% to 250%: Task 1, Task 2, and Task 3.
- Existing console fallback: Task 4 keeps console dispatch.
- Default generated pet fallback: Task 2.
- README and verification: Task 5.

Placeholder scan:

- No unresolved marker text is present in the plan.
- Every code-changing step includes the target file and concrete code.

Type consistency:

- `VideoPetSource.from_path`, `from_arrays`, and `next_frame` are defined in Task 1 and used in Task 2 and Task 4.
- `clamp_scale` is defined in Task 1 and used in Task 2.
- `ControlPanelWindow` signals are defined in Task 3 and connected in Task 4.
