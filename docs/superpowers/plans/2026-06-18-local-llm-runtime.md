# Local LLM Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a tested local chat runtime that loads the accepted Qwen adapter in a separate process and exposes reliable asynchronous requests without importing model libraries into the PyQt process.

**Architecture:** `llm_worker.py` owns Transformers, CUDA, tokenizer, model, adapter, and conversation generation. `chat_service.py` owns process lifecycle, one-request-at-a-time queuing, timeouts, restart policy, and callbacks. Both communicate through one-line JSON messages on stdin/stdout; worker diagnostics use stderr only.

**Tech Stack:** Python 3.11 standard library, Transformers/PEFT/bitsandbytes in the worker environment, pytest, JSON Lines, PowerShell 7

---

## Task 1: Define a Strict JSON Lines Protocol

**Files:**
- Create: `llm_protocol.py`
- Create: `tests/test_llm_protocol.py`

- [ ] **Step 1: Write failing protocol tests**

Cover valid round trips and malformed input:

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

Also test unknown message types, missing request IDs, invalid roles, empty user text, multi-line output, non-object JSON, and result/error events without matching fields.

- [ ] **Step 2: Run and confirm import failure**

```powershell
python -m pytest tests/test_llm_protocol.py -q
```

- [ ] **Step 3: Implement typed protocol messages**

Use frozen dataclasses and compact UTF-8-safe JSON serialization. Define these wire messages:

```json
{"type":"chat","request_id":"req-1","messages":[{"role":"user","content":"你好"}],"generation":{"max_new_tokens":128,"temperature":0.7,"top_p":0.8,"top_k":20}}
{"type":"ready","model_id":"Qwen/Qwen3-1.7B","adapter_loaded":true}
{"type":"result","request_id":"req-1","text":"你好呀。","input_tokens":16,"output_tokens":8,"elapsed_ms":420}
{"type":"error","request_id":"req-1","code":"generation_failed","message":"generation failed"}
```

Protocol validation must reject embedded newlines in serialized lines and must never deserialize arbitrary Python objects.

- [ ] **Step 4: Run focused tests**

```powershell
python -m pytest tests/test_llm_protocol.py -q
```

- [ ] **Step 5: Commit the protocol**

```powershell
git add llm_protocol.py tests/test_llm_protocol.py
git commit -m "feat: define local llm worker protocol"
```

## Task 2: Implement Bounded Conversation History

**Files:**
- Create: `chat_history.py`
- Create: `tests/test_chat_history.py`

- [ ] **Step 1: Write failing history tests**

The tests must prove that history:

- stores complete user/assistant rounds only;
- keeps at most 10 completed rounds;
- drops oldest complete rounds until the context estimate is at most 2048 tokens;
- always preserves the newest user message;
- does not mutate the caller's message objects;
- clears completely on request.

Use an injected `count_tokens(messages)` function so tests do not require Transformers.

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests/test_chat_history.py -q
```

- [ ] **Step 3: Implement the history object**

Expose a `ConversationHistory` class with these exact typed methods: constructor arguments `max_rounds: int = 10` and `max_tokens: int = 2048`; `build_request_messages(user_text: str, count_tokens: TokenCounter) -> Sequence[dict[str, str]]`; `append_result(user_text: str, assistant_text: str) -> None`; and `clear() -> None`.

Use a conservative standard-library estimate of one token per Chinese character and one token per four ASCII characters until the worker returns tokenizer-based counts. The estimator must be deterministic.

- [ ] **Step 4: Run focused tests and commit**

```powershell
python -m pytest tests/test_chat_history.py -q
git add chat_history.py tests/test_chat_history.py
git commit -m "feat: add bounded chat history"
```

## Task 3: Implement the Worker with an Injectable Engine

**Files:**
- Create: `llm_worker.py`
- Create: `tests/test_llm_worker.py`

- [ ] **Step 1: Write failing worker-loop tests**

Run `worker_loop` with `io.StringIO` streams and a fake engine. Verify:

- exactly one `ready` event is emitted after successful initialization;
- one request produces exactly one result line;
- malformed requests produce a sanitized error line and do not stop the loop;
- generation exceptions use code `generation_failed` and do not leak traceback text to stdout;
- all diagnostics go to the injected stderr stream;
- EOF exits with status zero.

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests/test_llm_worker.py -q
```

- [ ] **Step 3: Implement the protocol loop before model loading**

Use a `worker_loop(engine: ChatEngine, input_stream: TextIO, output_stream: TextIO, error_stream: TextIO) -> int` function so every dependency is injectable.

Flush stdout after every event. Never call `print()` without an explicit stream. Catch per-request exceptions, but let initialization failure return a non-zero process status after logging details to stderr.

- [ ] **Step 4: Implement `TransformersChatEngine` lazily**

Heavy imports must stay inside `TransformersChatEngine.load()`. Load `Qwen/Qwen3-1.7B` with NF4 double quantization and bfloat16 compute. If the configured adapter directory exists, attach it with PEFT; if it is absent, log the fallback and use the base model.

Generation must call the Qwen chat template with `enable_thinking=False`, use `max_new_tokens=128`, `temperature=0.7`, `top_p=0.8`, `top_k=20`, and decode only newly generated tokens. Return measured input tokens, output tokens, and elapsed milliseconds.

Supported CLI arguments:

```text
--model-id Qwen/Qwen3-1.7B
--adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
--max-context-tokens 2048
```

- [ ] **Step 5: Run worker tests**

```powershell
python -m pytest tests/test_llm_worker.py -q
```

- [ ] **Step 6: Run a real worker protocol smoke test**

Use PowerShell to send one line and inspect stdout separately from stderr:

```powershell
$request = '{"type":"chat","request_id":"smoke-1","messages":[{"role":"user","content":"你好，请用一句话介绍自己。"}],"generation":{"max_new_tokens":128,"temperature":0.7,"top_p":0.8,"top_k":20}}'
$request | & ".\.venv-llm\python.exe" -u llm_worker.py --model-id Qwen/Qwen3-1.7B --adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1 2> llm-worker-smoke.log
```

Expected stdout: one `ready` event and one `result` event, each on a single valid JSON line. `llm-worker-smoke.log` may contain loading diagnostics but no protocol events.

- [ ] **Step 7: Commit the worker**

```powershell
git add llm_worker.py tests/test_llm_worker.py
git commit -m "feat: add isolated local llm worker"
```

## Task 4: Add a Fake Worker Process for Lifecycle Tests

**Files:**
- Create: `tests/fixtures/fake_llm_worker.py`
- Create: `tests/test_fake_llm_worker.py`

- [ ] **Step 1: Write a subprocess contract test**

Start the fixture with the current test interpreter. Assert it emits `ready`, echoes a deterministic result, can delay a response, can emit malformed output, can exit on demand, and writes diagnostics to stderr only.

- [ ] **Step 2: Implement fixture modes**

Support command-line modes:

```text
normal
slow
malformed
crash-once
init-failure
```

For input `你好`, the normal reply must be exactly `fake:你好`. The slow mode delay must be configurable with `--delay-seconds`. Crash-once must use a marker-file argument so the restarted process succeeds.

- [ ] **Step 3: Run and commit**

```powershell
python -m pytest tests/test_fake_llm_worker.py -q
git add tests/fixtures/fake_llm_worker.py tests/test_fake_llm_worker.py
git commit -m "test: add deterministic llm worker fixture"
```

## Task 5: Implement Asynchronous `ChatService`

**Files:**
- Create: `chat_service.py`
- Create: `tests/test_chat_service.py`

- [ ] **Step 1: Write failing public-contract tests**

Instantiate the service with the fake worker and callback collectors. Test:

- `start()` returns immediately and later reports `loading` then `ready`;
- `submit("你好")` returns `True` only when a request is accepted;
- empty input and a second request while busy return `False`;
- a result calls `on_reply(text)` and returns state to `ready`;
- a result appends one history round;
- startup failure enters `fallback`;
- request timeout kills the worker, restarts once, and calls `on_fallback(original_text, reason)`;
- malformed stdout triggers the same bounded restart path;
- process exit during generation does not lose the original text;
- `stop()` terminates threads and the child process within five seconds.

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests/test_chat_service.py -q
```

- [ ] **Step 3: Implement environment discovery and command construction**

Resolve the worker interpreter in this order:

1. Explicit `python_executable` constructor argument.
2. `PROJECT_ROOT/.venv-llm/python.exe` for a conda prefix environment.
3. `PROJECT_ROOT/.venv-llm/Scripts/python.exe` for a virtual environment.

If none exists, report `fallback` without spawning. Build the worker command as an argument list, never a shell string, and pass `-u` for unbuffered protocol output.

- [ ] **Step 4: Implement lifecycle and reader threads**

Use `subprocess.Popen` with text mode UTF-8, line buffering, stdin/stdout/stderr pipes, and no visible console window on Windows. Own exactly one stdout reader thread, one stderr reader thread, and one timeout timer per active request. Protect mutable state with a lock and never invoke user callbacks while holding it.

Public surface: `start() -> None`, `submit(user_text: str) -> bool`, `clear_history() -> None`, `stop() -> None`, and read-only property `state: str`.

Constructor callbacks:

```python
on_state_change(state: str, message: str) -> None
on_reply(text: str) -> None
on_fallback(original_text: str, reason: str) -> None
```

Allowed states: `stopped`, `loading`, `ready`, `generating`, `fallback`, `error`.

- [ ] **Step 5: Implement bounded recovery**

Startup ready timeout: 120 seconds. Generation timeout: 30 seconds. On a protocol failure, timeout, or unexpected exit, terminate the process tree, start one replacement worker, and retry no user request automatically. The original request must go to `on_fallback`. A second failure without an intervening successful result leaves the service in `fallback`; it must not restart forever.

- [ ] **Step 6: Run focused tests and inspect thread cleanup**

```powershell
python -m pytest tests/test_chat_service.py -q
```

Expected: no hanging process and no non-daemon worker thread remains after each test.

- [ ] **Step 7: Commit the service**

```powershell
git add chat_service.py tests/test_chat_service.py
git commit -m "feat: add asynchronous local chat service"
```

## Task 6: Add Runtime Diagnostics Without Polluting the Protocol

**Files:**
- Modify: `chat_service.py`
- Modify: `llm_worker.py`
- Create: `tests/test_llm_runtime_logging.py`

- [ ] **Step 1: Write failing logging tests**

Inject a logger and assert messages contain lifecycle state, process exit code, request ID, elapsed time, and sanitized error code. Assert user prompt and full generated response are not logged by default.

- [ ] **Step 2: Implement standard logging**

Use module loggers. The service consumes worker stderr line by line at debug level. Logs must never be forwarded to stdout and must not contain model binary paths beyond project-relative adapter names.

- [ ] **Step 3: Run tests and commit**

```powershell
python -m pytest tests/test_llm_runtime_logging.py tests/test_chat_service.py tests/test_llm_worker.py -q
git add chat_service.py llm_worker.py tests/test_llm_runtime_logging.py
git commit -m "chore: add local llm runtime diagnostics"
```

## Task 7: Verify the Runtime End to End

- [ ] Run all runtime tests under the normal desktop Python environment:

```powershell
python -m pytest tests/test_llm_protocol.py tests/test_chat_history.py tests/test_llm_worker.py tests/test_fake_llm_worker.py tests/test_chat_service.py tests/test_llm_runtime_logging.py -q
```

- [ ] Run the complete existing suite:

```powershell
python -m pytest -q
```

- [ ] Run a real service smoke script with the LLM environment:

```powershell
& ".\.venv-llm\python.exe" -c "from chat_service import ChatService; import time; s=ChatService(on_state_change=lambda a,b: print(a,b), on_reply=print, on_fallback=print); s.start(); time.sleep(90); print('accepted', s.submit('晚上好，今天有点累')); time.sleep(35); s.stop()"
```

Expected: service reaches `ready`, accepts one request, prints one reply, and stops without a remaining `llm_worker.py` process.

- [ ] Inspect for accidental model imports in the desktop process boundary:

```powershell
rg "^(from|import) (torch|transformers|peft|trl|bitsandbytes)" --glob "*.py" --glob "!llm_worker.py" --glob "!llm_lab/**"
```

Expected: no matches outside `llm_worker.py` and `llm_lab/`.

- [ ] Inspect the commit series:

```powershell
git log --oneline -6
```

Expected: protocol, history, worker, fake worker, service, and diagnostics are separately reviewable.
