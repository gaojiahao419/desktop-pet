# 桌面宠物本地小型语言模型设计

## 1. 目标

在现有桌面宠物项目中加入本地中文聊天能力，并让开发者完整参与数据准备、监督微调、评估、本地推理和应用接入过程。

第一版基于开源模型进行参数高效微调，不从零预训练语言模型。目标模型为 `Qwen/Qwen3-1.7B`，使用 4-bit QLoRA 在本机 RTX 4060 Laptop 8GB 显存环境中训练。

第一版成功标准：

- 支持自然的日常中文聊天。
- 保留最近 10 轮对话，并将输入限制在约 2048 token 内。
- 模型推理不阻塞 PyQt5 桌宠和 Electron 控制台。
- 模型不可用时自动回退到现有 `LocalDialogue`。
- 完成基础模型与微调模型的固定测试集对比。
- 保持现有桌宠动作、素材、设置和控制台功能不变。

## 2. 范围

### 2.1 第一版包含

- Qwen3-1.7B 基础模型下载与基线测试。
- 中文日常对话数据集创建、清洗、划分和验证。
- 使用 Transformers、TRL、PEFT 和 bitsandbytes 进行 QLoRA 微调。
- 保存 checkpoint、LoRA Adapter、训练指标和评估结果。
- 独立本地模型进程。
- 桌宠聊天服务、短期对话历史和失败回退。
- 自动化测试与人工聊天验收。

### 2.2 第一版不包含

- 从零预训练模型。
- RLHF、DPO 或其他强化学习对齐。
- 在线模型 API。
- 跨启动长期记忆。
- 语音输入、语音合成或桌宠动作控制。
- 逐 token 流式显示。
- 将 PyTorch 和模型权重打进当前 PyInstaller 发布包。

## 3. 技术选择

### 3.1 基础模型

使用 `Qwen/Qwen3-1.7B`：

- 1.7B 参数，规模适合 8GB 显存上的 QLoRA。
- 支持中文和多轮对话。
- 支持关闭思考模式，适合快速日常聊天。
- Apache 2.0 许可证便于本地学习和后续发布。

推理时使用非思考模式。生成参数从以下值开始，再根据评估调整：

```text
enable_thinking=false
temperature=0.7
top_p=0.8
top_k=20
max_new_tokens=128
```

### 3.2 微调方案

使用 4-bit QLoRA：

- bitsandbytes 将基础模型权重量化为 NF4 4-bit。
- PEFT 为模型添加可训练的 LoRA 参数。
- TRL 的 `SFTTrainer` 负责监督微调流程。
- Transformers 负责模型、Tokenizer、聊天模板和生成。

基础权重在训练期间保持冻结，只更新 LoRA Adapter。这样能显著降低显存需求，并保留可独立替换的训练产物。

### 3.3 环境隔离

训练和推理使用独立环境 `.venv-llm/`，不将 PyTorch、TRL、PEFT 等依赖加入桌宠当前轻量 Python 环境。

依赖记录在 `requirements-llm.txt`。模型进程由该环境的 Python 启动，桌宠主进程继续使用当前 PyQt5 环境。

## 4. 目录结构

```text
desktop  pet/
  llm_lab/
    configs/
      qwen3_1_7b_qlora.json
    data/
      raw/
      processed/
        train.jsonl
        validation.jsonl
        test.jsonl
    adapters/
    checkpoints/
    reports/
    prepare_data.py
    validate_data.py
    train_qlora.py
    evaluate_model.py
    chat_cli.py
  chat_service.py
  llm_worker.py
  llm_protocol.py
  requirements-llm.txt
```

职责边界：

- `llm_lab/` 只负责训练、评估和训练产物。
- `llm_worker.py` 只负责加载模型和生成回复。
- `llm_protocol.py` 定义桌宠与模型进程之间的请求和响应格式。
- `chat_service.py` 管理进程生命周期、对话历史、超时和回退。
- `main.py` 只连接 Qt 信号和聊天服务，不直接导入 PyTorch。

## 5. 数据设计

### 5.1 第一版规模

准备约 600 条高质量中文对话：

| 类别 | 数量 | 目的 |
| --- | ---: | --- |
| 日常闲聊 | 300 | 问候、生活话题、兴趣和轻量交流 |
| 情绪陪伴 | 100 | 疲惫、压力、开心和低落时的自然回应 |
| 多轮追问 | 100 | 学习上下文延续和指代关系 |
| 不确定与边界 | 50 | 不知道、信息不足和不应编造的情况 |
| 简短回复约束 | 50 | 避免过长、过度分析和重复回答 |

数据使用 Hugging Face `messages` 格式：

```json
{"messages":[{"role":"user","content":"今天好累"},{"role":"assistant","content":"辛苦了，先休息一会儿吧。今天最累的是哪件事？"}]}
```

### 5.2 数据规则

- 以自然中文口语为主，不使用大量机械模板。
- 多轮对话按完整会话划分，避免同一会话泄漏到不同数据集。
- 删除空文本、完全重复样本和异常超长样本。
- 对话中不保存真实隐私信息。
- 第一版不使用未经确认许可的数据集。
- 训练集、验证集和测试集按 80%、10%、10% 划分。
- 固定测试集在训练后不得参与调参。

### 5.3 数据构建流程

先人工编写约 120 条覆盖各类别的种子对话，再使用未微调的基础模型为每条种子生成多个表达候选。候选内容必须经过人工筛选和改写，最终形成约 600 条训练数据。

基础模型生成只用于扩充表达方式，不能直接批量写入训练集。人工审核需要删除事实错误、机械模板、长篇推理、重复表达和不自然中文。固定测试集由人工单独编写，不参与候选生成。

## 6. 训练流程

### 6.1 基线

训练前先用基础模型运行固定测试问题并保存结果。后续所有训练版本都与同一基线比较，避免只看训练损失而忽略实际聊天质量。

### 6.2 起始参数

```text
quantization: 4-bit NF4
compute_dtype: bfloat16
lora_rank: 16
lora_alpha: 32
lora_dropout: 0.05
max_sequence_length: 1024
per_device_train_batch_size: 1
gradient_accumulation_steps: 16
learning_rate: 0.0001
epochs: 2
gradient_checkpointing: true
```

参数是第一轮实验起点。每次实验只调整少量变量，并把配置、随机种子和结果保存到报告中。

### 6.3 训练产物

- 每个评估周期的 checkpoint。
- 最终 LoRA Adapter。
- Tokenizer 和聊天模板版本信息。
- 训练与验证 loss。
- 显存峰值、训练耗时和样本吞吐。
- 固定测试问题的生成结果。
- 基础模型与微调模型对比报告。

## 7. 评估设计

第一版准备 100 条固定中文测试问题，覆盖问候、生活闲聊、情绪陪伴、上下文追问、信息不足和重复诱导。

评估维度：

- 相关性：是否回答了当前问题。
- 自然度：是否像正常中文交流。
- 简洁度：是否避免无意义长回答。
- 连贯性：是否正确使用前文信息。
- 诚实性：不知道时是否避免编造。
- 稳定性：是否出现循环、重复或乱码。

使用基础模型和微调模型进行盲测对比。微调模型只有在整体评分提高且没有明显稳定性退化时，才进入桌宠接入阶段。

## 8. 运行时架构

```text
Electron 控制台
  -> /api/chat
  -> main.py: chat_text()
  -> ChatService
  -> llm_worker.py 独立进程
  -> Qwen3-1.7B + LoRA Adapter
  -> ChatService 响应信号
  -> PetWindow.say()
```

### 8.1 模型进程

模型进程负责：

- 启动时加载基础模型和 Adapter。
- 接收结构化聊天请求。
- 应用 Qwen 聊天模板并关闭思考模式。
- 生成完整回复并返回状态、文本和耗时。
- 输出结构化日志，不向标准输出写无关调试文本。

模型进程与桌宠进程隔离。CUDA 错误、模型加载失败或推理崩溃不能导致桌宠退出。

桌宠使用 `.venv-llm/Scripts/python.exe` 启动 `llm_worker.py` 子进程。双方使用标准输入和标准输出传输一行一个 JSON 对象的 JSON Lines 协议。每个请求包含 `request_id` 和 `messages`，每个响应包含相同的 `request_id`、状态、回复文本、错误类型和耗时。标准错误和日志文件用于诊断，标准输出只允许协议消息。

### 8.2 ChatService

`ChatService` 负责：

- 在后台启动和监控模型进程。
- 保存最近 10 轮用户和助手消息。
- 按 Tokenizer 计算上下文长度，超过约 2048 token 时删除最早消息。
- 同一时间只允许一个生成请求。
- 将模型状态映射为 Qt 信号。
- 模型不可用时调用 `LocalDialogue`。

第一版返回完整回复，不实现 token 流式更新。模型可在应用启动后后台预热，预热期间桌宠和控制台保持可操作。

## 9. 错误处理

| 情况 | 处理 |
| --- | --- |
| `.venv-llm` 不存在 | 显示模型环境未安装并回退 `LocalDialogue` |
| 基础模型缺失 | 记录明确路径，回退 `LocalDialogue` |
| Adapter 缺失 | 使用未微调的基础模型，并显示当前为基础模型 |
| 模型加载失败 | 保持桌宠运行，允许手动或下一次请求重试 |
| 推理超过 30 秒 | 终止当前请求，返回简短提示并重启 worker |
| CUDA 显存不足 | 记录 OOM，清理 worker，回退本地预设回复 |
| worker 意外退出 | 下一次聊天前自动重启一次 |
| 用户连续提交 | 拒绝重复请求或提示当前正在生成 |
| 空输入 | 不发送模型请求 |

错误信息写入本地日志，界面只显示用户可理解的简短状态。

## 10. 测试设计

### 10.1 数据与训练测试

- JSONL 格式和角色顺序检查。
- 空文本、重复样本、超长样本检查。
- train、validation、test 会话无交叉检查。
- 训练脚本小样本 smoke test。
- Adapter 保存和重新加载测试。

### 10.2 运行时测试

- 10 轮历史和 2048 token 裁剪测试。
- worker 请求、响应、超时和退出协议测试。
- 使用假模型后端测试成功、失败和 OOM 回退。
- 验证生成期间 Qt 主线程不阻塞。
- 验证模型缺失时桌宠仍能启动。
- 验证现有 `/api/chat` 与宠物气泡链路继续工作。

### 10.3 手动验收

- 首次加载模型时窗口可拖动、按钮可操作。
- 连续完成 10 轮中文聊天。
- 提问前文内容时能正确承接。
- 简单问候不会输出长篇推理过程。
- 关闭 worker 后桌宠自动回退，不崩溃。
- 现有动作、素材上传、缩放、速度和控制面板功能无回归。

## 11. 实施阶段

### 阶段一：训练环境和数据闭环

建立独立环境、下载模型、创建数据格式、实现校验脚本并完成基础模型测试。

### 阶段二：QLoRA 微调与评估

完成第一轮训练，保存 Adapter，并用固定测试集比较基础模型与微调模型。根据错例修改数据后最多进行少量可解释迭代。

### 阶段三：独立本地推理

实现 `llm_worker.py` 和命令行聊天工具，验证 10 轮上下文、非思考模式、超时和显存占用。

### 阶段四：桌宠接入

实现 `ChatService`，接入现有 `/api/chat` 和宠物气泡，添加后台预热、忙碌状态与 `LocalDialogue` 回退。

### 阶段五：回归与文档

运行完整测试，执行手动验收，记录训练命令、模型目录、启动方式和常见错误。

## 12. 后续扩展

第一版稳定后可在不修改 UI 的情况下新增：

- `CloudChatBackend`，接入在线千问、DeepSeek 或其他 API。
- 本地与在线模型切换设置。
- 逐 token 流式输出。
- 对话摘要和跨启动长期记忆。
- 根据回复驱动桌宠表情和动作。
- 合并 Adapter、转换 GGUF 并使用 llama.cpp 或 Ollama 部署。

## 13. 参考资料

- Qwen3-1.7B: https://huggingface.co/Qwen/Qwen3-1.7B
- TRL SFTTrainer: https://huggingface.co/docs/trl/main/en/sft_trainer
- PEFT LoRA: https://huggingface.co/docs/peft/main/en/developer_guides/lora
- Transformers bitsandbytes: https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes
