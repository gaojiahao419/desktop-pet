from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from PIL import Image

from video_pet_source import LOOP_MODE_LOOP, LOOP_MODE_ONCE, clamp_playback_speed, clamp_scale, normalize_loop_mode


SCALE_MIN_PERCENT = 0
SCALE_MAX_PERCENT = 250
SCALE_DEFAULT_PERCENT = 100
SPEED_MIN_PERCENT = 25
SPEED_MAX_PERCENT = 300
SPEED_DEFAULT_PERCENT = 100
LOOP_MODE_OPTIONS = [
    ("循环播放", LOOP_MODE_LOOP),
    ("单次定格", LOOP_MODE_ONCE),
]

CONTROL_PANEL_DESIGN_TOKENS = {
    "shell": "#0b0f10",
    "panel": "#14201e",
    "card": "#1f2926",
    "card_alt": "#0f1514",
    "line": "#394842",
    "muted": "#b4b8ad",
    "text": "#f8f3ea",
    "accent": "#f2763d",
    "accent_hover": "#ff8a52",
    "success": "#7ec8a4",
    "danger": "#ff8b7b",
    "secondary": "#84a59d",
    "amber": "#f3b562",
    "chrome": "#eee7db",
}


def scale_percent_to_float(value: int) -> float:
    return clamp_scale(int(value) / 100)


def scale_float_to_percent(value: float) -> int:
    return int(round(clamp_scale(value) * 100))


def speed_percent_to_float(value: int) -> float:
    return clamp_playback_speed(int(value) / 100)


def speed_float_to_percent(value: float) -> int:
    return int(round(clamp_playback_speed(value) * 100))


def preview_frame_label(index: int, total: int) -> str:
    if total <= 0:
        return "当前帧：0 / 0"
    return f"当前帧：{min(total, max(0, index) + 1)} / {total}"


def next_preview_frame_index(index: int, total: int, loop_mode: str) -> int:
    if total <= 0:
        return 0
    if normalize_loop_mode(loop_mode) == LOOP_MODE_ONCE:
        return min(total - 1, index + 1)
    return (index + 1) % total


def control_panel_design_tokens() -> dict:
    return dict(CONTROL_PANEL_DESIGN_TOKENS)


STATE_MATERIALS = [
    ("idle", "待机动作", "平静待机循环"),
    ("happy", "高兴动作", "点击或切换开心时播放"),
    ("angry", "生气动作", "生气状态循环"),
    ("sleep", "睡觉动作", "睡觉状态循环"),
]


ACTION_BUTTONS = [
    ("待机", "idle", "lightButton"),
    ("开心", "happy", "orangeButton"),
    ("生气", "angry", "dangerButton"),
    ("睡觉", "sleep", "lightButton"),
    ("隐藏", "hide", "darkButton"),
    ("显示", "show", "orangeButton"),
]


class ControlPanelWindow(QWidget):
    state_requested = pyqtSignal(str)
    say_requested = pyqtSignal(str)
    chat_requested = pyqtSignal(str)
    state_video_requested = pyqtSignal(str, str, bool)
    reset_state_video_requested = pyqtSignal(str)
    state_scale_requested = pyqtSignal(str, float)
    state_playback_speed_requested = pyqtSignal(str, float)
    state_loop_mode_requested = pyqtSignal(str, str)
    black_background_requested = pyqtSignal(bool)
    quit_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._pending_state_scale = None
        self._state_scale_emit_timer = QTimer(self)
        self._state_scale_emit_timer.setSingleShot(True)
        self._state_scale_emit_timer.timeout.connect(self._emit_pending_state_scale)
        self._pending_state_speed = None
        self._state_speed_emit_timer = QTimer(self)
        self._state_speed_emit_timer.setSingleShot(True)
        self._state_speed_emit_timer.timeout.connect(self._emit_pending_state_speed)
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._advance_preview_frame)
        self._preview_source = None
        self._preview_state = None
        self._preview_frame_index = 0
        self._preview_playing = False
        self.black_background_transparent = False
        self.state_material_names = {state: "未绑定，使用内置绘制" for state, _title, _hint in STATE_MATERIALS}
        self.state_material_labels = {}
        self.state_status_labels = {}
        self.state_scale_sliders = {}
        self.state_scale_labels = {}
        self.state_speed_sliders = {}
        self.state_speed_labels = {}
        self.state_loop_selects = {}
        self.setWindowTitle("桌面宠物控制面板")
        self.setMinimumSize(1480, 900)
        self.setObjectName("controlPanel")
        self.setFont(QFont("Microsoft YaHei UI", 10))
        self._apply_style()

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 26, 26, 26)
        root.setSpacing(18)
        root.addWidget(self._build_title_bar())

        content = QHBoxLayout()
        content.setSpacing(18)
        content.addWidget(self._build_left_panel(), 0)
        content.addWidget(self._build_stage_panel(), 1)
        content.addWidget(self._build_control_stack(), 0)
        root.addLayout(content, 1)

        footer = QHBoxLayout()
        footer.setSpacing(14)
        self.status_label = QLabel("状态：使用内置绘制宠物")
        self.status_label.setObjectName("statusBar")
        self.status_label.setWordWrap(True)
        quit_button = QPushButton("退出程序")
        quit_button.setObjectName("dangerButton")
        quit_button.clicked.connect(self.quit_requested.emit)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(quit_button, 0)
        root.addLayout(footer)

    def _build_title_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("titleBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(26, 14, 26, 14)
        layout.setSpacing(16)

        dots = QLabel("●  ●  ●")
        dots.setObjectName("trafficDots")
        title = QLabel("桌面宠物控制面板")
        title.setObjectName("windowTitle")
        subtitle = QLabel("素材 / 动作 / 对话")
        subtitle.setObjectName("windowSubtitle")
        layout.addWidget(dots, 0)
        layout.addWidget(title, 1)
        layout.addWidget(subtitle, 0)
        return bar

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(450)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 22, 20, 22)
        layout.setSpacing(16)

        title = QLabel("素材库")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        hint = QLabel("上传已经抠好的透明 MP4。程序会直接读取素材 Alpha，不再自动识别背景色或做抠图处理。")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setObjectName("materialScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("materialScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        for state, title, subtitle in STATE_MATERIALS:
            content_layout.addWidget(self._build_state_material_card(state, title, subtitle))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return panel

    def _build_state_material_card(self, state: str, title: str, subtitle: str) -> QWidget:
        card = QFrame()
        card.setObjectName("materialCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        thumb = QLabel("MP4")
        thumb.setObjectName("thumbBadge")
        text_box = QVBoxLayout()
        name = QLabel(title)
        name.setObjectName("materialTitle")
        detail = QLabel(self.state_material_names[state])
        detail.setObjectName("materialSubtitle")
        detail.setWordWrap(True)
        text_box.addWidget(name)
        text_box.addWidget(detail)
        header.addWidget(thumb, 0)
        header.addLayout(text_box, 1)
        layout.addLayout(header)

        status = QLabel(subtitle)
        status.setObjectName("boundTag")
        layout.addWidget(status, 0, Qt.AlignLeft)

        self.state_material_labels[state] = detail
        self.state_status_labels[state] = status

        size_row = QHBoxLayout()
        size_row.setSpacing(10)
        size_text = QLabel("大小")
        size_text.setObjectName("fieldLabel")
        scale_label = QLabel(str(SCALE_DEFAULT_PERCENT))
        scale_label.setObjectName("metricValue")
        scale_slider = QSlider(Qt.Horizontal)
        scale_slider.setRange(SCALE_MIN_PERCENT, SCALE_MAX_PERCENT)
        scale_slider.setValue(SCALE_DEFAULT_PERCENT)
        scale_slider.valueChanged.connect(
            lambda value, key=state: self._queue_state_scale(key, value)
        )
        self.state_scale_sliders[state] = scale_slider
        self.state_scale_labels[state] = scale_label
        size_row.addWidget(size_text, 0)
        size_row.addWidget(scale_slider, 1)
        size_row.addWidget(scale_label, 0)
        layout.addLayout(size_row)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(10)
        speed_text = QLabel("速度")
        speed_text.setObjectName("fieldLabel")
        speed_label = QLabel(str(SPEED_DEFAULT_PERCENT))
        speed_label.setObjectName("metricValue")
        speed_slider = QSlider(Qt.Horizontal)
        speed_slider.setRange(SPEED_MIN_PERCENT, SPEED_MAX_PERCENT)
        speed_slider.setValue(SPEED_DEFAULT_PERCENT)
        speed_slider.valueChanged.connect(
            lambda value, key=state: self._queue_state_speed(key, value)
        )
        self.state_speed_sliders[state] = speed_slider
        self.state_speed_labels[state] = speed_label
        speed_row.addWidget(speed_text, 0)
        speed_row.addWidget(speed_slider, 1)
        speed_row.addWidget(speed_label, 0)
        layout.addLayout(speed_row)

        loop_row = QHBoxLayout()
        loop_row.setSpacing(10)
        loop_text = QLabel("循环方式")
        loop_text.setObjectName("fieldLabel")
        loop_select = QComboBox()
        loop_select.setObjectName("loopModeSelect")
        for label, value in LOOP_MODE_OPTIONS:
            loop_select.addItem(label, value)
        loop_select.currentIndexChanged.connect(
            lambda _index, key=state: self._emit_state_loop_mode(key)
        )
        self.state_loop_selects[state] = loop_select
        loop_row.addWidget(loop_text, 0)
        loop_row.addWidget(loop_select, 1)
        layout.addLayout(loop_row)

        buttons = QGridLayout()
        buttons.setSpacing(10)
        upload = QPushButton("上传 MP4")
        upload.setObjectName("orangeButton")
        switch = QPushButton("切换动作")
        switch.setObjectName("lightButton")
        reset = QPushButton("解绑素材")
        reset.setObjectName("ghostButton")
        upload.clicked.connect(lambda _checked=False, value=state: self._choose_state_video(value))
        switch.clicked.connect(lambda _checked=False, value=state: self.state_requested.emit(value))
        reset.clicked.connect(lambda _checked=False, value=state: self._reset_state_video(value))
        buttons.addWidget(upload, 0, 0)
        buttons.addWidget(switch, 0, 1)
        buttons.addWidget(reset, 1, 0, 1, 2)
        layout.addLayout(buttons)
        return card

    def _build_stage_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("stagePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)
        layout.addWidget(self._build_preview_card(), 1)
        return panel

    def _build_control_stack(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("rightPanel")
        panel.setFixedWidth(420)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(self._build_settings_card(), 0)
        layout.addWidget(self._build_action_card(), 0)
        layout.addWidget(self._build_dialogue_card(), 0)
        layout.addStretch(1)
        return panel

    def _build_preview_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("previewCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("宠物预览")
        title.setObjectName("sectionTitle")
        self.preview_label = QLabel("上传素材后显示首帧预览")
        self.preview_label.setObjectName("previewBox")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(380)

        preview_controls = QHBoxLayout()
        preview_controls.setSpacing(10)
        self.preview_frame_label = QLabel(preview_frame_label(0, 0))
        self.preview_frame_label.setObjectName("previewFrameLabel")
        play_button = QPushButton("播放")
        play_button.setObjectName("orangeButton")
        pause_button = QPushButton("暂停")
        pause_button.setObjectName("lightButton")
        play_button.clicked.connect(self.play_preview)
        pause_button.clicked.connect(self.pause_preview)
        preview_controls.addWidget(self.preview_frame_label, 1)
        preview_controls.addWidget(play_button, 0)
        preview_controls.addWidget(pause_button, 0)

        save_button = QPushButton("同步预览")
        save_button.setObjectName("orangeButton")
        save_button.clicked.connect(lambda: self.status_label.setText("状态：预览已同步到宠物窗口"))
        layout.addWidget(title)
        layout.addWidget(self.preview_label, 1)
        layout.addLayout(preview_controls)
        layout.addWidget(save_button, 0, Qt.AlignRight)
        return card

    def _build_settings_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(22)

        settings_title = QLabel("素材设置")
        settings_title.setObjectName("sectionTitle")

        self.black_background_checkbox = QCheckBox("黑底透明")
        self.black_background_checkbox.setObjectName("blackBackgroundSwitch")
        self.black_background_checkbox.toggled.connect(self._emit_black_background)

        alpha_hint = QLabel("透明素材直接播放；黑底开关只在素材本身是黑色底时使用。")
        alpha_hint.setObjectName("hintText")
        alpha_hint.setWordWrap(True)

        layout.addWidget(settings_title, 0, 0, 1, 3)
        layout.addWidget(self.black_background_checkbox, 1, 0, 1, 3)
        layout.addWidget(alpha_hint, 2, 0, 1, 3)
        return card

    def _build_action_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel("动作控制")
        title.setObjectName("sectionTitle")
        layout.addWidget(title, 0, 0, 1, 3)

        for index, (label, state, object_name) in enumerate(ACTION_BUTTONS):
            button = QPushButton(label)
            button.setObjectName(object_name)
            button.clicked.connect(lambda _checked=False, value=state: self.state_requested.emit(value))
            layout.addWidget(button, 1 + index // 3, index % 3)
        return card

    def _build_dialogue_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel("对话")
        title.setObjectName("sectionTitle")
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("输入要说的话或聊天内容")
        say_button = QPushButton("说话")
        say_button.setObjectName("orangeButton")
        chat_button = QPushButton("聊天")
        chat_button.setObjectName("lightButton")
        say_button.clicked.connect(lambda: self.say_requested.emit(self.text_input.text().strip()))
        chat_button.clicked.connect(lambda: self.chat_requested.emit(self.text_input.text().strip()))

        layout.addWidget(title, 0, 0, 1, 2)
        layout.addWidget(self.text_input, 1, 0, 1, 2)
        layout.addWidget(say_button, 2, 0)
        layout.addWidget(chat_button, 2, 1)
        return card

    def _choose_state_video(self, state: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择动作 MP4 素材", "", "MP4 视频 (*.mp4)")
        if not path:
            return
        self.set_state_material_loading(state, path)
        self.state_video_requested.emit(state, path, self.black_background_checkbox.isChecked())

    def _reset_state_video(self, state: str) -> None:
        self.state_material_names[state] = "未绑定，使用内置绘制"
        self.state_material_labels[state].setText(self.state_material_names[state])
        self.state_status_labels[state].setText("未绑定：使用默认")
        self.status_label.setText(f"状态：{self._state_title(state)} 已解绑素材")
        self.reset_state_video_requested.emit(state)

    def _state_title(self, state: str) -> str:
        for key, title, _subtitle in STATE_MATERIALS:
            if key == state:
                return title
        return state

    def set_state_material_loading(self, state: str, path: str) -> None:
        material_name = Path(path).name
        self.state_material_names[state] = material_name
        self.state_material_labels[state].setText(material_name)
        self.state_status_labels[state].setText("加载中：正在解析素材")
        self.status_label.setText(f"状态：正在加载 {self._state_title(state)} 素材")

    def set_state_material_loaded(self, state: str, path: str, has_transparency: bool = True) -> None:
        material_name = Path(path).name
        self.state_material_names[state] = material_name
        self.state_material_labels[state].setText(material_name)
        if has_transparency:
            self.state_status_labels[state].setText("已绑定：透明动作素材")
            self.status_label.setText(f"状态：{self._state_title(state)} 已绑定 {material_name}")
        else:
            self.state_status_labels[state].setText("无透明通道：会显示背景")
            self.status_label.setText(f"状态：{material_name} 没有透明通道，黑底会原样显示")

    def set_state_material_failed(self, state: str, path: str, error: str) -> None:
        material_name = Path(path).name
        self.state_material_labels[state].setText(f"{material_name} 加载失败")
        self.state_status_labels[state].setText("加载失败：检查素材")
        self.status_label.setText(f"状态：{self._state_title(state)} 素材加载失败：{error}")

    def _queue_state_scale(self, state: str, value: int) -> None:
        self.state_scale_labels[state].setText(str(value))
        self._pending_state_scale = (state, scale_percent_to_float(value))
        self._state_scale_emit_timer.start(80)

    def _queue_state_speed(self, state: str, value: int) -> None:
        self.state_speed_labels[state].setText(str(value))
        self._pending_state_speed = (state, speed_percent_to_float(value))
        self._state_speed_emit_timer.start(80)
        if self._preview_state == state and self._preview_playing:
            self._restart_preview_timer()

    def _emit_pending_state_scale(self) -> None:
        if self._pending_state_scale is None:
            return
        state, scale = self._pending_state_scale
        self.state_scale_requested.emit(state, scale)

    def _emit_pending_state_speed(self) -> None:
        if self._pending_state_speed is None:
            return
        state, speed = self._pending_state_speed
        self.state_playback_speed_requested.emit(state, speed)

    def _emit_state_loop_mode(self, state: str) -> None:
        loop_mode = self._loop_mode_for_state(state)
        self.state_loop_mode_requested.emit(state, loop_mode)

    def _emit_black_background(self, checked: bool) -> None:
        self.black_background_transparent = checked
        self.black_background_requested.emit(checked)

    def set_status(self, text: str) -> None:
        self.status_label.setText(f"状态：{text}")

    def set_preview_source(self, source, state: str = None) -> None:
        self._preview_source = source
        self._preview_state = state
        self._preview_frame_index = 0
        self._render_preview_frame()
        if self._preview_playing:
            self._restart_preview_timer()

    def _render_preview_frame(self) -> None:
        if self._preview_source is None:
            return
        frame = self._preview_source.frames[self._preview_frame_index].convert("RGBA")
        max_width = max(1, self.preview_label.width() - 24)
        max_height = max(1, self.preview_label.height() - 24)
        preview = frame.copy()
        preview.thumbnail((max_width, max_height), Image.LANCZOS)
        self.preview_label.setText("")
        self.preview_label.setPixmap(QPixmap.fromImage(self._pil_to_qimage(preview)))
        self.preview_frame_label.setText(
            preview_frame_label(self._preview_frame_index, len(self._preview_source.frames))
        )

    def set_preview_message(self, text: str) -> None:
        self.pause_preview()
        self._preview_source = None
        self._preview_state = None
        self._preview_frame_index = 0
        self.preview_label.clear()
        self.preview_label.setText(text)
        self.preview_frame_label.setText(preview_frame_label(0, 0))

    def play_preview(self) -> None:
        if self._preview_source is None:
            self.status_label.setText("状态：先上传或选择一个动作素材")
            return
        self._preview_playing = True
        self._restart_preview_timer()

    def pause_preview(self) -> None:
        self._preview_playing = False
        self._preview_timer.stop()

    def _restart_preview_timer(self) -> None:
        if self._preview_source is None:
            return
        self._preview_timer.start(self._preview_source.frame_interval_ms(self._preview_speed()))

    def _advance_preview_frame(self) -> None:
        if self._preview_source is None:
            self.pause_preview()
            return
        self._preview_frame_index = next_preview_frame_index(
            self._preview_frame_index,
            len(self._preview_source.frames),
            self._loop_mode_for_state(self._preview_state),
        )
        self._render_preview_frame()
        if (
            self._loop_mode_for_state(self._preview_state) == LOOP_MODE_ONCE
            and self._preview_frame_index == len(self._preview_source.frames) - 1
        ):
            self.pause_preview()

    def _preview_speed(self) -> float:
        if self._preview_state in self.state_speed_sliders:
            return speed_percent_to_float(self.state_speed_sliders[self._preview_state].value())
        return 1.0

    def _loop_mode_for_state(self, state: str) -> str:
        selector = self.state_loop_selects.get(state)
        if selector is None:
            return LOOP_MODE_LOOP
        return normalize_loop_mode(selector.currentData())

    def _pil_to_qimage(self, image: Image.Image) -> QImage:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        data = rgba.tobytes()
        qimage = QImage(data, width, height, width * 4, QImage.Format_RGBA8888)
        return qimage.copy()

    def set_state_scale(self, state: str, scale: float) -> None:
        if state not in self.state_scale_sliders:
            return
        percent = scale_float_to_percent(scale)
        slider = self.state_scale_sliders[state]
        slider.blockSignals(True)
        slider.setValue(percent)
        slider.blockSignals(False)
        self.state_scale_labels[state].setText(str(percent))

    def set_state_playback_speed(self, state: str, speed: float) -> None:
        if state not in self.state_speed_sliders:
            return
        percent = speed_float_to_percent(speed)
        slider = self.state_speed_sliders[state]
        slider.blockSignals(True)
        slider.setValue(percent)
        slider.blockSignals(False)
        self.state_speed_labels[state].setText(str(percent))

    def set_state_loop_mode(self, state: str, loop_mode: str) -> None:
        selector = self.state_loop_selects.get(state)
        if selector is None:
            return
        value = normalize_loop_mode(loop_mode)
        index = selector.findData(value)
        if index < 0:
            index = 0
        selector.blockSignals(True)
        selector.setCurrentIndex(index)
        selector.blockSignals(False)

    def apply_settings(
        self,
        scale: float,
        black_background_transparent: bool,
        state_materials: dict,
        state_scales: dict = None,
        state_playback_speeds: dict = None,
        state_loop_modes: dict = None,
    ) -> None:
        state_scales = state_scales or {}
        state_playback_speeds = state_playback_speeds or {}
        state_loop_modes = state_loop_modes or {}
        for state in self.state_scale_sliders:
            self.set_state_scale(state, state_scales.get(state, scale))
            self.set_state_playback_speed(state, state_playback_speeds.get(state, 1.0))
            self.set_state_loop_mode(state, state_loop_modes.get(state, LOOP_MODE_LOOP))
        self.black_background_transparent = bool(black_background_transparent)
        self.black_background_checkbox.setChecked(self.black_background_transparent)
        for state, path in state_materials.items():
            if state in self.state_material_labels:
                material_name = Path(path).name
                self.state_material_names[state] = material_name
                self.state_material_labels[state].setText(material_name)
                self.state_status_labels[state].setText("已保存：启动后加载")

    def _apply_style(self) -> None:
        tokens = control_panel_design_tokens()
        style = """
            QWidget#controlPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0b0f10, stop:0.52 #111815, stop:1 #16120f);
                color: #f4f4f2;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
                font-size: 15px;
            }

            QFrame#titleBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #eee7db, stop:0.54 #e4dacb, stop:1 #cfd9cf);
                border: 1px solid rgba(255, 255, 255, 165);
                border-radius: 18px;
            }

            QLabel#trafficDots {
                color: #f15b48;
                font-size: 14px;
                letter-spacing: 2px;
            }

            QLabel#windowTitle {
                color: #121715;
                font-weight: 800;
                font-size: 16px;
            }

            QLabel#windowSubtitle {
                color: #516057;
                font-size: 13px;
                font-weight: 700;
            }

            QFrame#leftPanel,
            QFrame#stagePanel,
            QFrame#rightPanel {
                background: rgba(20, 32, 30, 232);
                border: 1px solid rgba(238, 231, 219, 34);
                border-radius: 20px;
            }

            QFrame#stagePanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #14201e, stop:0.46 #0f1514, stop:1 #211914);
            }

            QScrollArea#materialScroll {
                background: transparent;
                border: 0;
            }

            QWidget#materialScrollContent {
                background: transparent;
            }

            QScrollBar:vertical {
                background: transparent;
                border: 0;
                width: 10px;
            }

            QScrollBar::handle:vertical {
                background: rgba(238, 231, 219, 46);
                border-radius: 5px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                border: none;
                background: transparent;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }

            QLabel#sectionTitle {
                color: #ffffff;
                font-size: 21px;
                font-weight: 800;
            }

            QFrame#materialCard,
            QFrame#settingsCard,
            QFrame#previewCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #24302c, stop:1 #18211f);
                border: 1px solid rgba(238, 231, 219, 38);
                border-radius: 18px;
            }

            QFrame#materialCard:hover,
            QFrame#settingsCard:hover {
                border: 1px solid rgba(242, 118, 61, 72);
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #283630, stop:1 #1b2522);
            }

            QLabel#thumbBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f2763d, stop:1 #84a59d);
                border: 1px solid rgba(238, 231, 219, 70);
                border-radius: 14px;
                color: #f4f4f2;
                font-weight: 800;
                min-width: 64px;
                min-height: 64px;
                qproperty-alignment: AlignCenter;
            }

            QLabel#materialTitle {
                color: #ffffff;
                font-weight: 800;
            }

            QLabel#materialSubtitle,
            QLabel#hintText {
                color: #b4b8ad;
                font-size: 14px;
                line-height: 140%;
            }

            QLabel#boundTag {
                background: rgba(126, 200, 164, 22);
                border: 1px solid rgba(126, 200, 164, 72);
                border-radius: 9px;
                color: #7ec8a4;
                font-size: 14px;
                font-weight: 800;
                padding: 7px 12px;
            }

            QLabel#previewBox {
                background: qradialgradient(cx:0.5, cy:0.35, radius:0.86,
                    fx:0.5, fy:0.35, stop:0 rgba(242, 118, 61, 44),
                    stop:0.48 rgba(132, 165, 157, 28), stop:1 #0f1514);
                border: 1px dashed rgba(238, 231, 219, 64);
                border-radius: 22px;
                color: #b4b8ad;
                font-size: 17px;
                min-height: 240px;
            }

            QLabel#fieldLabel {
                color: #dfe2e8;
                font-weight: 700;
                min-width: 88px;
            }

            QLabel#metricValue {
                background: rgba(238, 231, 219, 18);
                border: 1px solid rgba(238, 231, 219, 30);
                border-radius: 9px;
                color: #f4f4f2;
                font-weight: 800;
                min-width: 60px;
                padding: 4px 8px;
            }

            QLabel#previewFrameLabel {
                color: #b4b8ad;
                font-size: 13px;
                font-weight: 700;
            }

            QLabel#statusBar {
                background: rgba(20, 32, 30, 220);
                border: 1px solid rgba(238, 231, 219, 38);
                border-radius: 14px;
                color: #cdd2dc;
                padding: 14px 16px;
            }

            QLineEdit {
                background: rgba(15, 21, 20, 236);
                border: 1px solid rgba(238, 231, 219, 48);
                border-radius: 12px;
                color: #f4f4f2;
                padding: 14px 16px;
                selection-background-color: #ff7533;
            }

            QLineEdit:focus {
                border: 1px solid #ff7a38;
                background: #111216;
            }

            QComboBox#loopModeSelect {
                background: rgba(15, 21, 20, 236);
                border: 1px solid rgba(238, 231, 219, 48);
                border-radius: 11px;
                color: #f4f4f2;
                padding: 9px 12px;
                min-height: 30px;
            }

            QComboBox#loopModeSelect::drop-down {
                border: none;
                width: 24px;
            }

            QCheckBox#blackBackgroundSwitch {
                color: #f4f4f2;
                font-weight: 800;
                spacing: 10px;
            }

            QCheckBox#blackBackgroundSwitch::indicator {
                width: 42px;
                height: 22px;
                border-radius: 11px;
                background: rgba(238, 231, 219, 36);
                border: 1px solid rgba(238, 231, 219, 50);
            }

            QCheckBox#blackBackgroundSwitch::indicator:checked {
                background: #7ec8a4;
                border-color: rgba(126, 200, 164, 170);
            }

            QPushButton {
                background: rgba(238, 231, 219, 232);
                border: 1px solid rgba(255, 255, 255, 165);
                border-radius: 10px;
                color: #151719;
                font-weight: 800;
                padding: 12px 20px;
                min-height: 30px;
            }

            QPushButton:hover {
                background: #ffffff;
            }

            QPushButton:pressed {
                padding-top: 13px;
                padding-bottom: 11px;
            }

            QPushButton#orangeButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f2763d, stop:1 #f3b562);
                border-color: rgba(243, 181, 98, 160);
                color: #111111;
            }

            QPushButton#orangeButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff8a52, stop:1 #ffd088);
            }

            QPushButton#lightButton {
                background: rgba(255, 255, 255, 226);
                color: #17191c;
            }

            QPushButton#darkButton {
                background: rgba(132, 165, 157, 28);
                border-color: rgba(132, 165, 157, 82);
                color: #f4f4f2;
            }

            QPushButton#ghostButton {
                background: transparent;
                border-color: rgba(238, 231, 219, 52);
                color: #b7bdc8;
            }

            QPushButton#ghostButton:hover {
                background: rgba(255, 255, 255, 22);
                color: #f4f4f2;
            }

            QPushButton#dangerButton {
                background: rgba(255, 139, 123, 18);
                border-color: rgba(255, 139, 123, 68);
                color: #ffb0a3;
            }

            QPushButton#dangerButton:hover {
                background: rgba(255, 139, 123, 32);
            }

            QSlider::groove:horizontal {
                background: rgba(238, 231, 219, 34);
                border-radius: 6px;
                height: 12px;
            }

            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f2763d, stop:1 #7ec8a4);
                border-radius: 6px;
            }

            QSlider::handle:horizontal {
                background: #f7f2ec;
                border: 3px solid #f2763d;
                border-radius: 11px;
                width: 22px;
                margin: -7px 0;
            }
            """
        style = (
            style.replace("#0b0f10", tokens["shell"])
            .replace("#14201e", tokens["panel"])
            .replace("#24302c", tokens["card"])
            .replace("#0f1514", tokens["card_alt"])
            .replace("#394842", tokens["line"])
            .replace("#f4f4f2", tokens["text"])
            .replace("#f7f2ec", tokens["text"])
            .replace("#b4b8ad", tokens["muted"])
            .replace("#f2763d", tokens["accent"])
            .replace("#ff8a52", tokens["accent_hover"])
            .replace("#7ec8a4", tokens["success"])
            .replace("#84a59d", tokens["secondary"])
            .replace("#f3b562", tokens["amber"])
            .replace("#eee7db", tokens["chrome"])
            .replace("#ffb0a3", tokens["danger"])
        )
        self.setStyleSheet(style)
