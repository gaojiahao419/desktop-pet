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
        actions = [
            ("待机", "idle"),
            ("开心", "happy"),
            ("睡觉", "sleep"),
            ("走动", "walk"),
            ("隐藏", "hide"),
            ("显示", "show"),
        ]
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
