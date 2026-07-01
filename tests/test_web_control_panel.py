from pathlib import Path


def test_web_control_panel_assets_exist():
    asset_root = Path("web_control_panel")
    assert (asset_root / "index.html").exists()
    assert (asset_root / "app.css").exists()
    assert (asset_root / "app.js").exists()


def test_web_control_panel_removes_default_electron_menu_and_english_kicker():
    electron_main = Path("electron_app/main.js").read_text(encoding="utf-8")
    html = Path("web_control_panel/index.html").read_text(encoding="utf-8")
    style = Path("web_control_panel/app.css").read_text(encoding="utf-8")

    assert "Menu.setApplicationMenu(null)" in electron_main
    assert "autoHideMenuBar: true" in electron_main
    assert "menuBarVisible: false" in electron_main
    assert "Desktop Pet Studio" not in html
    assert "DESKTOP PET STUDIO" not in html
    assert "kicker" not in html
    assert ".kicker" not in style


def test_electron_shell_quits_python_from_button_and_window_close():
    electron_main = Path("electron_app/main.js").read_text(encoding="utf-8")
    preload = Path("electron_app/preload.js").read_text(encoding="utf-8")

    assert "async function requestPythonQuit" in electron_main
    assert "mainWindow.on(\"close\"" in electron_main
    assert "requestPythonQuit();" in electron_main
    assert "ipcMain.on(\"desktop-pet:quit-shell\"" in electron_main
    assert "app.quit();" in electron_main
    assert "ipcRenderer.send(\"desktop-pet:quit-shell\")" in preload
    assert "return await requestJson(\"/api/quit\")" in preload


def test_web_control_panel_js_exposes_python_bridge_calls():
    source = Path("web_control_panel/app.js").read_text(encoding="utf-8")

    assert "window.desktopPetApi" in source
    assert "connectElectronBridge" in source
    assert '{ state: "sleep", title: "睡觉动作", subtitle: "睡觉状态循环" }' in source
    assert '{ label: "睡觉", state: "sleep", role: "lightButton" }' in source
    assert 'callBridge("chooseStateVideo"' in source
    assert 'createBridgeScheduler("setStateScale"' in source
    assert 'createBridgeScheduler("setStateSpeed"' in source
    assert 'callBridge("setStateLoopMode"' in source
    assert 'callBridge("playPreview"' in source


def test_web_control_panel_left_library_uses_internal_scroll():
    source = Path("web_control_panel/app.css").read_text(encoding="utf-8")

    assert ".material-panel" in source
    assert "grid-template-rows: auto minmax(0, 1fr)" in source
    assert "height: 100%" in source
    assert "max-height: calc(100vh - 210px)" not in source


def test_web_control_panel_has_theme_options():
    html = Path("web_control_panel/index.html").read_text(encoding="utf-8")
    script = Path("web_control_panel/app.js").read_text(encoding="utf-8")
    style = Path("web_control_panel/app.css").read_text(encoding="utf-8")

    assert 'data-theme-option="obsidian"' in html
    assert 'data-theme-option="bluegray"' in html
    assert "白蓝灰" in html
    assert 'data-theme-option="aurora"' not in html
    assert 'data-theme-option="pearl"' not in html
    assert 'data-theme-option="berry"' not in html
    assert "localStorage.setItem(THEME_STORAGE_KEY" in script
    assert 'const THEMES = ["obsidian", "bluegray"]' in script
    assert 'body[data-theme="bluegray"]' in style
    assert "--shell: #cbd8e8" in style
    assert "--accent: #1d4ed8" in style
    assert "--primary-button-bg: #1d4ed8" in style
    assert "--primary-button-hover-bg: #2563eb" in style
    assert "--primary-button-active-bg: #1e40af" in style
    assert 'body[data-theme="aurora"]' not in style
    assert 'body[data-theme="pearl"]' not in style
    assert 'body[data-theme="berry"]' not in style


def test_web_control_panel_sliders_ignore_track_clicks():
    script = Path("web_control_panel/app.js").read_text(encoding="utf-8")

    assert "function setupSmoothRange" in script
    assert "function createBridgeScheduler" in script
    assert 'rangeInput.addEventListener("pointerdown"' in script
    assert 'rangeInput.addEventListener("pointermove"' in script
    assert "event.preventDefault()" in script
    assert "setupSmoothRange(scaleInput" in script
    assert "setupSmoothRange(speedInput" in script
    assert "requestAnimationFrame(flush)" in script


def test_web_control_panel_slider_bridge_does_not_repaint_cards():
    source = Path("electron_app/preload.js").read_text(encoding="utf-8")

    assert "setStateScale" in source
    assert "setStateSpeed" in source
    assert "return null;" in source


def test_web_control_panel_buttons_do_not_shift_on_click():
    style = Path("web_control_panel/app.css").read_text(encoding="utf-8")

    assert "translateY(1px) scale(0.99)" not in style
    assert "transition: filter 150ms ease, background 150ms ease, border-color 150ms ease;" in style


def test_web_control_panel_resizes_realtime_without_visual_mode_swap():
    source = Path("electron_app/main.js").read_text(encoding="utf-8")
    style = Path("web_control_panel/app.css").read_text(encoding="utf-8")

    assert "BrowserWindow" in source
    assert "loadFile" in source
    assert "QWebEngineView" not in source
    assert "body.is-resizing" not in style
    assert "height: 100vh" not in style
    assert "contain: layout paint" in style


def test_web_control_panel_default_size_is_not_the_minimum_size():
    source = Path("electron_app/main.js").read_text(encoding="utf-8")

    assert "minWidth: 1180" in source
    assert "minHeight: 760" in source
    assert "width: 1480" in source
    assert "height: 900" in source


def test_web_control_panel_columns_can_shrink_during_resize():
    style = Path("web_control_panel/app.css").read_text(encoding="utf-8")

    assert "min-width: 1120px" in style
    assert "grid-template-columns: minmax(360px, 430px) minmax(400px, 1fr) minmax(320px, 400px)" in style
    assert "min-height: clamp(300px, 50vh, 460px)" in style
