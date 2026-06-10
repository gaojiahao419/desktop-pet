from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog,
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


STATE_MATERIALS = [
    ("idle", "待机动作", "平静待机循环"),
    ("happy", "高兴动作", "点击或切换开心时播放"),
    ("sleep", "睡觉动作", "睡觉状态循环"),
    ("angry", "生气动作", "生气状态循环"),
]


class ControlPanelWindow(QWidget):
    state_requested = pyqtSignal(str)
    say_requested = pyqtSignal(str)
    chat_requested = pyqtSignal(str)
    video_requested = pyqtSignal(str, tuple, int)
    reset_video_requested = pyqtSignal()
    state_video_requested = pyqtSignal(str, str, tuple, int)
    reset_state_video_requested = pyqtSignal(str)
    scale_requested = pyqtSignal(float)
    settings_changed = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.background_color = (0, 255, 0)
        self.current_material = "内置绘制宠物"
        self.state_material_names = {state: "未绑定，使用内置绘制" for state, _title, _hint in STATE_MATERIALS}
        self.state_material_labels = {}
        self.state_status_labels = {}
        self.setWindowTitle("桌面宠物控制面板")
        self.setMinimumSize(1180, 780)
        self.setObjectName("controlPanel")
        self._apply_style()

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(18)
        root.addWidget(self._build_title_bar())

        content = QHBoxLayout()
        content.setSpacing(22)
        content.addWidget(self._build_left_panel(), 0)
        content.addWidget(self._build_right_panel(), 1)
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
        layout.setContentsMargins(22, 12, 22, 12)

        dots = QLabel("●  ●  ●")
        dots.setObjectName("trafficDots")
        title = QLabel("桌面宠物控制面板")
        title.setObjectName("windowTitle")
        layout.addWidget(dots, 0)
        layout.addWidget(title, 1)
        return bar

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(440)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        title = QLabel("素材库")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        hint = QLabel("上传透明 MP4 时会优先读取 Alpha；没有 Alpha 时使用背景色和容差透明化。")
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
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

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

        buttons = QGridLayout()
        buttons.setSpacing(10)
        upload = QPushButton("上传 MP4")
        upload.setObjectName("orangeButton")
        switch = QPushButton("切换动作")
        switch.setObjectName("lightButton")
        reset = QPushButton("解绑素材")
        reset.setObjectName("darkButton")
        upload.clicked.connect(lambda _checked=False, value=state: self._choose_state_video(value))
        switch.clicked.connect(lambda _checked=False, value=state: self.state_requested.emit(value))
        reset.clicked.connect(lambda _checked=False, value=state: self._reset_state_video(value))
        buttons.addWidget(upload, 0, 0)
        buttons.addWidget(switch, 0, 1)
        buttons.addWidget(reset, 1, 0, 1, 2)
        layout.addLayout(buttons)
        return card

    def _build_material_card(
        self,
        title: str,
        subtitle: str,
        tag: str,
        primary_label: str,
        secondary_label: str,
        primary_callback,
        secondary_callback,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("materialCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        thumb = QLabel("MP4")
        thumb.setObjectName("thumbBadge")
        text_box = QVBoxLayout()
        name = QLabel(title)
        name.setObjectName("materialTitle")
        detail = QLabel(subtitle)
        detail.setObjectName("materialSubtitle")
        detail.setWordWrap(True)
        text_box.addWidget(name)
        text_box.addWidget(detail)
        header.addWidget(thumb, 0)
        header.addLayout(text_box, 1)
        layout.addLayout(header)

        status = QLabel(tag)
        status.setObjectName("boundTag")
        layout.addWidget(status, 0, Qt.AlignLeft)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        primary = QPushButton(primary_label)
        primary.setObjectName("orangeButton")
        secondary = QPushButton(secondary_label)
        secondary.setObjectName("lightButton")
        primary.clicked.connect(primary_callback)
        secondary.clicked.connect(secondary_callback)
        buttons.addWidget(primary)
        buttons.addWidget(secondary)
        layout.addLayout(buttons)
        return card

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("rightPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(18)

        top = QHBoxLayout()
        top.setSpacing(22)
        top.addWidget(self._build_preview_card(), 1)
        top.addWidget(self._build_settings_card(), 1)
        layout.addLayout(top, 1)
        layout.addWidget(self._build_action_card(), 0)
        layout.addWidget(self._build_dialogue_card(), 0)
        return panel

    def _build_preview_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("previewCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        title = QLabel("宠物预览")
        title.setObjectName("sectionTitle")
        preview = QLabel("宠物窗口实时显示")
        preview.setObjectName("previewBox")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumHeight(240)
        save_button = QPushButton("保存并同步")
        save_button.setObjectName("orangeButton")
        save_button.clicked.connect(lambda: self.status_label.setText("状态：设置已同步到宠物窗口"))
        layout.addWidget(title)
        layout.addWidget(preview, 1)
        layout.addWidget(save_button, 0, Qt.AlignRight)
        return card

    def _build_settings_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(22)

        size_title = QLabel("宠物大小")
        size_title.setObjectName("fieldLabel")
        self.scale_label = QLabel("100")
        self.scale_label.setObjectName("metricValue")
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(50, 250)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self._emit_scale)

        tolerance_title = QLabel("透明容差")
        tolerance_title.setObjectName("fieldLabel")
        self.tolerance_label = QLabel("35")
        self.tolerance_label.setObjectName("metricValue")
        self.tolerance_slider = QSlider(Qt.Horizontal)
        self.tolerance_slider.setRange(0, 120)
        self.tolerance_slider.setValue(35)
        self.tolerance_slider.valueChanged.connect(lambda value: self.tolerance_label.setText(str(value)))
        self.tolerance_slider.valueChanged.connect(lambda _value: self.settings_changed.emit())

        layout.addWidget(size_title, 0, 0)
        layout.addWidget(self.scale_slider, 0, 1)
        layout.addWidget(self.scale_label, 0, 2)
        layout.addWidget(tolerance_title, 1, 0)
        layout.addWidget(self.tolerance_slider, 1, 1)
        layout.addWidget(self.tolerance_label, 1, 2)
        layout.addWidget(self._build_color_row(), 2, 0, 1, 3)
        return card

    def _build_color_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("inlinePanel")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        label = QLabel("背景色")
        label.setObjectName("fieldLabel")
        buttons = [
            ("绿", (0, 255, 0), "greenButton"),
            ("白", (255, 255, 255), "lightButton"),
            ("黑", (0, 0, 0), "darkButton"),
        ]
        layout.addWidget(label)
        for text, color, object_name in buttons:
            button = QPushButton(text)
            button.setObjectName(object_name)
            button.clicked.connect(lambda _checked=False, value=color: self._set_background_color(value))
            layout.addWidget(button)
        custom = QPushButton("自定义")
        custom.setObjectName("lightButton")
        custom.clicked.connect(self._choose_color)
        layout.addWidget(custom)
        layout.addStretch(1)
        return row

    def _build_action_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        actions = [
            ("待机", "idle", "lightButton"),
            ("开心", "happy", "orangeButton"),
            ("睡觉", "sleep", "lightButton"),
            ("生气", "angry", "dangerButton"),
            ("走动", "walk", "lightButton"),
            ("隐藏", "hide", "darkButton"),
            ("显示", "show", "orangeButton"),
        ]
        for index, (label, state, object_name) in enumerate(actions):
            button = QPushButton(label)
            button.setObjectName(object_name)
            button.clicked.connect(lambda _checked=False, value=state: self.state_requested.emit(value))
            layout.addWidget(button, index // 4, index % 4)
        return card

    def _build_dialogue_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("输入要说的话或聊天内容")
        say_button = QPushButton("说话")
        say_button.setObjectName("orangeButton")
        chat_button = QPushButton("聊天")
        chat_button.setObjectName("lightButton")
        say_button.clicked.connect(lambda: self.say_requested.emit(self.text_input.text().strip()))
        chat_button.clicked.connect(lambda: self.chat_requested.emit(self.text_input.text().strip()))

        layout.addWidget(self.text_input, 0, 0, 1, 2)
        layout.addWidget(say_button, 1, 0)
        layout.addWidget(chat_button, 1, 1)
        return card

    def _choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 MP4 素材", "", "MP4 视频 (*.mp4)")
        if not path:
            return
        self.current_material = Path(path).name
        self.status_label.setText(f"状态：已选择 {self.current_material}")
        self.video_requested.emit(path, self.background_color, self.tolerance_slider.value())

    def _choose_state_video(self, state: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择动作 MP4 素材", "", "MP4 视频 (*.mp4)")
        if not path:
            return
        self.set_state_material_loading(state, path)
        self.state_video_requested.emit(state, path, self.background_color, self.tolerance_slider.value())

    def _reset_video(self) -> None:
        self.current_material = "内置绘制宠物"
        self.status_label.setText("状态：使用内置绘制宠物")
        self.reset_video_requested.emit()

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

    def set_state_material_loaded(self, state: str, path: str) -> None:
        material_name = Path(path).name
        self.state_material_names[state] = material_name
        self.state_material_labels[state].setText(material_name)
        self.state_status_labels[state].setText("已绑定：动作素材")
        self.status_label.setText(f"状态：{self._state_title(state)} 已绑定 {material_name}")

    def set_state_material_failed(self, state: str, path: str, error: str) -> None:
        material_name = Path(path).name
        self.state_material_labels[state].setText(f"{material_name} 加载失败")
        self.state_status_labels[state].setText("加载失败：检查素材")
        self.status_label.setText(f"状态：{self._state_title(state)} 素材加载失败：{error}")

    def _set_background_color(self, color: tuple) -> None:
        self.background_color = color
        self.status_label.setText(f"状态：背景色已设置为 RGB{color}")
        self.settings_changed.emit()

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(QColor(*self.background_color), self, "选择背景色")
        if color.isValid():
            self._set_background_color((color.red(), color.green(), color.blue()))

    def _emit_scale(self, value: int) -> None:
        self.scale_label.setText(str(value))
        self.scale_requested.emit(value / 100)

    def set_status(self, text: str) -> None:
        self.status_label.setText(f"状态：{text}")

    def apply_settings(
        self,
        background_color: tuple,
        tolerance: int,
        scale: float,
        state_materials: dict,
    ) -> None:
        self.background_color = background_color
        self.tolerance_slider.setValue(tolerance)
        self.scale_slider.setValue(int(scale * 100))
        for state, path in state_materials.items():
            if state in self.state_material_labels:
                material_name = Path(path).name
                self.state_material_names[state] = material_name
                self.state_material_labels[state].setText(material_name)
                self.state_status_labels[state].setText("已保存：启动后加载")

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#controlPanel {
                background: #101114;
                color: #f4f4f2;
                font-family: "Microsoft YaHei", "Segoe UI";
                font-size: 15px;
            }

            QFrame#titleBar {
                background: #f1eeee;
                border-radius: 14px;
            }

            QLabel#trafficDots {
                color: #f15b48;
                font-size: 14px;
                letter-spacing: 2px;
            }

            QLabel#windowTitle {
                color: #222222;
                font-weight: 700;
            }

            QFrame#leftPanel,
            QFrame#rightPanel {
                background: #15171b;
                border: 1px solid #25282f;
                border-radius: 14px;
            }

            QScrollArea#materialScroll {
                background: transparent;
                border: 0;
            }

            QWidget#materialScrollContent {
                background: transparent;
            }

            QScrollBar:vertical {
                background: #15171b;
                border: 0;
                width: 8px;
            }

            QScrollBar::handle:vertical {
                background: #333844;
                border-radius: 4px;
            }

            QLabel#sectionTitle {
                color: #ffffff;
                font-size: 19px;
                font-weight: 800;
            }

            QFrame#materialCard,
            QFrame#settingsCard,
            QFrame#previewCard {
                background: #1d2026;
                border: 1px solid #2a2d35;
                border-radius: 12px;
            }

            QLabel#thumbBadge {
                background: #2a2d35;
                border: 1px solid #393d48;
                border-radius: 10px;
                color: #f4f4f2;
                font-weight: 800;
                min-width: 62px;
                min-height: 62px;
                qproperty-alignment: AlignCenter;
            }

            QLabel#materialTitle {
                color: #ffffff;
                font-weight: 800;
            }

            QLabel#materialSubtitle,
            QLabel#hintText {
                color: #a9adb8;
                font-size: 14px;
            }

            QLabel#boundTag {
                background: #18493a;
                border-radius: 7px;
                color: #52e3ad;
                font-size: 14px;
                font-weight: 800;
                padding: 6px 12px;
            }

            QLabel#previewBox {
                background: #111216;
                border: 1px dashed #333846;
                border-radius: 14px;
                color: #878d9b;
                font-size: 17px;
                min-height: 240px;
            }

            QLabel#fieldLabel {
                color: #dfe2e8;
                font-weight: 700;
                min-width: 88px;
            }

            QLabel#metricValue {
                color: #f4f4f2;
                font-weight: 800;
                min-width: 58px;
            }

            QLabel#statusBar {
                background: #171a20;
                border: 1px solid #2b303a;
                border-radius: 11px;
                color: #cdd2dc;
                padding: 14px 16px;
            }

            QLineEdit {
                background: #111216;
                border: 1px solid #323743;
                border-radius: 9px;
                color: #f4f4f2;
                padding: 14px 16px;
                selection-background-color: #ff7533;
            }

            QLineEdit:focus {
                border: 1px solid #ff7a38;
            }

            QPushButton {
                background: #ececec;
                border: 1px solid #ffffff;
                border-radius: 8px;
                color: #171717;
                font-weight: 800;
                padding: 12px 20px;
                min-height: 30px;
            }

            QPushButton:hover {
                background: #ffffff;
            }

            QPushButton#orangeButton {
                background: #ff7432;
                border-color: #ff9a68;
                color: #111111;
            }

            QPushButton#orangeButton:hover {
                background: #ff8a50;
            }

            QPushButton#lightButton {
                background: #f2f2f2;
                color: #171717;
            }

            QPushButton#darkButton {
                background: #2b2f38;
                border-color: #3c414d;
                color: #f4f4f2;
            }

            QPushButton#greenButton {
                background: #dff8e9;
                border-color: #b7e8c8;
                color: #12623b;
            }

            QPushButton#dangerButton {
                background: #351a1a;
                border-color: #6b2d2d;
                color: #ffb0a3;
            }

            QPushButton#dangerButton:hover {
                background: #4a2222;
            }

            QSlider::groove:horizontal {
                background: #343943;
                border-radius: 6px;
                height: 12px;
            }

            QSlider::sub-page:horizontal {
                background: #34d1a0;
                border-radius: 6px;
            }

            QSlider::handle:horizontal {
                background: #34d1a0;
                border: 1px solid #55ecc0;
                border-radius: 11px;
                width: 22px;
                margin: -7px 0;
            }
            """
        )
