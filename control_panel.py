from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
        self.setWindowTitle("桌面宠物控制台")
        self.setMinimumWidth(430)
        self.setObjectName("controlPanel")
        self._apply_style()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        root.addWidget(self._build_header())
        root.addWidget(self._build_material_group())
        root.addWidget(self._build_transparency_group())
        root.addWidget(self._build_size_group())
        root.addWidget(self._build_action_group())
        root.addWidget(self._build_dialogue_group())

        self.status_label = QLabel("当前素材：内置绘制宠物")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        quit_button = QPushButton("退出程序")
        quit_button.setObjectName("dangerButton")
        quit_button.clicked.connect(self.quit_requested.emit)
        root.addWidget(quit_button)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("headerCard")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        title = QLabel("桌面宠物控制台")
        title.setObjectName("titleLabel")
        subtitle = QLabel("上传素材、调整大小，或者让宠物陪你说两句。")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def _build_material_group(self) -> QGroupBox:
        group = self._card("素材")
        layout = QGridLayout(group)
        layout.setContentsMargins(14, 22, 14, 14)
        layout.setSpacing(10)

        upload_button = QPushButton("上传 MP4")
        upload_button.setObjectName("primaryButton")
        reset_button = QPushButton("恢复默认")
        upload_button.clicked.connect(self._choose_video)
        reset_button.clicked.connect(self._reset_video)
        layout.addWidget(upload_button, 0, 0)
        layout.addWidget(reset_button, 0, 1)
        return group

    def _build_transparency_group(self) -> QGroupBox:
        group = self._card("透明设置")
        layout = QGridLayout(group)
        layout.setContentsMargins(14, 22, 14, 14)
        layout.setSpacing(10)

        green_button = QPushButton("绿色")
        white_button = QPushButton("白色")
        black_button = QPushButton("黑色")
        custom_button = QPushButton("自定义")
        green_button.setProperty("tone", "green")
        white_button.setProperty("tone", "light")
        black_button.setProperty("tone", "dark")
        custom_button.setObjectName("secondaryButton")

        green_button.clicked.connect(lambda: self._set_background_color((0, 255, 0)))
        white_button.clicked.connect(lambda: self._set_background_color((255, 255, 255)))
        black_button.clicked.connect(lambda: self._set_background_color((0, 0, 0)))
        custom_button.clicked.connect(self._choose_color)

        self.tolerance_slider = QSlider(Qt.Horizontal)
        self.tolerance_slider.setRange(0, 120)
        self.tolerance_slider.setValue(35)
        self.tolerance_label = QLabel("容差：35")
        self.tolerance_label.setObjectName("valueLabel")
        self.tolerance_slider.valueChanged.connect(lambda value: self.tolerance_label.setText(f"容差：{value}"))

        layout.addWidget(green_button, 0, 0)
        layout.addWidget(white_button, 0, 1)
        layout.addWidget(black_button, 0, 2)
        layout.addWidget(custom_button, 0, 3)
        layout.addWidget(self.tolerance_label, 1, 0)
        layout.addWidget(self.tolerance_slider, 1, 1, 1, 3)
        return group

    def _build_size_group(self) -> QGroupBox:
        group = self._card("大小")
        layout = QGridLayout(group)
        layout.setContentsMargins(14, 22, 14, 14)
        layout.setSpacing(10)

        self.scale_label = QLabel("大小：100%")
        self.scale_label.setObjectName("valueLabel")
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(50, 250)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self._emit_scale)
        layout.addWidget(self.scale_label, 0, 0)
        layout.addWidget(self.scale_slider, 0, 1)
        return group

    def _build_action_group(self) -> QGroupBox:
        group = self._card("动作")
        layout = QGridLayout(group)
        layout.setContentsMargins(14, 22, 14, 14)
        layout.setSpacing(10)

        actions = [
            ("待机", "idle", "soft"),
            ("开心", "happy", "warm"),
            ("睡觉", "sleep", "cool"),
            ("走动", "walk", "green"),
            ("隐藏", "hide", "muted"),
            ("显示", "show", "primary"),
        ]
        for index, (label, state, tone) in enumerate(actions):
            button = QPushButton(label)
            button.setProperty("tone", tone)
            button.clicked.connect(lambda _checked=False, value=state: self.state_requested.emit(value))
            layout.addWidget(button, index // 3, index % 3)
        return group

    def _build_dialogue_group(self) -> QGroupBox:
        group = self._card("对话")
        layout = QGridLayout(group)
        layout.setContentsMargins(14, 22, 14, 14)
        layout.setSpacing(10)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("输入要说的话或聊天内容")
        say_button = QPushButton("说话")
        chat_button = QPushButton("聊天")
        say_button.setObjectName("primaryButton")
        chat_button.setObjectName("secondaryButton")
        say_button.clicked.connect(lambda: self.say_requested.emit(self.text_input.text().strip()))
        chat_button.clicked.connect(lambda: self.chat_requested.emit(self.text_input.text().strip()))

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addWidget(say_button)
        button_row.addWidget(chat_button)

        layout.addWidget(self.text_input, 0, 0)
        layout.addLayout(button_row, 1, 0)
        return group

    def _card(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setObjectName("card")
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

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#controlPanel {
                background: #fff7fb;
                color: #3b3140;
                font-family: "Microsoft YaHei", "Segoe UI";
                font-size: 13px;
            }

            QFrame#headerCard {
                background: #ffe8f1;
                border: 1px solid #ffd0df;
                border-radius: 12px;
            }

            QLabel#titleLabel {
                color: #35283b;
                font-size: 20px;
                font-weight: 700;
            }

            QLabel#subtitleLabel {
                color: #7b687f;
                font-size: 12px;
            }

            QGroupBox#card {
                background: #ffffff;
                border: 1px solid #f0dbe6;
                border-radius: 12px;
                margin-top: 10px;
                font-weight: 700;
                color: #5d4565;
            }

            QGroupBox#card::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #8f5f78;
            }

            QLabel#valueLabel {
                color: #5d4565;
                font-weight: 700;
                min-width: 72px;
            }

            QLabel#statusLabel {
                background: #fffdf7;
                border: 1px solid #f1deba;
                border-radius: 10px;
                color: #6a5b3c;
                padding: 10px 12px;
            }

            QLineEdit {
                background: #fffafd;
                border: 1px solid #efd7e4;
                border-radius: 10px;
                padding: 9px 11px;
                selection-background-color: #ffb8d0;
            }

            QLineEdit:focus {
                border: 1px solid #ec7ca5;
                background: #ffffff;
            }

            QPushButton {
                background: #f4f2fb;
                border: 1px solid #ddd7f2;
                border-radius: 10px;
                color: #473b57;
                font-weight: 600;
                padding: 9px 12px;
                min-height: 18px;
            }

            QPushButton:hover {
                background: #eee9fb;
            }

            QPushButton:pressed {
                background: #e1d8f6;
            }

            QPushButton#primaryButton,
            QPushButton[tone="primary"] {
                background: #ff8fb8;
                border-color: #f0719e;
                color: #ffffff;
            }

            QPushButton#primaryButton:hover,
            QPushButton[tone="primary"]:hover {
                background: #ff7aaa;
            }

            QPushButton#secondaryButton,
            QPushButton[tone="cool"] {
                background: #eaf3ff;
                border-color: #cfe3fb;
                color: #376083;
            }

            QPushButton[tone="warm"] {
                background: #fff0cc;
                border-color: #f3d681;
                color: #7a5a1f;
            }

            QPushButton[tone="green"] {
                background: #e7f8e9;
                border-color: #bfe8c5;
                color: #356c42;
            }

            QPushButton[tone="soft"] {
                background: #fff4fa;
                border-color: #f4d3e5;
                color: #7a4c68;
            }

            QPushButton[tone="muted"] {
                background: #f1f1f3;
                border-color: #d9d9df;
                color: #5c5c66;
            }

            QPushButton[tone="light"] {
                background: #ffffff;
                border-color: #dddddd;
                color: #555555;
            }

            QPushButton[tone="dark"] {
                background: #47434d;
                border-color: #36323c;
                color: #ffffff;
            }

            QPushButton#dangerButton {
                background: #fff0f0;
                border-color: #f0c5c5;
                color: #9b3d3d;
            }

            QPushButton#dangerButton:hover {
                background: #ffe3e3;
            }

            QSlider::groove:horizontal {
                background: #f2e5ef;
                border-radius: 4px;
                height: 8px;
            }

            QSlider::sub-page:horizontal {
                background: #ff9fc1;
                border-radius: 4px;
            }

            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #ff8fb8;
                border-radius: 8px;
                width: 16px;
                margin: -5px 0;
            }
            """
        )
