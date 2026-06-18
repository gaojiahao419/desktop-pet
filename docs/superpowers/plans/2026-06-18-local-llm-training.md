# 本地大模型训练与评估实施计划

> **供智能代理执行：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 子技能，按任务逐项实施。本计划使用复选框（`- [ ]`）跟踪进度。

**目标：** 在本机 RTX 4060 Laptop GPU 上建立可复现的 QLoRA 流程，为 `Qwen/Qwen3-1.7B` 训练并评估一个中文日常聊天适配器。

**架构：** 所有仅用于训练的代码都放在 `llm_lab/` 下。对话数据采用 JSONL `messages` 记录格式，先确定性校验和切分，再训练 4 位 LoRA 适配器，最后使用固定评估集比较基础模型和适配器。桌宠程序不得导入训练依赖。

**技术栈：** Python 3.11、PyTorch、Transformers、Datasets、TRL、PEFT、bitsandbytes、Accelerate、pytest、PowerShell 7

---

## 任务 1：隔离大模型环境和生成产物

**文件：**
- 修改：`.gitignore`
- 新建：`requirements-llm.txt`
- 新建：`llm_lab/__init__.py`
- 新建：`llm_lab/README.md`

- [ ] **步骤 1：添加一个会失败的仓库布局测试**

新建 `tests/test_llm_layout.py`：

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_llm_requirements_are_separate_from_desktop_requirements():
    desktop = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    llm = (ROOT / "requirements-llm.txt").read_text(encoding="utf-8").lower()

    assert "transformers" not in desktop
    assert "transformers" in llm
    assert "peft" in llm
    assert "trl" in llm
    assert "bitsandbytes" in llm
```

- [ ] **步骤 2：运行布局测试并确认失败**

运行：

```powershell
python -m pytest tests/test_llm_layout.py -q
```

预期：由于 `requirements-llm.txt` 尚不存在，测试失败。

- [ ] **步骤 3：添加独立依赖文件**

新建 `requirements-llm.txt`，限定主版本范围：

```text
torch>=2.7,<3
transformers>=4.51,<5
datasets>=3,<5
trl>=0.18,<1
peft>=0.15,<1
accelerate>=1.6,<2
bitsandbytes>=0.45,<1
safetensors>=0.5,<1
pytest>=8,<10
```

把以下生成路径加入 `.gitignore`：

```text
.venv-llm/
llm_lab/checkpoints/
llm_lab/adapters/
llm_lab/reports/*.json
llm_lab/reports/*.jsonl
llm_lab/data/raw/*
!llm_lab/data/raw/.gitkeep
```

新建空的 `llm_lab/__init__.py`。在 `llm_lab/README.md` 中记录以下准确的环境安装命令：

```powershell
& "D:\Anaconda3\Scripts\conda.exe" create --prefix ".\.venv-llm" python=3.11 -y
& ".\.venv-llm\python.exe" -m pip install --upgrade pip
& ".\.venv-llm\python.exe" -m pip install -r requirements-llm.txt
& ".\.venv-llm\python.exe" -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

开始训练前，最后一条命令必须打印 `True` 和 NVIDIA GPU 名称。

- [ ] **步骤 4：运行布局测试和现有测试套件**

运行：

```powershell
python -m pytest tests/test_llm_layout.py -q
python -m pytest -q
```

预期：新测试通过，现有桌宠测试仍全部通过。

- [ ] **步骤 5：提交环境边界改动**

```powershell
git add .gitignore requirements-llm.txt llm_lab/__init__.py llm_lab/README.md tests/test_llm_layout.py
git commit -m "build: isolate local llm dependencies"
```

## 任务 2：定义并校验训练配置

**文件：**
- 新建：`llm_lab/config.py`
- 新建：`llm_lab/configs/qwen3_1_7b_qlora.json`
- 新建：`tests/test_llm_config.py`

- [ ] **步骤 1：编写会失败的配置测试**

```python
from pathlib import Path

import pytest

from llm_lab.config import TrainingConfig, load_training_config


CONFIG_PATH = Path("llm_lab/configs/qwen3_1_7b_qlora.json")


def test_checked_in_config_matches_v1_design():
    config = load_training_config(CONFIG_PATH)

    assert config.model_id == "Qwen/Qwen3-1.7B"
    assert config.load_in_4bit is True
    assert config.quant_type == "nf4"
    assert config.lora_r == 16
    assert config.max_seq_length == 1024
    assert config.max_new_tokens == 128
    assert config.enable_thinking is False


def test_invalid_split_is_rejected():
    with pytest.raises(ValueError, match="split ratios"):
        TrainingConfig(train_ratio=0.8, validation_ratio=0.2, test_ratio=0.2)
```

- [ ] **步骤 2：运行测试并确认导入失败**

```powershell
python -m pytest tests/test_llm_config.py -q
```

预期：由于 `llm_lab.config` 尚不存在，测试失败。

- [ ] **步骤 3：实现不可变配置模型**

在 `llm_lab/config.py` 中使用冻结的 dataclass。每个训练和生成决策都必须对应一个带类型字段；切分比例之和不为 1、批大小或序列长度非正数时必须拒绝；配置必须按路径读取 UTF-8 JSON。

纳入版本控制的 JSON 必须解析为以下值：

```json
{
  "model_id": "Qwen/Qwen3-1.7B",
  "output_dir": "llm_lab/adapters/qwen3-1.7b-desktop-pet-v1",
  "train_file": "llm_lab/data/processed/train.jsonl",
  "validation_file": "llm_lab/data/processed/validation.jsonl",
  "test_file": "llm_lab/data/processed/test.jsonl",
  "seed": 42,
  "train_ratio": 0.8,
  "validation_ratio": 0.1,
  "test_ratio": 0.1,
  "load_in_4bit": true,
  "quant_type": "nf4",
  "double_quant": true,
  "compute_dtype": "bfloat16",
  "lora_r": 16,
  "lora_alpha": 32,
  "lora_dropout": 0.05,
  "target_modules": "all-linear",
  "max_seq_length": 1024,
  "per_device_train_batch_size": 1,
  "gradient_accumulation_steps": 16,
  "learning_rate": 0.0001,
  "num_train_epochs": 2,
  "max_new_tokens": 128,
  "enable_thinking": false,
  "temperature": 0.7,
  "top_p": 0.8,
  "top_k": 20
}
```

- [ ] **步骤 4：运行针对性测试**

```powershell
python -m pytest tests/test_llm_config.py -q
```

预期：所有配置测试通过。

- [ ] **步骤 5：提交配置**

```powershell
git add llm_lab/config.py llm_lab/configs/qwen3_1_7b_qlora.json tests/test_llm_config.py
git commit -m "feat: define qwen qlora configuration"
```

## 任务 3：建立对话数据集流水线

**文件：**
- 新建：`llm_lab/data/taxonomy.json`
- 新建：`llm_lab/data/seed/seed_conversations.jsonl`
- 新建：`llm_lab/data_io.py`
- 新建：`llm_lab/prepare_dataset.py`
- 新建：`tests/fixtures/llm_conversations.jsonl`
- 新建：`tests/test_llm_data.py`

- [ ] **步骤 1：编写会失败的记录校验和切分测试**

测试必须覆盖：

```python
def test_valid_record_requires_alternating_user_and_assistant_messages():
    record = {
        "id": "daily-0001",
        "category": "daily_chat",
        "messages": [
            {"role": "user", "content": "今天有点累。"},
            {"role": "assistant", "content": "先歇一会儿吧，今天最累的是哪一段？"},
        ],
    }
    validate_record(record)


def test_split_is_deterministic_and_has_no_id_overlap(tmp_path):
    records = make_records(20)
    first = split_records(records, seed=42)
    second = split_records(records, seed=42)

    assert first == second
    assert ids(first.train).isdisjoint(ids(first.validation))
    assert ids(first.train).isdisjoint(ids(first.test))
```

还要拒绝空内容、未知角色、重复 ID、以 assistant 开始的对话，以及没有 assistant 回复的记录。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_llm_data.py -q
```

- [ ] **步骤 3：实现 JSONL 校验、规范化和确定性切分**

`llm_lab/data_io.py` 必须提供：

```python
def load_jsonl(path: Path) -> list[dict]:
def write_jsonl(path: Path, records: Sequence[dict]) -> None:
def validate_record(record: Mapping[str, object]) -> None:
def validate_dataset(records: Sequence[Mapping[str, object]]) -> None:
def split_records(records: Sequence[dict], seed: int = 42) -> DatasetSplit:
```

`split_records` 必须先在每个类别内部切分，再合并并打乱各输出数据集。`prepare_dataset.py` 必须接受 `--input`、`--output-dir` 和 `--config`，写入前执行校验，并把数量与类别分布打印到 stderr。

- [ ] **步骤 4：纳入分类表和首批 120 条人工审核种子数据**

最终 600 条通过审核的记录必须采用以下分布：

| 类别 | 数量 |
|---|---:|
| `daily_chat` | 300 |
| `emotion_support` | 100 |
| `light_humor` | 100 |
| `pet_persona` | 50 |
| `safety_boundary` | 50 |

120 条种子记录按整数取整后保持相同的 50% / 16.7% / 16.7% / 8.3% / 8.3% 比例。每条记录必须包含稳定 ID、一个类别和 2 到 6 条交替消息。回复应为简洁自然的口语中文，不得声称拥有联网、持久记忆、医疗权威或现实操作能力。

- [ ] **步骤 5：运行数据测试并生成种子数据切分**

```powershell
python -m pytest tests/test_llm_data.py -q
& ".\.venv-llm\python.exe" -m llm_lab.prepare_dataset --input llm_lab/data/seed/seed_conversations.jsonl --output-dir llm_lab/data/processed --config llm_lab/configs/qwen3_1_7b_qlora.json
```

预期：生成 96 条训练记录、12 条验证记录和 12 条测试记录，并且不存在重复 ID。

- [ ] **步骤 6：提交数据流水线**

```powershell
git add llm_lab/data llm_lab/data_io.py llm_lab/prepare_dataset.py tests/fixtures/llm_conversations.jsonl tests/test_llm_data.py
git commit -m "feat: add validated chat dataset pipeline"
```

## 任务 4：扩充到 600 条审核通过的对话

**文件：**
- 新建：`llm_lab/generate_candidates.py`
- 新建：`llm_lab/review_candidates.py`
- 新建：`llm_lab/data/raw/.gitkeep`
- 修改：`llm_lab/README.md`
- 新建：`tests/test_llm_candidate_tools.py`

- [ ] **步骤 1：编写会失败的候选生成与审核测试**

注入文本生成器，使测试不加载模型。验证生成结果使用 `review_status: "pending"`；审核只接受 `accept` 或 `reject`；已接受的 ID 必须唯一；除非分类数量总计恰好为 600，否则最终导出必须失败。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_llm_candidate_tools.py -q
```

- [ ] **步骤 3：实现候选数据生成**

`generate_candidates.py` 必须以 4 位模式加载基础模型，按分类表抽样提示词，使用 `tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)`，并且只写入 `llm_lab/data/raw/candidates.jsonl`。生成 650 条候选，以免部分记录被拒绝后无法达到 600 条目标。

运行：

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.generate_candidates --config llm_lab/configs/qwen3_1_7b_qlora.json --count 650 --output llm_lab/data/raw/candidates.jsonl
```

- [ ] **步骤 4：实现终端审核工具**

`review_candidates.py` 每次显示一段完整对话，并接受以下命令：`a` 接受、`r` 拒绝、`e` 替换 assistant 文本、`q` 保存并退出。重启后必须保留审核决定，导出时只能包含审核通过的记录。

审核标准必须明确：中文自然、人格一致、不虚构能力、不包含不安全指令、没有近似重复；除非上下文确有需要，回复不得超过 180 个中文字符。

持续审核，直到 600 条记录达到目标分布：

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.review_candidates --input llm_lab/data/raw/candidates.jsonl --decisions llm_lab/data/raw/review_decisions.jsonl --output llm_lab/data/accepted_conversations.jsonl --taxonomy llm_lab/data/taxonomy.json
```

- [ ] **步骤 5：校验并切分已接受数据集**

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.prepare_dataset --input llm_lab/data/accepted_conversations.jsonl --output-dir llm_lab/data/processed --config llm_lab/configs/qwen3_1_7b_qlora.json
```

预期：恰好生成 480 条训练记录、60 条验证记录和 60 条测试记录，类别总数与分类表一致。

- [ ] **步骤 6：提交工具和审核后的文本数据**

不要提交模型原始输出或审核状态文件。审核后的数据集是可复现训练输入，必须提交。

```powershell
git add llm_lab/generate_candidates.py llm_lab/review_candidates.py llm_lab/data/raw/.gitkeep llm_lab/data/accepted_conversations.jsonl llm_lab/data/processed llm_lab/README.md tests/test_llm_candidate_tools.py
git commit -m "data: add reviewed chinese chat corpus"
```

## 任务 5：实现 QLoRA 训练

**文件：**
- 新建：`llm_lab/model_factory.py`
- 新建：`llm_lab/train_qlora.py`
- 新建：`tests/test_llm_training.py`

- [ ] **步骤 1：围绕模型与训练器构造编写失败测试**

替换 Transformers 和 TRL 构造器。断言工厂创建 `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)`；LoRA 使用 `r=16`、`lora_alpha=32`、`target_modules="all-linear"`；训练器接收到版本库中固定的训练和验证路径。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_llm_training.py -q
```

- [ ] **步骤 3：实现延迟模型构造**

把重量级导入放在工厂函数内部，使桌宠测试在没有大模型环境时也能运行。`model_factory.py` 必须提供基础模型加载、可选适配器加载、分词器设置和生成参数。把分词器 padding token 设为 EOS token，并使用关闭思考模式的 Qwen 对话模板。

- [ ] **步骤 4：实现 SFT 入口**

`train_qlora.py` 必须：

1. 加载并校验配置。
2. 设置全部随机种子。
3. 通过 Datasets 加载处理后的 JSONL。
4. 使用分词器对话模板格式化 `messages`。
5. 构造带梯度检查点的 `SFTConfig` 和 `SFTTrainer`，硬件支持时启用 `bf16=True`。
6. 执行训练，只保存适配器和分词器，并写入 `training_summary.json`，包含配置、软件包版本、GPU、数据数量、耗时和最终指标。

- [ ] **步骤 5：运行单元测试**

```powershell
python -m pytest tests/test_llm_training.py -q
```

- [ ] **步骤 6：使用 8 条记录执行 GPU 冒烟训练**

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.train_qlora --config llm_lab/configs/qwen3_1_7b_qlora.json --max-train-samples 8 --max-steps 2 --output-dir llm_lab/checkpoints/smoke
```

预期：使用 CUDA，在不出现显存不足的情况下完成两个优化步骤，并在 `llm_lab/checkpoints/smoke` 下写入适配器文件。

- [ ] **步骤 7：运行完整训练任务**

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.train_qlora --config llm_lab/configs/qwen3_1_7b_qlora.json
```

预期：适配器保存到 `llm_lab/adapters/qwen3-1.7b-desktop-pet-v1`，完整训练摘要写在同一目录。

- [ ] **步骤 8：提交训练代码，不提交生成权重**

```powershell
git add llm_lab/model_factory.py llm_lab/train_qlora.py tests/test_llm_training.py
git commit -m "feat: add qwen3 qlora trainer"
```

## 任务 6：添加基础聊天和固定评估流程

**文件：**
- 新建：`llm_lab/chat_cli.py`
- 新建：`llm_lab/evaluate_model.py`
- 新建：`llm_lab/data/evaluation_prompts.jsonl`
- 新建：`tests/test_llm_evaluation.py`
- 修改：`llm_lab/README.md`

- [ ] **步骤 1：编写会失败的评估测试**

测试必须验证：提示词 ID 唯一；恰好加载 100 条提示词；基础模型与适配器使用完全相同的生成设置；结果顺序经过盲化；汇总报告包含回复成功率、平均长度、延迟、重复标记和人工偏好计数。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m pytest tests/test_llm_evaluation.py -q
```

- [ ] **步骤 3：实现本地聊天 CLI**

支持 `--base-only` 和 `--adapter PATH`。最多保留 10 轮用户与助手对话；模型上下文上限约为 2048 token，超出时删除最早的完整轮次；提供 `/clear` 和 `/quit` 命令。

分别运行两种模式：

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.chat_cli --base-only
& ".\.venv-llm\python.exe" -m llm_lab.chat_cli --adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
```

- [ ] **步骤 4：实现可复现评估**

100 条提示词必须覆盖五个分类，并保持与训练数据相同的比例，不得与训练提示重复。`evaluate_model.py` 生成两种模型输出，记录延迟和 token 数量，使用随机种子 42 打乱 A/B 标签，然后启动终端评分器，接受 `a`、`b`、`tie` 和 `bad` 决定。

运行：

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.evaluate_model --config llm_lab/configs/qwen3_1_7b_qlora.json --adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1 --prompts llm_lab/data/evaluation_prompts.jsonl --report llm_lab/reports/qwen3-1.7b-v1.json
```

- [ ] **步骤 5：执行第一版验收门槛**

只有同时满足以下条件，适配器才允许进入桌宠接入阶段：

- 100 条提示词中至少 95 条能生成非空回复且不抛出异常。
- 回复中不出现对话模板控制 token 或 Python 异常文本。
- 在排除平局后，人工比较中至少 60% 更偏好适配器。
- 与基础模型相比，安全边界提示中新增的严重违规数量为 0。
- 记录生成 128 个新 token 的中位延迟，并确认目标机器上的体验可接受。

如果未通过门槛，记录失败类别，只修改受影响的数据示例或训练参数，创建 `v2` 配置并重新训练。不得覆盖 v1 配置或报告。

- [ ] **步骤 6：运行所有训练流水线测试**

```powershell
python -m pytest tests/test_llm_layout.py tests/test_llm_config.py tests/test_llm_data.py tests/test_llm_candidate_tools.py tests/test_llm_training.py tests/test_llm_evaluation.py -q
```

- [ ] **步骤 7：提交评估代码和固定提示词**

```powershell
git add llm_lab/chat_cli.py llm_lab/evaluate_model.py llm_lab/data/evaluation_prompts.jsonl llm_lab/README.md tests/test_llm_evaluation.py
git commit -m "feat: add local llm evaluation gate"
```

## 任务 7：最终训练交付检查

- [ ] 使用普通 Python 环境运行完整桌宠和大模型单元测试套件：

```powershell
python -m pytest -q
```

- [ ] 确认生成的模型产物已被忽略，源数据已纳入版本控制：

```powershell
git status --short
git check-ignore llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
git ls-files llm_lab/data/accepted_conversations.jsonl llm_lab/data/processed/train.jsonl
```

- [ ] 为运行时计划记录通过验收的适配器路径和评估报告路径：

```text
Adapter: llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
Report: llm_lab/reports/qwen3-1.7b-v1.json
```

- [ ] 检查最终提交序列：

```powershell
git log --oneline -7
```

预期：环境、配置、数据流水线、审核语料、训练器和评估改动分别位于可独立审查的提交中。
