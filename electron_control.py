import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


CONTROL_WINDOW_TITLE = "桌面宠物控制台"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_electron_executable(root: Path = None) -> Optional[Path]:
    root = Path(root) if root is not None else project_root()
    candidates = [
        root / "node_modules" / "electron" / "dist" / "electron.exe",
        root / "node_modules" / ".bin" / "electron.cmd",
        root / "node_modules" / ".bin" / "electron.exe",
        root / "node_modules" / ".bin" / "electron",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_electron_command(root: Path, control_url: str) -> list[str]:
    electron = find_electron_executable(root)
    if electron is None:
        raise FileNotFoundError("没有找到 Electron，请先运行 npm install")
    app_main = Path(root) / "electron_app" / "main.js"
    return [str(electron), str(app_main), "--control-url", control_url]


def focus_window_by_title(title: str = CONTROL_WINDOW_TITLE) -> bool:
    if sys.platform != "win32":
        return False

    import ctypes

    user32 = ctypes.windll.user32
    matches: list[int] = []

    def enum_callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if title in buffer.value:
            matches.append(hwnd)
            return False
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_callback)
    user32.EnumWindows(callback, 0)
    if not matches:
        return False
    hwnd = matches[0]
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    return True


class ElectronControlLauncher:
    def __init__(self, root: Path = None) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.process: Optional[subprocess.Popen] = None

    def show(self, control_url: str) -> bool:
        if self.process is not None and self.process.poll() is None:
            return focus_window_by_title()
        command = build_electron_command(self.root, control_url)
        env = os.environ.copy()
        env["DESKTOP_PET_CONTROL_URL"] = control_url
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        self.process = subprocess.Popen(
            command,
            cwd=str(self.root),
            env=env,
            creationflags=creationflags,
        )
        return True

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
