import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock, Thread
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from PIL import Image
from PyQt5.QtCore import QObject, pyqtSignal

from control_panel import (
    ACTION_BUTTONS,
    LOOP_MODE_LOOP,
    SCALE_DEFAULT_PERCENT,
    STATE_MATERIALS,
    next_preview_frame_index,
    normalize_loop_mode,
    preview_frame_label,
    scale_float_to_percent,
    scale_percent_to_float,
    speed_float_to_percent,
    speed_percent_to_float,
)


class ControlApiSignals(QObject):
    state_requested = pyqtSignal(str)
    say_requested = pyqtSignal(str)
    chat_requested = pyqtSignal(str)
    state_video_requested = pyqtSignal(str, str, bool)
    reset_state_video_requested = pyqtSignal(str)
    state_scale_requested = pyqtSignal(str, float)
    state_playback_speed_requested = pyqtSignal(str, float)
    state_loop_mode_requested = pyqtSignal(str, str)
    black_background_requested = pyqtSignal(bool)
    play_preview_requested = pyqtSignal()
    pause_preview_requested = pyqtSignal()
    sync_preview_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    @classmethod
    def signal_names(cls) -> tuple[str, ...]:
        return (
            "state_requested",
            "say_requested",
            "chat_requested",
            "state_video_requested",
            "reset_state_video_requested",
            "state_scale_requested",
            "state_playback_speed_requested",
            "state_loop_mode_requested",
            "black_background_requested",
            "play_preview_requested",
            "pause_preview_requested",
            "sync_preview_requested",
            "quit_requested",
        )


class ControlApiStateStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.black_background_transparent = False
        self.state_material_names = {
            state: "未绑定，使用内置绘制" for state, _title, _hint in STATE_MATERIALS
        }
        self.state_status_names = {
            state: subtitle for state, _title, subtitle in STATE_MATERIALS
        }
        self.state_scale_percents = {
            state: SCALE_DEFAULT_PERCENT for state, _title, _hint in STATE_MATERIALS
        }
        self.state_speed_percents = {state: 100 for state, _title, _hint in STATE_MATERIALS}
        self.state_loop_modes = {state: LOOP_MODE_LOOP for state, _title, _hint in STATE_MATERIALS}
        self._status = "状态：使用内置绘制宠物"
        self._revision = 0
        self._preview_source = None
        self._preview_state = None
        self._preview_frame_index = 0
        self._preview_playing = False
        self._preview = {
            "message": "上传素材后显示首帧预览",
            "image": "",
            "frameLabel": preview_frame_label(0, 0),
            "state": "",
            "playing": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "states": self._states_payload_locked(),
                "actions": self._actions_payload(),
                "blackBackground": self.black_background_transparent,
                "status": self._status,
                "preview": dict(self._preview),
                "revision": self._revision,
            }

    def apply_settings(
        self,
        scale: float,
        black_background_transparent: bool,
        state_materials: dict[str, str],
        state_scales: dict[str, float] = None,
        state_playback_speeds: dict[str, float] = None,
        state_loop_modes: dict[str, str] = None,
    ) -> None:
        state_scales = state_scales or {}
        state_playback_speeds = state_playback_speeds or {}
        state_loop_modes = state_loop_modes or {}
        with self._lock:
            for state, _title, _subtitle in STATE_MATERIALS:
                self.state_scale_percents[state] = scale_float_to_percent(state_scales.get(state, scale))
                self.state_speed_percents[state] = speed_float_to_percent(
                    state_playback_speeds.get(state, 1.0)
                )
                self.state_loop_modes[state] = normalize_loop_mode(
                    state_loop_modes.get(state, LOOP_MODE_LOOP)
                )
            self.black_background_transparent = bool(black_background_transparent)
            for state, path in state_materials.items():
                if state in self.state_material_names:
                    self.state_material_names[state] = Path(path).name
                    self.state_status_names[state] = "已保存：启动后加载"
            self._touch_locked()

    def set_status(self, text: str) -> None:
        with self._lock:
            self._status = text if text.startswith("状态：") else f"状态：{text}"
            self._touch_locked()

    def set_state_material_loading(self, state: str, path: str) -> None:
        with self._lock:
            self.state_material_names[state] = Path(path).name
            self.state_status_names[state] = "加载中：正在解析素材"
            self._status = f"状态：正在加载 {self._state_title(state)} 素材"
            self._touch_locked()

    def set_state_material_loaded(self, state: str, path: str, has_transparency: bool = True) -> None:
        with self._lock:
            material_name = Path(path).name
            self.state_material_names[state] = material_name
            if has_transparency:
                self.state_status_names[state] = "已绑定：透明动作素材"
                self._status = f"状态：{self._state_title(state)} 已绑定 {material_name}"
            else:
                self.state_status_names[state] = "无透明通道：会显示背景"
                self._status = f"状态：{material_name} 没有透明通道，黑底会原样显示"
            self._touch_locked()

    def set_state_material_failed(self, state: str, path: str, error: str) -> None:
        with self._lock:
            self.state_material_names[state] = f"{Path(path).name} 加载失败"
            self.state_status_names[state] = "加载失败：检查素材"
            self._status = f"状态：{self._state_title(state)} 素材加载失败：{error}"
            self._touch_locked()

    def reset_state_video(self, state: str) -> None:
        with self._lock:
            self.state_material_names[state] = "未绑定，使用内置绘制"
            self.state_status_names[state] = "未绑定：使用默认"
            self._status = f"状态：{self._state_title(state)} 已解绑素材"
            if self._preview_state == state:
                self._set_preview_message_locked("上传素材后显示首帧预览")
            self._touch_locked()

    def set_state_scale_percent(self, state: str, percent: int) -> None:
        with self._lock:
            self.state_scale_percents[state] = max(0, min(250, int(percent)))
            self._touch_locked()

    def set_state_speed_percent(self, state: str, percent: int) -> None:
        with self._lock:
            self.state_speed_percents[state] = max(25, min(300, int(percent)))
            self._touch_locked()

    def set_state_loop_mode(self, state: str, loop_mode: str) -> None:
        with self._lock:
            self.state_loop_modes[state] = normalize_loop_mode(loop_mode)
            self._touch_locked()

    def set_black_background_transparent(self, enabled: bool) -> None:
        with self._lock:
            self.black_background_transparent = bool(enabled)
            self._touch_locked()

    def set_preview_source(self, source, state: str = None) -> None:
        with self._lock:
            self._preview_source = source
            self._preview_state = state
            self._preview_frame_index = 0
            self._render_preview_frame_locked()
            self._touch_locked()

    def set_preview_message(self, text: str) -> None:
        with self._lock:
            self._set_preview_message_locked(text)
            self._touch_locked()

    def play_preview(self) -> bool:
        with self._lock:
            if self._preview_source is None:
                self._status = "状态：先上传或选择一个动作素材"
                self._touch_locked()
                return False
            self._preview_playing = True
            self._preview["playing"] = True
            self._touch_locked()
            return True

    def pause_preview(self) -> None:
        with self._lock:
            self._preview_playing = False
            self._preview["playing"] = False
            self._touch_locked()

    def advance_preview_frame(self) -> bool:
        with self._lock:
            if self._preview_source is None:
                self._set_preview_message_locked("上传素材后显示首帧预览")
                self._touch_locked()
                return False
            total = len(self._preview_source.frames)
            self._preview_frame_index = next_preview_frame_index(
                self._preview_frame_index,
                total,
                self._loop_mode_for_state_locked(self._preview_state),
            )
            self._render_preview_frame_locked()
            if (
                self._loop_mode_for_state_locked(self._preview_state) == "once"
                and self._preview_frame_index == total - 1
            ):
                self._preview_playing = False
                self._preview["playing"] = False
                self._touch_locked()
                return False
            self._touch_locked()
            return True

    def preview_interval_ms(self) -> int:
        with self._lock:
            if self._preview_source is None:
                return 100
            return self._preview_source.frame_interval_ms(self._preview_speed_locked())

    def preview_playing(self) -> bool:
        with self._lock:
            return self._preview_playing

    def _actions_payload(self) -> list[dict[str, str]]:
        return [
            {"label": label, "state": state, "role": object_name}
            for label, state, object_name in ACTION_BUTTONS
        ]

    def _touch_locked(self) -> None:
        self._revision += 1

    def _states_payload_locked(self) -> dict[str, dict[str, Any]]:
        payload = {}
        for state, title, subtitle in STATE_MATERIALS:
            payload[state] = {
                "state": state,
                "title": title,
                "subtitle": subtitle,
                "materialName": self.state_material_names.get(state, "未绑定，使用内置绘制"),
                "status": self.state_status_names.get(state, subtitle),
                "scalePercent": self.state_scale_percents.get(state, SCALE_DEFAULT_PERCENT),
                "speedPercent": self.state_speed_percents.get(state, 100),
                "loopMode": self.state_loop_modes.get(state, LOOP_MODE_LOOP),
            }
        return payload

    def _state_title(self, state: str) -> str:
        for key, title, _subtitle in STATE_MATERIALS:
            if key == state:
                return title
        return state

    def _set_preview_message_locked(self, text: str) -> None:
        self._preview_source = None
        self._preview_state = None
        self._preview_frame_index = 0
        self._preview_playing = False
        self._preview = {
            "message": text,
            "image": "",
            "frameLabel": preview_frame_label(0, 0),
            "state": "",
            "playing": False,
        }

    def _preview_speed_locked(self) -> float:
        if self._preview_state in self.state_speed_percents:
            return speed_percent_to_float(self.state_speed_percents[self._preview_state])
        return 1.0

    def _loop_mode_for_state_locked(self, state: str) -> str:
        return normalize_loop_mode(self.state_loop_modes.get(state, LOOP_MODE_LOOP))

    def _render_preview_frame_locked(self) -> None:
        if self._preview_source is None:
            return
        frame = self._preview_source.frames[self._preview_frame_index].convert("RGBA")
        preview = frame.copy()
        preview.thumbnail((720, 460), Image.LANCZOS)
        buffer = io.BytesIO()
        preview.save(buffer, format="PNG")
        image_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        self._preview = {
            "message": "",
            "image": image_url,
            "state": self._preview_state,
            "frameLabel": preview_frame_label(
                self._preview_frame_index,
                len(self._preview_source.frames),
            ),
            "playing": self._preview_playing,
        }


class ControlApiServer:
    def __init__(
        self,
        store: ControlApiStateStore,
        signals: Any,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.store = store
        self.signals = signals
        self.host = host
        self.port = port
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[Thread] = None

    @property
    def url(self) -> str:
        if self._httpd is None:
            return f"http://{self.host}:{self.port}"
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        if self._httpd is not None:
            return
        handler = self._handler_class()
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._httpd = None
        self._thread = None

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self) -> None:
                self._send_json({})

            def do_GET(self) -> None:
                route = urlparse(self.path).path
                if route == "/api/state":
                    self._send_json(api.store.snapshot())
                    return
                self._send_json({"error": "Not found"}, status=404)

            def do_POST(self) -> None:
                route = urlparse(self.path).path
                payload = self._read_json()
                handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
                    "/api/request-state": api._request_state,
                    "/api/state-video": api._state_video,
                    "/api/reset-state-video": api._reset_state_video,
                    "/api/state-scale": api._state_scale,
                    "/api/state-speed": api._state_speed,
                    "/api/state-loop": api._state_loop,
                    "/api/black-background": api._black_background,
                    "/api/say": api._say,
                    "/api/chat": api._chat,
                    "/api/play-preview": api._play_preview,
                    "/api/pause-preview": api._pause_preview,
                    "/api/sync-preview": api._sync_preview,
                    "/api/quit": api._quit,
                }
                handler = handlers.get(route)
                if handler is None:
                    self._send_json({"error": "Not found"}, status=404)
                    return
                try:
                    response = handler(payload)
                except (KeyError, TypeError, ValueError) as exc:
                    self._send_json({"error": str(exc)}, status=400)
                    return
                self._send_json(response)

            def log_message(self, _format: str, *args: Any) -> None:
                return

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw)

            def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def _emit(self, signal_name: str, *args: Any) -> None:
        getattr(self.signals, signal_name).emit(*args)

    def _request_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload["state"])
        self._emit("state_requested", state)
        return self.store.snapshot()

    def _state_video(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload["state"])
        path = str(payload["path"])
        self.store.set_state_material_loading(state, path)
        self._emit("state_video_requested", state, path, self.store.black_background_transparent)
        return self.store.snapshot()

    def _reset_state_video(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload["state"])
        self.store.reset_state_video(state)
        self._emit("reset_state_video_requested", state)
        return self.store.snapshot()

    def _state_scale(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload["state"])
        percent = int(payload["percent"])
        self.store.set_state_scale_percent(state, percent)
        self._emit("state_scale_requested", state, scale_percent_to_float(percent))
        return self.store.snapshot()

    def _state_speed(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload["state"])
        percent = int(payload["percent"])
        self.store.set_state_speed_percent(state, percent)
        self._emit("state_playback_speed_requested", state, speed_percent_to_float(percent))
        return self.store.snapshot()

    def _state_loop(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload["state"])
        loop_mode = normalize_loop_mode(str(payload["loopMode"]))
        self.store.set_state_loop_mode(state, loop_mode)
        self._emit("state_loop_mode_requested", state, loop_mode)
        return self.store.snapshot()

    def _black_background(self, payload: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(payload["enabled"])
        self.store.set_black_background_transparent(enabled)
        self._emit("black_background_requested", enabled)
        return self.store.snapshot()

    def _say(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._emit("say_requested", str(payload.get("text", "")).strip())
        return self.store.snapshot()

    def _chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._emit("chat_requested", str(payload.get("text", "")).strip())
        return self.store.snapshot()

    def _play_preview(self, _payload: dict[str, Any]) -> dict[str, Any]:
        if self.store.play_preview():
            self._emit("play_preview_requested")
        return self.store.snapshot()

    def _pause_preview(self, _payload: dict[str, Any]) -> dict[str, Any]:
        self.store.pause_preview()
        self._emit("pause_preview_requested")
        return self.store.snapshot()

    def _sync_preview(self, _payload: dict[str, Any]) -> dict[str, Any]:
        self.store.set_status("预览已同步到宠物窗口")
        self._emit("sync_preview_requested")
        return self.store.snapshot()

    def _quit(self, _payload: dict[str, Any]) -> dict[str, Any]:
        self._emit("quit_requested")
        return self.store.snapshot()
