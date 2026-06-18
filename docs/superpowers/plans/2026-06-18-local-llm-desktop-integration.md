# 本地大模型桌宠接入实施计划

> **供智能代理执行：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 子技能，按任务逐项实施。本计划使用复选框（`- [ ]`）跟踪进度。

**目标：** 把桌宠聊天路由到本地大模型运行时，同时保持 PyQt 响应流畅、控制面板状态清晰，并在模型不可用时自动回退到 `LocalDialogue`。

**架构：** 一个轻量 Qt 信号桥把 `ChatService` 后台线程回调转换为主线程信号。`main.py` 负责服务启动和关闭，把聊天请求发送给 worker，并且只在运行时不可用或失败时调用 `LocalDialogue`。`control_api.py` 向现有 Electron 控制面板公开聊天状态；加载或生成期间，控制面板禁止重复发送。

**技术栈：** Python、PyQt5、现有本地 HTTP 控制 API、Electron/原生 JavaScript 控制面板、pytest、PowerShell 7

---

## 任务 1：向控制 API 添加聊天运行时状态

**文件：**
- 修改：`control_api.py`
- 修改：`tests/test_control_api.py`

- [ ] **步骤 1：编写会失败的状态存储测试**

断言全新快照包含：

```python
"chat": {
    "state": "stopped",
    "message": "本地模型尚未启动",
}
```

测试 `set_chat_state(state, message)`：只有字段发生变化时才增加 `revision`；保留所有无关状态；拒绝 `stopped`、`loading`、`ready`、`generating`、`fallback` 和 `error` 以外的状态。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_control_api.py -q
```

- [ ] **步骤 3：在 `ControlApiStateStore` 中实现聊天状态**

聊天状态使用嵌套字典保存，生成快照时复制该字典，并添加受锁保护的 setter。不要复用现有通用 `status` 字段，该字段继续用于素材和播放反馈。

- [ ] **步骤 4：运行针对性测试并提交**

```powershell
python -m pytest tests/test_control_api.py -q
git add control_api.py tests/test_control_api.py
git commit -m "feat: expose local chat runtime state"
```

## 任务 2：把运行时回调桥接到 Qt 主线程

**文件：**
- 新建：`chat_qt_bridge.py`
- 新建：`tests/test_chat_qt_bridge.py`

- [ ] **步骤 1：编写会失败的信号测试**

使用现有 `QApplication` fixture，连接收集器并验证以下公共回调方法会发出匹配的信号：

```python
bridge.handle_state_change("ready", "本地模型已就绪")
bridge.handle_reply("晚上好。")
bridge.handle_fallback("你好", "worker unavailable")
```

信号定义：

```python
state_changed = pyqtSignal(str, str)
reply_ready = pyqtSignal(str)
fallback_requested = pyqtSignal(str, str)
```

从后台 `threading.Thread` 调用每个回调，处理 Qt 事件，并断言连接的 slot 通过 Qt 队列安全执行。

- [ ] **步骤 2：运行测试并确认导入失败**

```powershell
python -m pytest tests/test_chat_qt_bridge.py -q
```

- [ ] **步骤 3：实现信号桥**

`ChatQtBridge(QObject)` 只包含三个信号和三个回调方法。它不得导入 `ChatService`、加载模型、操作控件或包含回退业务逻辑。

- [ ] **步骤 4：运行测试并提交**

```powershell
python -m pytest tests/test_chat_qt_bridge.py -q
git add chat_qt_bridge.py tests/test_chat_qt_bridge.py
git commit -m "feat: bridge chat callbacks to qt"
```

## 任务 3：在应用启动流程中接入 `ChatService`

**文件：**
- 修改：`main.py`
- 修改：`tests/test_main.py`

- [ ] **步骤 1：使用假服务添加会失败的集成测试**

让 `main.main()` 接受服务工厂，或提取一个接收兼容 `ChatService` 对象的 `ApplicationChatController`。测试不得启动真实模型。

验证：

- 建立全部信号连接后，启动流程只调用一次 `service.start()`；
- 接受聊天文本时调用 `service.submit(text)`，且不会立即调用 `LocalDialogue`；
- 忽略空白文本；
- submit 被拒绝时调用 `LocalDialogue.reply_for_text(text)`，并通过 `window.say` 显示；
- `reply_ready` 通过 `window.say` 显示模型文本；
- `fallback_requested` 使用原始用户文本生成一次本地回退回复；
- 状态变化调用 `api_store.set_chat_state`；
- `app.aboutToQuit` 只停止一次服务。

- [ ] **步骤 2：运行针对性测试并确认失败**

```powershell
python -m pytest tests/test_main.py -q
```

- [ ] **步骤 3：连接服务所有权和回调流程**

保留现有 `LocalDialogue` 实例。创建 `ChatQtBridge`，把它的回调方法传给 `ChatService`，连接完桥接信号后再调用 `start()`。

聊天流程必须等价于：

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

`reason` 只用于诊断，不得显示在桌宠对话气泡中。

- [ ] **步骤 4：保持 UI 线程边界**

只有 Qt slot 可以调用 `window.say()` 或修改 `ControlApiStateStore`。`ChatService` 的读取线程和定时器线程只能调用信号桥回调方法。添加断言或测试钩子，证明回复显示逻辑运行在 `QApplication.instance().thread()` 上。

- [ ] **步骤 5：运行集成测试和回归测试**

```powershell
python -m pytest tests/test_main.py tests/test_chat_qt_bridge.py tests/test_control_api.py -q
python -m pytest -q
```

- [ ] **步骤 6：提交应用接线改动**

```powershell
git add main.py tests/test_main.py
git commit -m "feat: route desktop chat through local llm"
```

## 任务 4：在 Electron 控制面板中显示聊天状态

**文件：**
- 修改：`web_control_panel/app.js`
- 修改：`web_control_panel/index.html`
- 修改：`tests/test_web_control_panel.py`

- [ ] **步骤 1：扩展会失败的静态行为测试**

断言 JavaScript 状态包含嵌套的 `chat` 对象；API patch 合并 `chat`，而不是替换无关状态；渲染逻辑根据聊天状态决定按钮行为。

必须实现以下行为：

| 状态 | 按钮 | 输入框 | 可见状态文字 |
|---|---|---|---|
| `stopped` | 禁用 | 启用 | 本地模型尚未启动 |
| `loading` | 禁用 | 启用 | 正在加载本地模型 |
| `ready` | 启用 | 启用 | 本地模型已就绪 |
| `generating` | 禁用 | 禁用 | 正在生成回复 |
| `fallback` | 启用 | 启用 | 当前使用基础回复 |
| `error` | 启用 | 启用 | 本地模型异常，使用基础回复 |

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_web_control_panel.py -q
```

- [ ] **步骤 3：实现状态渲染**

按钮文字始终保持为 `发送`，状态通过现有状态区域显示。生成期间添加 `aria-busy="true"`。第一版不得添加设置页、模型选择器、流式文本或模型下载控件。

`/api/chat` 成功后才清空输入框。轮询继续提供权威运行时状态。HTTP 请求失败时恢复用户输入的文本，并通过现有状态机制显示传输错误。

- [ ] **步骤 4：运行前端测试和语法检查**

```powershell
python -m pytest tests/test_web_control_panel.py tests/test_control_api.py -q
node --check web_control_panel/app.js
```

- [ ] **步骤 5：提交控制面板行为改动**

```powershell
git add web_control_panel/app.js web_control_panel/index.html tests/test_web_control_panel.py
git commit -m "feat: show local chat status in control panel"
```

## 任务 5：明确处理环境或适配器缺失情况

**文件：**
- 修改：`main.py`
- 修改：`chat_service.py`
- 修改：`tests/test_main.py`
- 修改：`tests/test_chat_service.py`

- [ ] **步骤 1：添加会失败的回退矩阵测试**

覆盖以下启动情况：

| 条件 | 预期行为 |
|---|---|
| 缺少 `.venv-llm` | 应用正常打开；聊天状态为 `fallback`；本地回复可用 |
| worker 导入失败 | 应用正常打开；聊天状态为 `fallback`；记录错误日志 |
| 缺少适配器但基础模型已有缓存 | worker 进入 `ready`，且 `adapter_loaded=false` |
| 离线时基础模型不可用 | 应用正常打开；聊天状态为 `fallback`；本地回复可用 |
| 生成超时 | 当前提示获得一次本地回复；服务尝试重启一次 |
| 加载期间关闭应用 | 终止 worker，且关闭流程不被阻塞 |

- [ ] **步骤 2：运行针对性测试并确认新增用例失败**

```powershell
python -m pytest tests/test_main.py tests/test_chat_service.py -q
```

- [ ] **步骤 3：实现对用户安全的状态消息**

在 `main.py` 中把内部错误映射为简短中文状态消息；完整异常详情只保留在日志中。UI 不得显示文件系统路径、Python 回溯、软件包名称或 CUDA 详情。

使用以下消息：

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

- [ ] **步骤 4：运行测试并提交**

```powershell
python -m pytest tests/test_main.py tests/test_chat_service.py -q
git add main.py chat_service.py tests/test_main.py tests/test_chat_service.py
git commit -m "fix: keep chat usable when local model fails"
```

## 任务 6：确保模型资源不进入 Windows 安装包

**文件：**
- 修改：`build_windows.ps1`
- 修改：`DesktopPet.spec`
- 修改：`README.md`
- 新建：`tests/test_llm_packaging_boundary.py`

- [ ] **步骤 1：编写会失败的打包边界测试**

断言 `DesktopPet.spec` 和 `build_windows.ps1` 不收集 `torch`、`transformers`、`bitsandbytes`、`peft`、`.venv-llm`、`llm_lab/adapters`、模型缓存目录或适配器权重。桌宠所需的运行时源码模块通过普通 Python 导入纳入包中。

- [ ] **步骤 2：运行测试**

```powershell
python -m pytest tests/test_llm_packaging_boundary.py -q
```

预期：如果当前收集规则过宽、会包含训练或模型资源，则测试失败；否则测试可以通过，并在修改前固定打包边界。

- [ ] **步骤 3：仅在需要时收紧打包规则**

开发期间，打包后的桌宠可以启动项目旁边单独安装的 `.venv-llm`，但第一版发布不承诺内置模型运行时。更新 README 运行说明，明确区分：

```text
仅桌宠模式：使用现有应用依赖，通过 LocalDialogue 回退回复。
本地大模型模式：需要项目源码、.venv-llm，以及已下载的基础模型和适配器。
```

不得改变现有 Electron 打包或视频素材行为。

- [ ] **步骤 4：运行打包测试并构建**

```powershell
python -m pytest tests/test_llm_packaging_boundary.py -q
pwsh -NoLogo -NoProfile -File .\build_windows.ps1
```

预期：构建成功，且不会把模型权重、大模型 Python 软件包或 `.venv-llm` 复制到 `dist`。

- [ ] **步骤 5：冒烟测试打包后的回退路径**

在无法发现 `.venv-llm` 的位置临时运行打包后的应用。确认桌宠和控制面板正常打开、聊天状态显示回退，并且输入一条消息后能收到 `LocalDialogue` 回复。

- [ ] **步骤 6：提交打包文档和测试**

```powershell
git add build_windows.ps1 DesktopPet.spec README.md tests/test_llm_packaging_boundary.py
git commit -m "docs: define local llm packaging boundary"
```

## 任务 7：桌宠端到端验证

- [ ] 运行完整自动化测试套件：

```powershell
python -m pytest -q
node --check web_control_panel/app.js
```

- [ ] 从 PowerShell 7 启动应用：

```powershell
python main.py
```

- [ ] 手动验证正常模型路径：

1. 控制面板打开，同时桌宠保持响应。
2. 状态从加载变为就绪，两个 UI 都没有冻结。
3. 输入 `晚上好，今天工作有点累` 并发送一次。
4. 生成期间发送按钮处于禁用状态。
5. 桌宠对话气泡中出现一条模型回复。
6. 完成 10 轮对话后聊天仍然可用，内存不会无限增长。

- [ ] 手动验证回退路径：

1. 关闭应用，临时重命名 `.venv-llm`。
2. 再次运行 `python main.py`。
3. 确认应用正常打开，状态提示当前使用基础回复模式。
4. 发送一条消息，确认 `LocalDialogue` 能够回复。
5. 恢复 `.venv-llm` 目录名称。

- [ ] 验证干净关闭：

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'llm_worker\.py' } | Select-Object ProcessId, CommandLine
```

关闭应用后的预期结果：没有匹配进程。

- [ ] 完成前检查范围：

```powershell
git diff --stat HEAD~6..HEAD
git status --short
```

预期：没有加入流式实现、在线 API、持久记忆、桌宠动作控制、模型选择器或打包后的模型权重。
