from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QAction, QLabel, QMenu, QVBoxLayout, QWidget
from PIL import Image

from dialogue import LocalDialogue
from pet_animator import PetAnimator, VALID_STATES
from pet_renderer import PetRenderer
from video_pet_source import VideoPetSource, clamp_scale


def select_video_source_for_state(state: str, state_sources: dict, default_source):
    return state_sources.get(state) or default_source


def scaled_dimensions(size: tuple, scale: float) -> tuple:
    width, height = size
    scale = clamp_scale(scale)
    return max(1, int(width * scale)), max(1, int(height * scale))


class PetWindow(QWidget):
    def __init__(self, animator: PetAnimator, dialogue: LocalDialogue) -> None:
        super().__init__()
        self.animator = animator
        self.dialogue = dialogue
        self.renderer = PetRenderer()
        self.video_source = None
        self.state_video_sources = {}
        self._pixmap_cache = {}
        self.scale = 1.0
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
        self.timer.start(60)
        self.refresh_frame()

    def refresh_frame(self) -> None:
        frame = self.animator.advance()
        video_source = select_video_source_for_state(frame.state, self.state_video_sources, self.video_source)
        if video_source is not None:
            self._apply_scaled_size(video_source.size)
            pixmap = self._next_video_pixmap(video_source)
        else:
            self._apply_scaled_size()
            image = self.renderer.render(frame, self.animator.speech_text)
            image = self._resize_image(image)
            qimage = self._pil_to_qimage(image)
            pixmap = QPixmap.fromImage(qimage)
        self.image_label.setPixmap(pixmap)

        if frame.state == "walk":
            pos = self.pos()
            next_x = max(20, pos.x() + frame.walk_dx)
            self.move(next_x, pos.y())

    def set_state(self, state: str) -> None:
        self.animator.set_state(state)
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

    def set_scale(self, scale: float) -> None:
        old_pos = self.pos()
        self.scale = clamp_scale(scale)
        self._apply_scaled_size(self._current_video_size())
        self._pixmap_cache.clear()
        self.move(old_pos)
        self.refresh_frame()

    def say(self, text: str) -> None:
        self.animator.say(text)
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

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self.dragging:
            self.animator.next_click_state()
            event.accept()
        self.dragging = False

    def _show_dialogue_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        actions = [
            ("打招呼", "greeting"),
            ("问问状态", "status"),
            ("陪我一下", "company"),
            ("鼓励我", "encourage"),
            ("随机聊天", "random"),
        ]
        for label, action_key in actions:
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, key=action_key: self._menu_reply(key))
            menu.addAction(action)
        menu.exec_(global_pos)

    def _menu_reply(self, action: str) -> None:
        reply = self.dialogue.reply_for_menu(action, self.animator.state)
        print(f"宠物: {reply}")
        self.say(reply)

    def _apply_scaled_size(self, source_size: tuple = None) -> None:
        if source_size is None:
            display_size = int(self.base_size * self.scale)
            target_size = (display_size, display_size)
        else:
            target_size = scaled_dimensions(source_size, self.scale)
        if self.size().width() == target_size[0] and self.size().height() == target_size[1]:
            return
        self.setFixedSize(*target_size)
        self.image_label.setFixedSize(*target_size)

    def _resize_image(self, image: Image.Image) -> Image.Image:
        display_size = int(self.base_size * self.scale)
        return image.convert("RGBA").resize((display_size, display_size), Image.LANCZOS)

    def _next_video_pixmap(self, source: VideoPetSource) -> QPixmap:
        display_size = scaled_dimensions(source.size, self.scale)
        cache_key = (id(source), display_size)
        if cache_key not in self._pixmap_cache:
            self._pixmap_cache[cache_key] = [
                QPixmap.fromImage(self._pil_to_qimage(self._resize_to_display(frame, display_size)))
                for frame in source.frames
            ]
        return self._pixmap_cache[cache_key][source.next_frame_index()]

    def _resize_to_display(self, image: Image.Image, display_size: tuple) -> Image.Image:
        return image.convert("RGBA").resize(display_size, Image.LANCZOS)

    def _current_video_size(self):
        source = select_video_source_for_state(self.animator.state, self.state_video_sources, self.video_source)
        return source.size if source is not None else None

    def _pil_to_qimage(self, image) -> QImage:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        data = rgba.tobytes()
        qimage = QImage(data, width, height, width * 4, QImage.Format_RGBA8888)
        return qimage.copy()
