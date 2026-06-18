# 本地大模型运行时实施计划

> **供智能代理执行：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 子技能，按任务逐项实施。本计划使用复选框（`- [ ]`）跟踪进度。

**目标：** 提供经过测试的本地聊天运行时，在独立进程中加载通过验收的 Qwen 适配器，并提供可靠的异步请求接口，确保 PyQt 进程不导入模型库。

**架构：** `llm_worker.py` 负责 Transformers、CUDA、分词器、模型、适配器和对话生成。`chat_service.py` 负责进程生命周期、单请求队列、超时、重启策略和回调。双方通过 stdin/stdout 上的单行 JSON 消息通信；worker 的诊断信息只能写入 stderr。

**技术栈：** Python 3.11 标准库、worker 环境中的 Transformers/PEFT/bitsandbytes、pytest、JSON Lines、PowerShell 7

---

## 任务 1：定义严格的 JSON Lines 协议

**文件：**
- 新建：`llm_protocol.py`
- 新建：`tests/test_llm_protocol.py`

- [ ] **步骤 1：编写会失败的协议测试**

覆盖有效的往返转换和错误输入：

```python
from llm_protocol import ChatRequest, ResultEvent, decode_event, decode_request


def test_chat_request_round_trip():
    request = ChatRequest(
        request_id="req-1",
        messages=({"role": "user", "content": "你好"},),
        max_new_tokens=128,
        temperature=0.7,
        top_p=0.8,
        top_k=20,
    )

    assert decode_request(request.to_json_line()) == request


def test_result_event_round_trip():
    event = ResultEvent(request_id="req-1", text="你好呀。")

    assert decode_event(event.to_json_line()) == event
```

还要测试未知消息类型、缺少请求 ID、无效角色、空用户文本、多行输出、非对象 JSON，以及缺少对应字段的 result/error 事件。

- [ ] **步骤 2：运行测试并确认导入失败**

```powershell
python -m pytest tests/test_llm_protocol.py -q
```

- [ ] **步骤 3：实现带类型的协议消息**

使用冻结的 dataclass 和紧凑、UTF-8 安全的 JSON 序列化。定义以下线协议消息：

```json
{"type":"chat","request_id":"req-1","messages":[{"role":"user","content":"你好"}],"generation":{"max_new_tokens":128,"temperature":0.7,"top_p":0.8,"top_k":20}}
{"type":"ready","model_id":"Qwen/Qwen3-1.7B","adapter_loaded":true}
{"type":"result","request_id":"req-1","text":"你好呀。","input_tokens":16,"output_tokens":8,"elapsed_ms":420}
{"type":"error","request_id":"req-1","code":"generation_failed","message":"generation failed"}
```

协议校验必须拒绝序列化行中嵌入的换行符，且不得反序列化任意 Python 对象。

- [ ] **步骤 4：运行针对性测试**

```powershell
python -m pytest tests/test_llm_protocol.py -q
```

- [ ] **步骤 5：提交协议实现**

```powershell
git add llm_protocol.py tests/test_llm_protocol.py
git commit -m "feat: define local llm worker protocol"
```

## 任务 2：实现有界对话历史

**文件：**
- 新建：`chat_history.py`
- 新建：`tests/test_chat_history.py`

- [ ] **步骤 1：编写会失败的历史记录测试**

测试必须证明历史记录：

- 只保存完整的用户/助手轮次；
- 最多保留 10 个已完成轮次；
- 删除最早的完整轮次，直到上下文估算值不超过 2048 token；
- 始终保留最新用户消息；
- 不修改调用方传入的消息对象；
- 收到清空请求后完全清除。

注入 `count_tokens(messages)` 函数，使测试不依赖 Transformers。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_chat_history.py -q
```

- [ ] **步骤 3：实现历史记录对象**

提供 `ConversationHistory` 类，包含以下准确的类型接口：构造参数 `max_rounds: int = 10` 和 `max_tokens: int = 2048`；`build_request_messages(user_text: str, count_tokens: TokenCounter) -> Sequence[dict[str, str]]`；`append_result(user_text: str, assistant_text: str) -> None`；`clear() -> None`。

在 worker 返回基于分词器的计数前，使用保守的标准库估算：每个中文字符按一个 token、每四个 ASCII 字符按一个 token 计算。估算结果必须确定且可复现。

- [ ] **步骤 4：运行针对性测试并提交**

```powershell
python -m pytest tests/test_chat_history.py -q
git add chat_history.py tests/test_chat_history.py
git commit -m "feat: add bounded chat history"
```

## 任务 3：使用可注入引擎实现 Worker

**文件：**
- 新建：`llm_worker.py`
- 新建：`tests/test_llm_worker.py`

- [ ] **步骤 1：编写会失败的 worker 循环测试**

使用 `io.StringIO` 流和假引擎运行 `worker_loop`。验证：

- 初始化成功后只发出一个 `ready` 事件；
- 一个请求只产生一行 result；
- 错误请求产生经过清理的 error 行，且循环不会停止；
- 生成异常使用错误码 `generation_failed`，stdout 不泄漏回溯文本；
- 所有诊断信息都进入注入的 stderr 流；
- 遇到 EOF 时以状态码 0 退出。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_llm_worker.py -q
```

- [ ] **步骤 3：先于模型加载实现协议循环**

使用 `worker_loop(engine: ChatEngine, input_stream: TextIO, output_stream: TextIO, error_stream: TextIO) -> int` 函数，使所有依赖都可注入。

每个事件输出后必须刷新 stdout。不得在不指定 stream 的情况下调用 `print()`。捕获单个请求的异常，但初始化失败时应把详细信息写入 stderr，并返回非零进程状态码。

- [ ] **步骤 4：延迟实现 `TransformersChatEngine`**

重量级导入必须放在 `TransformersChatEngine.load()` 内部。使用 NF4 双重量化和 bfloat16 计算加载 `Qwen/Qwen3-1.7B`。如果配置的适配器目录存在，通过 PEFT 附加适配器；如果不存在，记录回退信息并使用基础模型。

生成过程必须调用 `enable_thinking=False` 的 Qwen 对话模板，使用 `max_new_tokens=128`、`temperature=0.7`、`top_p=0.8`、`top_k=20`，并且只解码新生成的 token。返回测得的输入 token 数、输出 token 数和耗时毫秒数。

支持以下 CLI 参数：

```text
--model-id Qwen/Qwen3-1.7B
--adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
--max-context-tokens 2048
```

- [ ] **步骤 5：运行 worker 测试**

```powershell
python -m pytest tests/test_llm_worker.py -q
```

- [ ] **步骤 6：执行真实 worker 协议冒烟测试**

使用 PowerShell 发送一行请求，并分别检查 stdout 和 stderr：

```powershell
$request = '{"type":"chat","request_id":"smoke-1","messages":[{"role":"user","content":"你好，请用一句话介绍自己。"}],"generation":{"max_new_tokens":128,"temperature":0.7,"top_p":0.8,"top_k":20}}'
$request | & ".\.venv-llm\python.exe" -u llm_worker.py --model-id Qwen/Qwen3-1.7B --adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1 2> llm-worker-smoke.log
```

预期 stdout：一个 `ready` 事件和一个 `result` 事件，每个事件各占一行有效 JSON。`llm-worker-smoke.log` 可以包含加载诊断信息，但不得包含协议事件。

- [ ] **步骤 7：提交 worker**

```powershell
git add llm_worker.py tests/test_llm_worker.py
git commit -m "feat: add isolated local llm worker"
```

## 任务 4：为生命周期测试添加假 Worker 进程

**文件：**
- 新建：`tests/fixtures/fake_llm_worker.py`
- 新建：`tests/test_fake_llm_worker.py`

- [ ] **步骤 1：编写子进程契约测试**

使用当前测试解释器启动 fixture。断言它会发出 `ready`、返回确定性结果、支持延迟回复、能发出错误格式输出、可以按要求退出，并且诊断信息只写入 stderr。

- [ ] **步骤 2：实现 fixture 模式**

支持以下命令行模式：

```text
normal
slow
malformed
crash-once
init-failure
```

输入 `你好` 时，normal 模式回复必须严格等于 `fake:你好`。slow 模式延迟时间通过 `--delay-seconds` 配置。crash-once 必须使用标记文件参数，使重启后的进程能够成功运行。

- [ ] **步骤 3：运行测试并提交**

```powershell
python -m pytest tests/test_fake_llm_worker.py -q
git add tests/fixtures/fake_llm_worker.py tests/test_fake_llm_worker.py
git commit -m "test: add deterministic llm worker fixture"
```

## 任务 5：实现异步 `ChatService`

**文件：**
- 新建：`chat_service.py`
- 新建：`tests/test_chat_service.py`

- [ ] **步骤 1：编写会失败的公共契约测试**

使用假 worker 和回调收集器实例化服务。测试：

- `start()` 立即返回，随后依次报告 `loading` 和 `ready`；
- 只有请求被接受时，`submit("你好")` 才返回 `True`；
- 空输入以及忙碌时的第二个请求返回 `False`；
- 收到结果后调用 `on_reply(text)` 并恢复 `ready` 状态；
- 收到结果后向历史记录追加一个轮次；
- 启动失败后进入 `fallback`；
- 请求超时后终止 worker、重启一次，并调用 `on_fallback(original_text, reason)`；
- stdout 格式错误走相同的有限重启路径；
- 生成期间进程退出时不丢失原始文本；
- `stop()` 在五秒内终止线程和子进程。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_chat_service.py -q
```

- [ ] **步骤 3：实现环境发现和命令构造**

按以下顺序解析 worker 解释器：

1. 构造函数显式传入的 `python_executable`。
2. conda 前缀环境中的 `PROJECT_ROOT/.venv-llm/python.exe`。
3. 虚拟环境中的 `PROJECT_ROOT/.venv-llm/Scripts/python.exe`。

如果全部不存在，直接报告 `fallback`，不启动进程。worker 命令必须使用参数列表构造，不得使用 shell 字符串，并传入 `-u` 以禁用协议输出缓冲。

- [ ] **步骤 4：实现生命周期和读取线程**

使用 `subprocess.Popen`，启用 UTF-8 文本模式、行缓冲以及 stdin/stdout/stderr 管道；在 Windows 上不得显示控制台窗口。每个活动进程只允许拥有一个 stdout 读取线程、一个 stderr 读取线程，以及每个活动请求一个超时定时器。使用锁保护可变状态，持锁期间不得调用用户回调。

公共接口：`start() -> None`、`submit(user_text: str) -> bool`、`clear_history() -> None`、`stop() -> None`，以及只读属性 `state: str`。

构造函数回调：

```python
on_state_change(state: str, message: str) -> None
on_reply(text: str) -> None
on_fallback(original_text: str, reason: str) -> None
```

允许的状态：`stopped`、`loading`、`ready`、`generating`、`fallback`、`error`。

- [ ] **步骤 5：实现有限恢复策略**

启动 ready 超时为 120 秒，生成超时为 30 秒。发生协议错误、超时或意外退出时，终止进程树并启动一个替代 worker，但不得自动重试用户请求。原请求必须传给 `on_fallback`。如果在没有成功结果的情况下再次失败，服务保持 `fallback`，不得无限重启。

- [ ] **步骤 6：运行针对性测试并检查线程清理**

```powershell
python -m pytest tests/test_chat_service.py -q
```

预期：每个测试结束后没有挂起进程，也没有残留的非守护 worker 线程。

- [ ] **步骤 7：提交服务实现**

```powershell
git add chat_service.py tests/test_chat_service.py
git commit -m "feat: add asynchronous local chat service"
```

## 任务 6：添加不会污染协议的运行时诊断

**文件：**
- 修改：`chat_service.py`
- 修改：`llm_worker.py`
- 新建：`tests/test_llm_runtime_logging.py`

- [ ] **步骤 1：编写会失败的日志测试**

注入 logger，断言消息包含生命周期状态、进程退出码、请求 ID、耗时和经过清理的错误码。默认不得记录用户提示词和完整生成回复。

- [ ] **步骤 2：实现标准日志记录**

使用模块级 logger。服务逐行读取 worker 的 stderr，并以 debug 级别记录。日志不得转发到 stdout；模型二进制路径不得完整出现，只允许记录项目相对的适配器名称。

- [ ] **步骤 3：运行测试并提交**

```powershell
python -m pytest tests/test_llm_runtime_logging.py tests/test_chat_service.py tests/test_llm_worker.py -q
git add chat_service.py llm_worker.py tests/test_llm_runtime_logging.py
git commit -m "chore: add local llm runtime diagnostics"
```

## 任务 7：端到端验证运行时

- [ ] 使用普通桌宠 Python 环境运行全部运行时测试：

```powershell
python -m pytest tests/test_llm_protocol.py tests/test_chat_history.py tests/test_llm_worker.py tests/test_fake_llm_worker.py tests/test_chat_service.py tests/test_llm_runtime_logging.py -q
```

- [ ] 运行完整现有测试套件：

```powershell
python -m pytest -q
```

- [ ] 使用大模型环境运行真实服务冒烟脚本：

```powershell
& ".\.venv-llm\python.exe" -c "from chat_service import ChatService; import time; s=ChatService(on_state_change=lambda a,b: print(a,b), on_reply=print, on_fallback=print); s.start(); time.sleep(90); print('accepted', s.submit('晚上好，今天有点累')); time.sleep(35); s.stop()"
```

预期：服务进入 `ready`，接受一个请求，打印一条回复，并且停止后不残留 `llm_worker.py` 进程。

- [ ] 检查桌宠进程边界中是否意外导入模型库：

```powershell
rg "^(from|import) (torch|transformers|peft|trl|bitsandbytes)" --glob "*.py" --glob "!llm_worker.py" --glob "!llm_lab/**"
```

预期：除 `llm_worker.py` 和 `llm_lab/` 外没有匹配结果。

- [ ] 检查提交序列：

```powershell
git log --oneline -6
```

预期：协议、历史记录、worker、假 worker、服务和诊断分别位于可独立审查的提交中。
