from pathlib import Path

import sys

import electron_control
from electron_control import build_electron_command, find_electron_executable


def test_find_electron_executable_prefers_real_electron_exe(tmp_path):
    electron_cmd = tmp_path / "node_modules" / ".bin" / "electron.cmd"
    electron_exe = tmp_path / "node_modules" / "electron" / "dist" / "electron.exe"
    electron_cmd.parent.mkdir(parents=True)
    electron_exe.parent.mkdir(parents=True)
    electron_cmd.write_text("@echo off", encoding="utf-8")
    electron_exe.write_text("", encoding="utf-8")

    assert find_electron_executable(tmp_path) == electron_exe


def test_build_electron_command_points_to_desktop_control_shell(tmp_path):
    electron_cmd = tmp_path / "node_modules" / "electron" / "dist" / "electron.exe"
    app_main = tmp_path / "electron_app" / "main.js"
    app_main.parent.mkdir(parents=True)
    electron_cmd.parent.mkdir(parents=True)
    electron_cmd.write_text("@echo off", encoding="utf-8")
    app_main.write_text("", encoding="utf-8")

    command = build_electron_command(tmp_path, "http://127.0.0.1:34567")

    assert command == [
        str(electron_cmd),
        str(app_main),
        "--control-url",
        "http://127.0.0.1:34567",
    ]


def test_project_root_uses_executable_parent_when_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "DesktopPet.exe"
    fake_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert electron_control.project_root() == tmp_path
