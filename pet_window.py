from collections import OrderedDict

from PyQt5.QtCore import QEasingCurve, QPoint, QParallelAnimationGroup, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget
from PIL import Image

from dialogue import LocalDialogue
from pet_animator import PetAnimator, VALID_STATES
from pet_renderer import PetRenderer
from video_pet_source import LOOP_MODE_LOOP, VideoPetSource, clamp_playback_speed, clamp_scale, normalize_loop_mode


DEFAULT_ANIMATION_INTERVAL_MS = 60
RIGHT_CLICK_MENU_WIDTH = 236
RIGHT_CLICK_MENU_MARGIN = 12
RIGHT_CLICK_MENU_ANIMATION_DURATION_MS = 180
RIGHT_CLICK_MENU_SLIDE_OFFSET_Y = 12
RIGHT_CLICK_MENU_DESIGN_TOKENS = {
    "panel": "#f8fbff",
    "line": "#bfdbfe",
    "button": "#ffffff",
    "text": "#0f172a",
    "muted": "#64748b",
    "action_accent": "#2563eb",
    "dialogue_accent": "#2563eb",
    "utility_accent": "#2563eb",
}
CHAT_DIALOG_DEFAULT_SIZE = (560, 640)
CHAT_DIALOG_MARGIN = 16

RIGHT_CLICK_STATE_ACTIONS = []

RIGHT_CLICK_DIALOGUE_ACTIONS = []

RIGHT_CLICK_UTILITY_ACTIONS = [
    ("打开对话", "open_chat"),
    ("打开控制台", "open_control_panel"),
]


def right_click_menu_animation_config() -> dict:
    return {
        "duration_ms": RIGHT_CLICK_MENU_ANIMATION_DURATION_MS,
        "start_opacity": 0.0,
        "end_opacity": 1.0,
        "slide_offset_y": RIGHT_CLICK_MENU_SLIDE_OFFSET_Y,
    }


def right_click_menu_design_tokens() -> dict:
    return dict(RIGHT_CLICK_MENU_DESIGN_TOKENS)


def clamp_popup_position(point: tuple, popup_size: tuple, screen_rect: tuple, margin: int = RIGHT_CLICK_MENU_MARGIN) -> tuple:
    x, y = point
    popup_width, popup_height = popup_size
    screen_left, screen_top, screen_width, screen_height = screen_rect
    min_x = screen_left + margin
    min_y = screen_top + margin
    max_x = screen_left + screen_width - margin - popup_width
    max_y = screen_top + screen_height - margin - popup_height
    return max(min_x, min(x, max_x)), max(min_y, min(y, max_y))


def popup_anchor_offset(pet_position: tuple, popup_position: tuple) -> tuple:
    pet_x, pet_y = pet_position
    popup_x, popup_y = popup_position
    return popup_x - pet_x, popup_y - pet_y


def popup_position_from_anchor(pet_position: tuple, anchor_offset: tuple) -> tuple:
    pet_x, pet_y = pet_position
    offset_x, offset_y = anchor_offset
    return pet_x + offset_x, pet_y + offset_y


def chat_dialog_position_for_pet(
    pet_position: tuple,
    pet_size: tuple,
    dialog_size: tuple,
    screen_rect: tuple,
    margin: int = CHAT_DIALOG_MARGIN,
) -> tuple:
    pet_x, pet_y = pet_position
    pet_width, pet_height = pet_size
    dialog_width, dialog_height = dialog_size
    screen_left, screen_top, screen_width, screen_height = screen_rect
    preferred_x = pet_x + pet_width + margin
    preferred_y = pet_y + (pet_height - dialog_height) // 2
    if preferred_x + dialog_width + margin > screen_left + screen_width:
        preferred_x = pet_x - dialog_width - margin
    return clamp_popup_position(
        point=(preferred_x, preferred_y),
        popup_size=(dialog_width, dialog_height),
        screen_rect=(screen_left, screen_top, screen_width, screen_height),
        margin=margin,
    )


def select_video_source_for_state(state: str, state_sources: dict, default_source):
    return state_sources.get(state) or default_source


def scaled_dimensions(size: tuple, scale: float) -> tuple:
    width, height = size
    scale = clamp_scale(scale)
    return max(1, int(width * scale)), max(1, int(height * scale))


def display_dimension(base_size: int, scale: float) -> int:
    return max(1, int(base_size * clamp_scale(scale)))


def select_scale_for_state(state: str, state_scales: dict, default_scale: float) -> float:
    return clamp_scale(state_scales.get(state, default_scale))


def select_playback_speed_for_state(state: str, state_speeds: dict, default_speed: float) -> float:
    return clamp_playback_speed(state_speeds.get(state, default_speed))


def select_loop_mode_for_state(state: str, state_loop_modes: dict, default_loop_mode: str) -> str:
    return normalize_loop_mode(state_loop_modes.get(state, default_loop_mode))


def timer_interval_for_source(source, playback_speed: float = 1.0) -> int:
    if source is None:
        return DEFAULT_ANIMATION_INTERVAL_MS
    return source.frame_interval_ms(playback_speed=playback_speed)


class AnimatedRightClickMenu(QWidget):
    def __init__(self, state_callback, dialogue_callback, utility_callback, parent=None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.Tool)
        self.state_callback = state_callback
        self.dialogue_callback = dialogue_callback
        self.utility_callback = utility_callback
        self._animation_group = None
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedWidth(RIGHT_CLICK_MENU_WIDTH)
        self.setObjectName("rightClickMenuWindow")
        self.setFont(QFont("Microsoft YaHei UI", 10))
        self._build_ui()
        self._apply_style()

    def show_at(self, global_pos: QPoint) -> QPoint:
        self.adjustSize()
        final_pos = self._clamped_position(global_pos)
        config = right_click_menu_animation_config()
        start_pos = QPoint(final_pos.x(), final_pos.y() + config["slide_offset_y"])

        self.move(start_pos)
        self.setWindowOpacity(config["start_opacity"])
        self.show()
        self.raise_()

        pos_animation = QPropertyAnimation(self, b"pos", self)
        pos_animation.setDuration(config["duration_ms"])
        pos_animation.setStartValue(start_pos)
        pos_animation.setEndValue(final_pos)
        pos_animation.setEasingCurve(QEasingCurve.OutCubic)

        opacity_animation = QPropertyAnimation(self, b"windowOpacity", self)
        opacity_animation.setDuration(config["duration_ms"])
        opacity_animation.setStartValue(config["start_opacity"])
        opacity_animation.setEndValue(config["end_opacity"])
        opacity_animation.setEasingCurve(QEasingCurve.OutCubic)

        self._animation_group = QParallelAnimationGroup(self)
        self._animation_group.addAnimation(pos_animation)
        self._animation_group.addAnimation(opacity_animation)
        self._animation_group.start()
        return final_pos

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        panel = QFrame(self)
        panel.setObjectName("rightClickMenuPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("快捷入口", self)
        title.setObjectName("rightClickMenuTitle")
        subtitle = QLabel("对话 / 控制台", self)
        subtitle.setObjectName("rightClickMenuSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        if RIGHT_CLICK_STATE_ACTIONS:
            self._add_caption(layout, "动作")
            for label, state in RIGHT_CLICK_STATE_ACTIONS:
                self._add_button(layout, label, self.state_callback, state, "state")

        if RIGHT_CLICK_DIALOGUE_ACTIONS:
            self._add_divider(layout)
            self._add_caption(layout, "对话")
            for label, action_key in RIGHT_CLICK_DIALOGUE_ACTIONS:
                self._add_button(layout, label, self.dialogue_callback, action_key, "dialogue")

        if RIGHT_CLICK_STATE_ACTIONS or RIGHT_CLICK_DIALOGUE_ACTIONS:
            self._add_divider(layout)
        self._add_caption(layout, "更多")
        for label, action_key in RIGHT_CLICK_UTILITY_ACTIONS:
            self._add_button(layout, label, self.utility_callback, action_key, "utility")

        root.addWidget(panel)

    def _add_caption(self, layout: QVBoxLayout, text: str) -> None:
        label = QLabel(text, self)
        label.setObjectName("rightClickMenuCaption")
        layout.addWidget(label)

    def _add_button(self, layout: QVBoxLayout, label: str, callback, value: str, role: str) -> None:
        button = QPushButton(label, self)
        button.setObjectName("rightClickMenuButton")
        button.setProperty("menuRole", role)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, cb=callback, item=value: self._trigger(cb, item))
        layout.addWidget(button)

    def _add_divider(self, layout: QVBoxLayout) -> None:
        divider = QFrame(self)
        divider.setObjectName("rightClickMenuDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

    def _trigger(self, callback, value: str) -> None:
        self.close()
        callback(value)

    def _clamped_position(self, global_pos: QPoint) -> QPoint:
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        if screen is None:
            return global_pos
        rect = screen.availableGeometry()
        x, y = clamp_popup_position(
            point=(global_pos.x(), global_pos.y()),
            popup_size=(self.width(), self.height()),
            screen_rect=(rect.left(), rect.top(), rect.width(), rect.height()),
        )
        return QPoint(x, y)

    def _apply_style(self) -> None:
        tokens = right_click_menu_design_tokens()
        style = """
            QWidget#rightClickMenuWindow {
                background: transparent;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
            }

            QFrame#rightClickMenuPanel {
                background: #f8fbff;
                border: 1px solid #bfdbfe;
                border-radius: 14px;
            }

            QLabel#rightClickMenuTitle {
                color: #0f172a;
                font-size: 15px;
                font-weight: 800;
                padding: 2px 8px 0 8px;
            }

            QLabel#rightClickMenuSubtitle {
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
                padding: 0 8px 6px 8px;
            }

            QLabel#rightClickMenuCaption {
                color: #64748b;
                font-size: 12px;
                font-weight: 700;
                padding: 6px 8px 2px 8px;
            }

            QPushButton#rightClickMenuButton {
                background: #ffffff;
                border: 1px solid #dbeafe;
                border-radius: 10px;
                color: #0f172a;
                font-weight: 700;
                min-height: 38px;
                padding: 8px 12px;
                text-align: left;
            }

            QPushButton#rightClickMenuButton[menuRole="state"] {
                border-left: 4px solid #f2763d;
            }

            QPushButton#rightClickMenuButton[menuRole="dialogue"] {
                border-left: 4px solid #7ec8a4;
            }

            QPushButton#rightClickMenuButton[menuRole="utility"] {
                border-left: 4px solid #2563eb;
            }

            QPushButton#rightClickMenuButton[menuRole="state"]:hover {
                background: rgba(242, 118, 61, 50);
                border-color: rgba(242, 118, 61, 162);
                color: #ffffff;
            }

            QPushButton#rightClickMenuButton[menuRole="dialogue"]:hover {
                background: rgba(126, 200, 164, 46);
                border-color: rgba(126, 200, 164, 158);
                color: #ffffff;
            }

            QPushButton#rightClickMenuButton[menuRole="utility"]:hover {
                background: #eff6ff;
                border-color: #60a5fa;
                color: #1d4ed8;
            }

            QPushButton#rightClickMenuButton:pressed {
                padding-top: 9px;
                padding-bottom: 7px;
            }

            QFrame#rightClickMenuDivider {
                background: #dbeafe;
                border: none;
                margin: 6px 4px;
            }
            """
        style = (
            style.replace("#f8fbff", tokens["panel"])
            .replace("#bfdbfe", tokens["line"])
            .replace("#ffffff", tokens["button"])
            .replace("#0f172a", tokens["text"])
            .replace("#64748b", tokens["muted"])
            .replace("#f2763d", tokens["action_accent"])
            .replace("#7ec8a4", tokens["dialogue_accent"])
            .replace("#2563eb", tokens["utility_accent"])
        )
        self.setStyleSheet(style)


class PetChatDialog(QDialog):
    message_submitted = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._messages = []
        self.setWindowTitle("和宠物聊天")
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self.setMinimumSize(520, 600)
        self.resize(*CHAT_DIALOG_DEFAULT_SIZE)
        self.setObjectName("petChatDialog")
        self.setFont(QFont("Microsoft YaHei UI", 11))
        self._build_ui()
        self._apply_style()

    def append_user_message(self, text: str) -> None:
        self._append_message("你", text, "user")

    def append_assistant_message(self, text: str) -> None:
        self._append_message("宠物", text, "assistant")
        self.status_label.setText("就绪")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("和宠物聊天", self)
        title.setObjectName("chatTitle")
        title.setFont(QFont("Microsoft YaHei UI", 17, QFont.Bold))
        self.status_label = QLabel("输入内容后发送给本地模型", self)
        self.status_label.setObjectName("chatStatus")
        self.status_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Medium))

        self.history_scroll = QScrollArea(self)
        self.history_scroll.setObjectName("chatHistoryScroll")
        self.history_scroll.setWidgetResizable(True)
        self.history_content = QWidget(self.history_scroll)
        self.history_content.setObjectName("chatHistoryContent")
        self.history_layout = QVBoxLayout(self.history_content)
        self.history_layout.setContentsMargins(12, 12, 12, 12)
        self.history_layout.setSpacing(12)
        self.history_layout.addStretch(1)
        self.history_scroll.setWidget(self.history_content)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input_field = QLineEdit(self)
        self.input_field.setObjectName("chatInput")
        self.input_field.setPlaceholderText("输入要对宠物说的话")
        self.input_field.setFixedHeight(58)
        self.input_field.setFont(QFont("Microsoft YaHei UI", 13))
        self.send_button = QPushButton("发送", self)
        self.send_button.setObjectName("chatSendButton")
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setFixedSize(104, 58)
        self.send_button.setFont(QFont("Microsoft YaHei UI", 13, QFont.Bold))
        self.send_button.clicked.connect(self._submit_message)
        self.input_field.returnPressed.connect(self._submit_message)
        input_row.addWidget(self.input_field, 1)
        input_row.addWidget(self.send_button)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.history_scroll, 1)
        layout.addLayout(input_row)

    def _submit_message(self) -> None:
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.append_user_message(text)
        self.status_label.setText("宠物正在思考...")
        self.message_submitted.emit(text)

    def _append_message(self, speaker: str, text: str, role: str) -> None:
        self._messages.append((speaker, text, role))
        self._add_message_bubble(speaker, text, role)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _add_message_bubble(self, speaker: str, text: str, role: str) -> None:
        row = QWidget(self.history_content)
        row.setObjectName("chatMessageRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        bubble = QFrame(row)
        bubble.setObjectName("userBubble" if role == "user" else "assistantBubble")
        bubble.setMinimumWidth(230 if role == "user" else 320)
        bubble.setMaximumWidth(430)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 13, 16, 13)
        bubble_layout.setSpacing(6)

        speaker_label = QLabel(speaker, bubble)
        speaker_label.setObjectName("userSpeaker" if role == "user" else "assistantSpeaker")
        speaker_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        message_label = QLabel(text, bubble)
        message_label.setObjectName("userMessage" if role == "user" else "assistantMessage")
        message_label.setFont(QFont("Microsoft YaHei UI", 13, QFont.Medium))
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        bubble_layout.addWidget(speaker_label)
        bubble_layout.addWidget(message_label)

        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
        else:
            row_layout.addWidget(bubble, 0, Qt.AlignLeft)
            row_layout.addStretch(1)

        self.history_layout.insertWidget(self.history_layout.count() - 1, row)

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.history_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog#petChatDialog {
                background: #f8fbff;
                color: #0f172a;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
            }
            QLabel#chatTitle {
                color: #0f172a;
                font-size: 23px;
                font-weight: 800;
            }
            QLabel#chatStatus {
                color: #64748b;
                font-size: 14px;
                font-weight: 700;
            }
            QScrollArea#chatHistoryScroll {
                background: #eef6ff;
                border: 1px solid #bfdbfe;
                border-radius: 10px;
                color: #0f172a;
            }
            QScrollArea#chatHistoryScroll QWidget#chatHistoryContent {
                background: #eef6ff;
            }
            QWidget#chatMessageRow {
                background: transparent;
            }
            QFrame#assistantBubble {
                background: #ffffff;
                border: 1px solid #bfdbfe;
                border-radius: 12px;
            }
            QFrame#userBubble {
                background: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 12px;
            }
            QLabel#assistantSpeaker {
                color: #2563eb;
                font-size: 14px;
                font-weight: 800;
            }
            QLabel#userSpeaker {
                color: #bfdbfe;
                font-size: 14px;
                font-weight: 800;
            }
            QLabel#assistantMessage {
                color: #0f172a;
                font-size: 17px;
                font-weight: 500;
            }
            QLabel#userMessage {
                color: #ffffff;
                font-size: 17px;
                font-weight: 500;
            }
            QLineEdit#chatInput {
                background: #ffffff;
                border: 1px solid #bfdbfe;
                border-radius: 10px;
                color: #0f172a;
                min-height: 58px;
                padding: 0 16px;
                font-size: 18px;
            }
            QLineEdit#chatInput:focus {
                border: 1px solid #2563eb;
            }
            QPushButton#chatSendButton {
                background: #2563eb;
                border: none;
                border-radius: 10px;
                color: #ffffff;
                font-weight: 800;
                min-width: 104px;
                min-height: 58px;
                font-size: 18px;
            }
            QPushButton#chatSendButton:hover {
                background: #1d4ed8;
            }
            """
        )


class PetWindow(QWidget):
    control_panel_requested = pyqtSignal()
    chat_requested = pyqtSignal(str)

    def __init__(self, animator: PetAnimator, dialogue: LocalDialogue) -> None:
        super().__init__()
        self.animator = animator
        self.dialogue = dialogue
        self.renderer = PetRenderer()
        self.video_source = None
        self.state_video_sources = {}
        self._pixmap_cache = OrderedDict()
        self._max_pixmap_cache_items = 180
        self._timer_interval_ms = DEFAULT_ANIMATION_INTERVAL_MS
        self._right_click_menu = None
        self._right_click_menu_anchor = None
        self._chat_dialog = None
        self.scale = 1.0
        self.state_scales = {}
        self.state_playback_speeds = {}
        self.state_loop_modes = {}
        self.base_size = 220
        self.image_label = QLabel(self)
        self.image_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.image_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.drag_start = QPoint()
        self.dragging = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._apply_scaled_size()
        self.move(1200, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.image_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_frame)
        self.timer.start(self._timer_interval_ms)
        self.refresh_frame()

    def refresh_frame(self) -> None:
        frame = self.animator.advance()
        video_source = select_video_source_for_state(frame.state, self.state_video_sources, self.video_source)
        scale = self.scale_for_state(frame.state)
        playback_speed = self.playback_speed_for_state(frame.state)
        loop_mode = self.loop_mode_for_state(frame.state)
        self._sync_timer_interval(video_source, playback_speed)
        if video_source is not None:
            self._apply_scaled_size(video_source.size, scale)
            pixmap = self._next_video_pixmap(video_source, scale, self.animator.speech_text, loop_mode)
        else:
            self._apply_scaled_size(scale=scale)
            image = self.renderer.render(frame, self.animator.speech_text)
            image = self._resize_image(image, scale)
            qimage = self._pil_to_qimage(image)
            pixmap = QPixmap.fromImage(qimage)
        self.image_label.setPixmap(pixmap)

        if frame.state == "walk":
            pos = self.pos()
            next_x = max(20, pos.x() + frame.walk_dx)
            self.move(next_x, pos.y())

    def set_state(self, state: str) -> None:
        self.animator.set_state(state)
        source = self.video_source_for_state(state)
        if source is not None:
            source.reset()
        self.show_pet()

    def set_video_source(self, source: VideoPetSource) -> None:
        self.video_source = source
        self._pixmap_cache.clear()
        self.show_pet()

    def clear_video_source(self) -> None:
        self.video_source = None
        self._pixmap_cache.clear()
        self.show_pet()

    def set_state_video_source(self, state: str, source: VideoPetSource) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported pet state: {state}")
        self.state_video_sources[state] = source
        self._pixmap_cache.clear()
        self.show_pet()

    def clear_state_video_source(self, state: str) -> None:
        self.state_video_sources.pop(state, None)
        self._pixmap_cache.clear()
        self.show_pet()

    def video_source_for_state(self, state: str):
        return select_video_source_for_state(state, self.state_video_sources, self.video_source)

    def set_scale(self, scale: float) -> None:
        old_pos = self.pos()
        self.scale = clamp_scale(scale)
        self._apply_scaled_size(self._current_video_size())
        self._pixmap_cache.clear()
        self.move(old_pos)
        self.refresh_frame()

    def set_state_scale(self, state: str, scale: float) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported pet state: {state}")
        old_pos = self.pos()
        self.state_scales[state] = clamp_scale(scale)
        self._apply_scaled_size(self._current_video_size(), self.scale_for_state(self.animator.state))
        self._pixmap_cache.clear()
        self.move(old_pos)
        self.refresh_frame()

    def set_state_scales(self, state_scales: dict) -> None:
        self.state_scales = {str(state): clamp_scale(scale) for state, scale in state_scales.items()}
        self._pixmap_cache.clear()
        self.refresh_frame()

    def scale_for_state(self, state: str) -> float:
        return select_scale_for_state(state, self.state_scales, self.scale)

    def set_state_playback_speed(self, state: str, speed: float) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported pet state: {state}")
        self.state_playback_speeds[state] = clamp_playback_speed(speed)
        self._sync_timer_interval(self._current_video_source(), self.playback_speed_for_state(self.animator.state))
        self.refresh_frame()

    def set_state_playback_speeds(self, state_speeds: dict) -> None:
        self.state_playback_speeds = {
            str(state): clamp_playback_speed(speed)
            for state, speed in state_speeds.items()
        }
        self.refresh_frame()

    def playback_speed_for_state(self, state: str) -> float:
        return select_playback_speed_for_state(state, self.state_playback_speeds, 1.0)

    def set_state_loop_mode(self, state: str, loop_mode: str) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported pet state: {state}")
        self.state_loop_modes[state] = normalize_loop_mode(loop_mode)
        source = self.video_source_for_state(state)
        if source is not None:
            source.reset()
        self.refresh_frame()

    def set_state_loop_modes(self, state_loop_modes: dict) -> None:
        self.state_loop_modes = {
            str(state): normalize_loop_mode(loop_mode)
            for state, loop_mode in state_loop_modes.items()
        }
        self.refresh_frame()

    def loop_mode_for_state(self, state: str) -> str:
        return select_loop_mode_for_state(state, self.state_loop_modes, LOOP_MODE_LOOP)

    def say(self, text: str, preserve_state: bool = True) -> None:
        self.animator.say(text, preserve_state=preserve_state)
        self.show()
        self.raise_()

    def show_pet(self) -> None:
        if self.animator.state == "hidden":
            self.animator.set_state("idle")
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

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._sync_right_click_menu_position()
        self._sync_chat_dialog_position()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self.dragging:
            self.animator.next_click_state()
            event.accept()
        self.dragging = False

    def _show_dialogue_menu(self, global_pos: QPoint) -> None:
        if self._right_click_menu is not None and self._right_click_menu.isVisible():
            self._right_click_menu.close()
            self._right_click_menu = None
            self._right_click_menu_anchor = None
            return
        if self._right_click_menu is not None:
            self._right_click_menu.close()
        menu = AnimatedRightClickMenu(
            self._menu_state_action,
            self._menu_reply,
            self._menu_utility_action,
            self,
        )
        menu.destroyed.connect(lambda _object=None, target=menu: self._clear_right_click_menu(target))
        self._right_click_menu = menu
        final_pos = menu.show_at(global_pos)
        self._right_click_menu_anchor = popup_anchor_offset(
            pet_position=(self.pos().x(), self.pos().y()),
            popup_position=(final_pos.x(), final_pos.y()),
        )

    def _clear_right_click_menu(self, menu) -> None:
        if self._right_click_menu is not menu:
            return
        self._right_click_menu = None
        self._right_click_menu_anchor = None

    def _sync_right_click_menu_position(self) -> None:
        menu = self._right_click_menu
        if menu is None or self._right_click_menu_anchor is None or not menu.isVisible():
            return
        popup_x, popup_y = popup_position_from_anchor(
            pet_position=(self.pos().x(), self.pos().y()),
            anchor_offset=self._right_click_menu_anchor,
        )
        menu.move(menu._clamped_position(QPoint(popup_x, popup_y)))

    def _menu_state_action(self, state: str) -> None:
        if state == "hide":
            self.hide_pet()
            return
        if state == "show":
            self.show_pet()
            return
        self.set_state(state)

    def _menu_reply(self, action: str) -> None:
        reply = self.dialogue.reply_for_menu(action, self.animator.state)
        self.say(reply, preserve_state=True)

    def _show_chat_dialog(self) -> None:
        if self._chat_dialog is None:
            dialog = PetChatDialog(self)
            dialog.message_submitted.connect(lambda text: self.chat_requested.emit(text))
            dialog.destroyed.connect(lambda _object=None: self._clear_chat_dialog(dialog))
            self._chat_dialog = dialog
        self._chat_dialog.show()
        self._sync_chat_dialog_position(force=True)
        self._chat_dialog.raise_()
        self._chat_dialog.activateWindow()

    def _clear_chat_dialog(self, dialog) -> None:
        if self._chat_dialog is dialog:
            self._chat_dialog = None

    def receive_chat_reply(self, text: str) -> None:
        if self._chat_dialog is not None:
            self._chat_dialog.append_assistant_message(text)

    def _sync_chat_dialog_position(self, force: bool = False) -> None:
        dialog = self._chat_dialog
        if dialog is None or (not force and not dialog.isVisible()):
            return
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        x, y = chat_dialog_position_for_pet(
            pet_position=(self.pos().x(), self.pos().y()),
            pet_size=(self.width(), self.height()),
            dialog_size=(dialog.width(), dialog.height()),
            screen_rect=(rect.left(), rect.top(), rect.width(), rect.height()),
        )
        dialog.move(x, y)

    def _menu_utility_action(self, action: str) -> None:
        if action == "open_chat":
            self._show_chat_dialog()
            return
        if action == "open_control_panel":
            self.control_panel_requested.emit()

    def _apply_scaled_size(self, source_size: tuple = None, scale: float = None) -> None:
        scale = self.scale if scale is None else scale
        if source_size is None:
            display_size = display_dimension(self.base_size, scale)
            target_size = (display_size, display_size)
        else:
            target_size = scaled_dimensions(source_size, scale)
        if self.size().width() == target_size[0] and self.size().height() == target_size[1]:
            return
        self.setFixedSize(*target_size)
        self.image_label.setFixedSize(*target_size)

    def _resize_image(self, image: Image.Image, scale: float) -> Image.Image:
        display_size = display_dimension(self.base_size, scale)
        return image.convert("RGBA").resize((display_size, display_size), Image.LANCZOS)

    def _next_video_pixmap(
        self,
        source: VideoPetSource,
        scale: float,
        speech_text: str = "",
        loop_mode: str = LOOP_MODE_LOOP,
    ) -> QPixmap:
        display_size = scaled_dimensions(source.size, scale)
        frame_index = source.next_frame_index(loop_mode)
        cache_key = (id(source), display_size, frame_index, speech_text)
        if cache_key not in self._pixmap_cache:
            frame = source.frames[frame_index]
            display_frame = self._resize_to_display(frame, display_size)
            if speech_text:
                display_frame = self.renderer.with_speech_bubble(display_frame, speech_text)
            self._pixmap_cache[cache_key] = QPixmap.fromImage(
                self._pil_to_qimage(display_frame)
            )
            if len(self._pixmap_cache) > self._max_pixmap_cache_items:
                self._pixmap_cache.popitem(last=False)
        else:
            self._pixmap_cache.move_to_end(cache_key)
        return self._pixmap_cache[cache_key]

    def _resize_to_display(self, image: Image.Image, display_size: tuple) -> Image.Image:
        rgba = image.convert("RGBA")
        if rgba.size == display_size:
            return rgba
        return rgba.resize(display_size, Image.BILINEAR)

    def _current_video_size(self):
        source = self._current_video_source()
        return source.size if source is not None else None

    def _current_video_source(self):
        return select_video_source_for_state(self.animator.state, self.state_video_sources, self.video_source)

    def _sync_timer_interval(self, source, playback_speed: float = 1.0) -> None:
        interval = timer_interval_for_source(source, playback_speed)
        if interval == self._timer_interval_ms:
            return
        self._timer_interval_ms = interval
        self.timer.start(interval)

    def _pil_to_qimage(self, image) -> QImage:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        data = rgba.tobytes()
        qimage = QImage(data, width, height, width * 4, QImage.Format_RGBA8888)
        return qimage.copy()
