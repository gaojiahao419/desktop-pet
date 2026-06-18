# Local LLM Desktop Pet Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route desktop-pet chat through the local LLM runtime while preserving responsive PyQt behavior, clear control-panel status, and automatic fallback to `LocalDialogue`.

**Architecture:** A small Qt signal bridge converts thread callbacks from `ChatService` into main-thread signals. `main.py` owns service startup and shutdown, sends accepted chat requests to the worker, and invokes `LocalDialogue` only when the runtime is unavailable or fails. `control_api.py` exposes chat state to the existing Electron control panel, which disables duplicate sends while loading or generating.

**Tech Stack:** Python, PyQt5, existing local HTTP control API, Electron/vanilla JavaScript control panel, pytest, PowerShell 7

---

## Task 1: Add Chat Runtime State to the Control API

**Files:**
- Modify: `control_api.py`
- Modify: `tests/test_control_api.py`

- [ ] **Step 1: Write failing state-store tests**

Add assertions that a fresh snapshot contains:

```python
"chat": {
    "state": "stopped",
    "message": "本地模型尚未启动",
}
```

Test `set_chat_state(state, message)` increments `revision` only when either field changes, preserves all unrelated state, and rejects states outside `stopped`, `loading`, `ready`, `generating`, `fallback`, and `error`.

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests/test_control_api.py -q
```

- [ ] **Step 3: Implement chat state in `ControlApiStateStore`**

Store chat state as a nested dictionary, copy it in snapshots, and add a lock-protected setter. Do not overload the existing general `status` field; it remains available for material and playback feedback.

- [ ] **Step 4: Run focused tests and commit**

```powershell
python -m pytest tests/test_control_api.py -q
git add control_api.py tests/test_control_api.py
git commit -m "feat: expose local chat runtime state"
```

## Task 2: Bridge Runtime Callbacks onto the Qt Main Thread

**Files:**
- Create: `chat_qt_bridge.py`
- Create: `tests/test_chat_qt_bridge.py`

- [ ] **Step 1: Write failing signal tests**

With an existing `QApplication` fixture, connect collectors and verify these public callback methods emit matching signals:

```python
bridge.handle_state_change("ready", "本地模型已就绪")
bridge.handle_reply("晚上好。")
bridge.handle_fallback("你好", "worker unavailable")
```

Signals:

```python
state_changed = pyqtSignal(str, str)
reply_ready = pyqtSignal(str)
fallback_requested = pyqtSignal(str, str)
```

Call each callback from a background `threading.Thread`, process Qt events, and assert the connected slot runs safely through Qt's queued delivery.

- [ ] **Step 2: Run and confirm import failure**

```powershell
python -m pytest tests/test_chat_qt_bridge.py -q
```

- [ ] **Step 3: Implement the bridge**

`ChatQtBridge(QObject)` contains only the three signals and three callback methods. It must not import `ChatService`, load models, touch widgets, or contain fallback business logic.

- [ ] **Step 4: Run and commit**

```powershell
python -m pytest tests/test_chat_qt_bridge.py -q
git add chat_qt_bridge.py tests/test_chat_qt_bridge.py
git commit -m "feat: bridge chat callbacks to qt"
```

## Task 3: Integrate `ChatService` in Application Startup

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Add failing integration tests with a fake service**

Make `main.main()` accept a service factory or extract an `ApplicationChatController` that accepts a `ChatService`-compatible object. Tests must not start a real model.

Verify:

- startup calls `service.start()` once after signal connections exist;
- accepted chat text calls `service.submit(text)` and does not call `LocalDialogue` immediately;
- blank text is ignored;
- a rejected submit uses `LocalDialogue.reply_for_text(text)` and displays it with `window.say`;
- `reply_ready` displays the model text with `window.say`;
- `fallback_requested` generates one local fallback reply from the original user text;
- state changes call `api_store.set_chat_state`;
- `app.aboutToQuit` stops the service exactly once.

- [ ] **Step 2: Run focused tests and confirm failure**

```powershell
python -m pytest tests/test_main.py -q
```

- [ ] **Step 3: Wire service ownership and callback flow**

Preserve the existing `LocalDialogue` instance. Create `ChatQtBridge`, pass its callback methods into `ChatService`, then connect bridge signals before calling `start()`.

The chat flow must be equivalent to:

```python
def chat_text(text: str) -> None:
    normalized = text.strip()
    if not normalized:
        return
    if chat_service.submit(normalized):
        return
    window.say(dialogue.reply_for_text(normalized))


def show_fallback_reply(original_text: str, reason: str) -> None:
    api_store.set_chat_state("fallback", "本地模型不可用，已切换基础回复")
    window.say(dialogue.reply_for_text(original_text))
```

The reason is diagnostic context and must not be shown inside the pet's speech bubble.

- [ ] **Step 4: Preserve the UI thread boundary**

Only Qt slots may call `window.say()` or mutate `ControlApiStateStore`. `ChatService` reader and timer threads call bridge callback methods only. Add an assertion or test hook proving reply display executes on `QApplication.instance().thread()`.

- [ ] **Step 5: Run integration and regression tests**

```powershell
python -m pytest tests/test_main.py tests/test_chat_qt_bridge.py tests/test_control_api.py -q
python -m pytest -q
```

- [ ] **Step 6: Commit application wiring**

```powershell
git add main.py tests/test_main.py
git commit -m "feat: route desktop chat through local llm"
```

## Task 4: Reflect Chat State in the Electron Control Panel

**Files:**
- Modify: `web_control_panel/app.js`
- Modify: `web_control_panel/index.html`
- Modify: `tests/test_web_control_panel.py`

- [ ] **Step 1: Extend failing static behavior tests**

Assert that JavaScript state includes the nested `chat` object, API patches merge `chat` instead of replacing unrelated state, and rendering derives button behavior from chat state.

Required behavior:

| State | Button | Input | Visible status |
|---|---|---|---|
| `stopped` | disabled | enabled | 本地模型尚未启动 |
| `loading` | disabled | enabled | 正在加载本地模型 |
| `ready` | enabled | enabled | 本地模型已就绪 |
| `generating` | disabled | disabled | 正在生成回复 |
| `fallback` | enabled | enabled | 当前使用基础回复 |
| `error` | enabled | enabled | 本地模型异常，使用基础回复 |

- [ ] **Step 2: Run tests and confirm failure**

```powershell
python -m pytest tests/test_web_control_panel.py -q
```

- [ ] **Step 3: Implement state rendering**

Keep button text stable as `发送`; show status through the existing status area. Add `aria-busy="true"` while generating. Do not add a settings page, model selector, streaming text, or model download controls in v1.

When `/api/chat` succeeds, clear the input only after the request returns successfully. Polling continues to supply authoritative runtime state. A failed HTTP request restores the typed text and reports the transport error through the existing status mechanism.

- [ ] **Step 4: Run frontend tests and lint-level checks**

```powershell
python -m pytest tests/test_web_control_panel.py tests/test_control_api.py -q
node --check web_control_panel/app.js
```

- [ ] **Step 5: Commit control-panel behavior**

```powershell
git add web_control_panel/app.js web_control_panel/index.html tests/test_web_control_panel.py
git commit -m "feat: show local chat status in control panel"
```

## Task 5: Handle Missing Environments and Adapters Explicitly

**Files:**
- Modify: `main.py`
- Modify: `chat_service.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_chat_service.py`

- [ ] **Step 1: Add failing fallback matrix tests**

Cover each startup condition:

| Condition | Expected behavior |
|---|---|
| `.venv-llm` missing | app opens; chat state `fallback`; local replies work |
| worker imports fail | app opens; chat state `fallback`; error logged |
| adapter missing, base cached | worker reaches `ready` with `adapter_loaded=false` |
| base model unavailable offline | app opens; chat state `fallback`; local replies work |
| generation timeout | current prompt gets one local reply; service attempts one restart |
| app closes while loading | worker is terminated without blocking shutdown |

- [ ] **Step 2: Run focused tests and confirm the new cases fail**

```powershell
python -m pytest tests/test_main.py tests/test_chat_service.py -q
```

- [ ] **Step 3: Implement user-safe state messages**

Map internal failures to short Chinese state messages in `main.py`; preserve full exception details only in logs. Do not display filesystem paths, Python tracebacks, package names, or CUDA details in the UI.

Use these messages:

```python
CHAT_STATE_MESSAGES = {
    "stopped": "本地模型尚未启动",
    "loading": "正在加载本地模型",
    "ready": "本地模型已就绪",
    "generating": "正在生成回复",
    "fallback": "本地模型不可用，当前使用基础回复",
    "error": "本地模型异常，当前使用基础回复",
}
```

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_main.py tests/test_chat_service.py -q
git add main.py chat_service.py tests/test_main.py tests/test_chat_service.py
git commit -m "fix: keep chat usable when local model fails"
```

## Task 6: Keep Model Assets Outside Windows Packaging

**Files:**
- Modify: `build_windows.ps1`
- Modify: `DesktopPet.spec`
- Modify: `README.md`
- Create: `tests/test_llm_packaging_boundary.py`

- [ ] **Step 1: Write failing packaging-boundary tests**

Assert that `DesktopPet.spec` and `build_windows.ps1` do not collect `torch`, `transformers`, `bitsandbytes`, `peft`, `.venv-llm`, `llm_lab/adapters`, model cache directories, or adapter weights. Assert runtime source modules needed by the desktop app are included through normal Python imports.

- [ ] **Step 2: Run the test**

```powershell
python -m pytest tests/test_llm_packaging_boundary.py -q
```

Expected: fail if current collection rules are broad enough to include training/model assets; otherwise it may pass and documents the boundary before changes.

- [ ] **Step 3: Tighten packaging rules only where required**

The packaged desktop app may launch a separately installed `.venv-llm` beside the project during development, but v1 distribution does not promise an embedded model runtime. Update README run instructions to distinguish:

```text
Desktop-only mode: existing application dependencies, LocalDialogue fallback.
Local-LLM mode: project checkout plus .venv-llm and downloaded base model/adapter.
```

Do not change the existing Electron bundling or video asset behavior.

- [ ] **Step 4: Run packaging tests and build**

```powershell
python -m pytest tests/test_llm_packaging_boundary.py -q
pwsh -NoLogo -NoProfile -File .\build_windows.ps1
```

Expected: build succeeds without copying model weights, LLM Python packages, or `.venv-llm` into `dist`.

- [ ] **Step 5: Smoke-test the packaged fallback path**

Temporarily run the packaged app where `.venv-llm` is not discoverable. Confirm the pet and control panel open, chat state shows fallback, and one entered message receives a `LocalDialogue` response.

- [ ] **Step 6: Commit packaging documentation and tests**

```powershell
git add build_windows.ps1 DesktopPet.spec README.md tests/test_llm_packaging_boundary.py
git commit -m "docs: define local llm packaging boundary"
```

## Task 7: End-to-End Desktop Verification

- [ ] Run the full automated suite:

```powershell
python -m pytest -q
node --check web_control_panel/app.js
```

- [ ] Start the application from PowerShell 7:

```powershell
python main.py
```

- [ ] Verify the ready path manually:

1. Control panel opens while the pet remains responsive.
2. Status moves from loading to ready without freezing either UI.
3. Enter `晚上好，今天工作有点累` and press send once.
4. Send is disabled while generation is active.
5. One model reply appears in the pet speech bubble.
6. After 10 rounds, chat still works and memory does not grow without bound.

- [ ] Verify the fallback path manually:

1. Close the app and rename `.venv-llm` temporarily.
2. Start `python main.py` again.
3. Confirm the app opens and status says the base reply mode is active.
4. Send one message and confirm `LocalDialogue` replies.
5. Restore the `.venv-llm` directory name.

- [ ] Verify clean shutdown:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'llm_worker\.py' } | Select-Object ProcessId, CommandLine
```

Expected after closing the app: no matching process.

- [ ] Inspect scope before completion:

```powershell
git diff --stat HEAD~6..HEAD
git status --short
```

Expected: no streaming implementation, online API, persistent memory, pet-action control, model selector, or bundled model weights were added.
