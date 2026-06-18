# Local LLM Training and Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible QLoRA pipeline that produces and evaluates a Chinese daily-chat adapter for `Qwen/Qwen3-1.7B` on the local RTX 4060 Laptop GPU.

**Architecture:** Keep all training-only code under `llm_lab/`. Store conversations as JSONL `messages` records, validate and split them deterministically, train a 4-bit LoRA adapter, then compare the base model and adapter on a fixed evaluation set. The desktop application must not import training dependencies.

**Tech Stack:** Python 3.11, PyTorch, Transformers, Datasets, TRL, PEFT, bitsandbytes, Accelerate, pytest, PowerShell 7

---

## Task 1: Isolate the LLM Environment and Generated Artifacts

**Files:**
- Modify: `.gitignore`
- Create: `requirements-llm.txt`
- Create: `llm_lab/__init__.py`
- Create: `llm_lab/README.md`

- [ ] **Step 1: Add a failing repository-layout test**

Create `tests/test_llm_layout.py`:

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

- [ ] **Step 2: Run the layout test and confirm it fails**

Run:

```powershell
python -m pytest tests/test_llm_layout.py -q
```

Expected: failure because `requirements-llm.txt` does not exist.

- [ ] **Step 3: Add the isolated dependency file**

Create `requirements-llm.txt` with bounded major versions:

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

Add these generated paths to `.gitignore`:

```text
.venv-llm/
llm_lab/checkpoints/
llm_lab/adapters/
llm_lab/reports/*.json
llm_lab/reports/*.jsonl
llm_lab/data/raw/*
!llm_lab/data/raw/.gitkeep
```

Create an empty `llm_lab/__init__.py`. In `llm_lab/README.md`, document these exact setup commands:

```powershell
& "D:\Anaconda3\Scripts\conda.exe" create --prefix ".\.venv-llm" python=3.11 -y
& ".\.venv-llm\python.exe" -m pip install --upgrade pip
& ".\.venv-llm\python.exe" -m pip install -r requirements-llm.txt
& ".\.venv-llm\python.exe" -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

The final command must print `True` and the NVIDIA GPU name before training proceeds.

- [ ] **Step 4: Run the layout test and the existing suite**

Run:

```powershell
python -m pytest tests/test_llm_layout.py -q
python -m pytest -q
```

Expected: the new test passes and the existing desktop-pet tests remain green.

- [ ] **Step 5: Commit the environment boundary**

```powershell
git add .gitignore requirements-llm.txt llm_lab/__init__.py llm_lab/README.md tests/test_llm_layout.py
git commit -m "build: isolate local llm dependencies"
```

## Task 2: Define and Validate Training Configuration

**Files:**
- Create: `llm_lab/config.py`
- Create: `llm_lab/configs/qwen3_1_7b_qlora.json`
- Create: `tests/test_llm_config.py`

- [ ] **Step 1: Write failing configuration tests**

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

- [ ] **Step 2: Run the tests and confirm import failure**

```powershell
python -m pytest tests/test_llm_config.py -q
```

Expected: failure because `llm_lab.config` does not exist.

- [ ] **Step 3: Implement the immutable configuration model**

Use a frozen dataclass in `llm_lab/config.py`. It must expose every training and generation decision as a typed field, reject non-unit split totals, reject non-positive batch or sequence values, and load UTF-8 JSON by path.

The checked-in JSON must resolve to these values:

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

- [ ] **Step 4: Run focused tests**

```powershell
python -m pytest tests/test_llm_config.py -q
```

Expected: all configuration tests pass.

- [ ] **Step 5: Commit configuration**

```powershell
git add llm_lab/config.py llm_lab/configs/qwen3_1_7b_qlora.json tests/test_llm_config.py
git commit -m "feat: define qwen qlora configuration"
```

## Task 3: Build the Conversation Dataset Pipeline

**Files:**
- Create: `llm_lab/data/taxonomy.json`
- Create: `llm_lab/data/seed/seed_conversations.jsonl`
- Create: `llm_lab/data_io.py`
- Create: `llm_lab/prepare_dataset.py`
- Create: `tests/fixtures/llm_conversations.jsonl`
- Create: `tests/test_llm_data.py`

- [ ] **Step 1: Write failing record-validation and split tests**

Tests must cover:

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

Also reject empty content, unknown roles, duplicate IDs, assistant-first conversations, and records without an assistant response.

- [ ] **Step 2: Run the tests and confirm failure**

```powershell
python -m pytest tests/test_llm_data.py -q
```

- [ ] **Step 3: Implement JSONL validation, normalization, and deterministic splitting**

`llm_lab/data_io.py` must provide:

```python
def load_jsonl(path: Path) -> list[dict]:
def write_jsonl(path: Path, records: Sequence[dict]) -> None:
def validate_record(record: Mapping[str, object]) -> None:
def validate_dataset(records: Sequence[Mapping[str, object]]) -> None:
def split_records(records: Sequence[dict], seed: int = 42) -> DatasetSplit:
```

`split_records` must split within each category before combining and shuffling each output split. `prepare_dataset.py` must accept `--input`, `--output-dir`, and `--config`, validate before writing, and print counts plus category distribution to stderr.

- [ ] **Step 4: Check in taxonomy and the first 120 human-reviewed seed records**

Use this exact target distribution for the final 600 accepted records:

| Category | Count |
|---|---:|
| `daily_chat` | 300 |
| `emotion_support` | 100 |
| `light_humor` | 100 |
| `pet_persona` | 50 |
| `safety_boundary` | 50 |

The 120 seed records must follow the same 50/16.7/16.7/8.3/8.3 percent proportions after integer rounding. Every record needs a stable ID, one category, and two to six alternating messages. Replies should be concise spoken Chinese and must not claim internet access, persistent memory, medical authority, or real-world action execution.

- [ ] **Step 5: Run data tests and prepare the seed split**

```powershell
python -m pytest tests/test_llm_data.py -q
& ".\.venv-llm\python.exe" -m llm_lab.prepare_dataset --input llm_lab/data/seed/seed_conversations.jsonl --output-dir llm_lab/data/processed --config llm_lab/configs/qwen3_1_7b_qlora.json
```

Expected: 96 train, 12 validation, and 12 test seed records with no duplicate IDs.

- [ ] **Step 6: Commit the data pipeline**

```powershell
git add llm_lab/data llm_lab/data_io.py llm_lab/prepare_dataset.py tests/fixtures/llm_conversations.jsonl tests/test_llm_data.py
git commit -m "feat: add validated chat dataset pipeline"
```

## Task 4: Expand to 600 Reviewed Conversations

**Files:**
- Create: `llm_lab/generate_candidates.py`
- Create: `llm_lab/review_candidates.py`
- Create: `llm_lab/data/raw/.gitkeep`
- Modify: `llm_lab/README.md`
- Create: `tests/test_llm_candidate_tools.py`

- [ ] **Step 1: Write failing tests for candidate generation and review**

Use an injected text generator so tests do not load a model. Verify that generation writes records with `review_status: "pending"`, review accepts only `accept` or `reject`, accepted IDs stay unique, and finalization fails unless the taxonomy totals are exactly 600.

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests/test_llm_candidate_tools.py -q
```

- [ ] **Step 3: Implement candidate generation**

`generate_candidates.py` must load the base model in 4-bit mode, sample prompts from the taxonomy, use `tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)`, and write only to `llm_lab/data/raw/candidates.jsonl`. Generate 650 candidates so rejection does not block the 600-record goal.

Run:

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.generate_candidates --config llm_lab/configs/qwen3_1_7b_qlora.json --count 650 --output llm_lab/data/raw/candidates.jsonl
```

- [ ] **Step 4: Implement terminal-based review**

`review_candidates.py` must display one complete conversation at a time and accept these commands: `a` accept, `r` reject, `e` replace assistant text, `q` save and quit. It must preserve decisions after restart and export only reviewed accepted records.

Review criteria are concrete: natural Chinese, persona consistency, no fabricated capabilities, no unsafe instruction, no near duplicate, and no answer longer than 180 Chinese characters unless context requires it.

Run until 600 accepted records match the target distribution:

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.review_candidates --input llm_lab/data/raw/candidates.jsonl --decisions llm_lab/data/raw/review_decisions.jsonl --output llm_lab/data/accepted_conversations.jsonl --taxonomy llm_lab/data/taxonomy.json
```

- [ ] **Step 5: Validate and split the accepted dataset**

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.prepare_dataset --input llm_lab/data/accepted_conversations.jsonl --output-dir llm_lab/data/processed --config llm_lab/configs/qwen3_1_7b_qlora.json
```

Expected: exactly 480 train, 60 validation, and 60 test records, with category totals matching the taxonomy.

- [ ] **Step 6: Commit tools and reviewed text data**

Do not commit raw model outputs or review-state files. Commit the reviewed dataset because it is the reproducible training input.

```powershell
git add llm_lab/generate_candidates.py llm_lab/review_candidates.py llm_lab/data/raw/.gitkeep llm_lab/data/accepted_conversations.jsonl llm_lab/data/processed llm_lab/README.md tests/test_llm_candidate_tools.py
git commit -m "data: add reviewed chinese chat corpus"
```

## Task 5: Implement QLoRA Training

**Files:**
- Create: `llm_lab/model_factory.py`
- Create: `llm_lab/train_qlora.py`
- Create: `tests/test_llm_training.py`

- [ ] **Step 1: Write failing tests around model and trainer construction**

Patch Transformers and TRL constructors. Assert that the factory creates `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)`, LoRA uses `r=16`, `lora_alpha=32`, `target_modules="all-linear"`, and the trainer receives the checked-in train and validation paths.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
python -m pytest tests/test_llm_training.py -q
```

- [ ] **Step 3: Implement lazy model construction**

Keep heavy imports inside factory functions so desktop tests run without the LLM environment. `model_factory.py` must expose base-model loading, optional adapter loading, tokenizer setup, and generation settings. Set tokenizer padding to the EOS token and use the Qwen chat template with thinking disabled.

- [ ] **Step 4: Implement the SFT entry point**

`train_qlora.py` must:

1. Load and validate configuration.
2. Set all random seeds.
3. Load processed JSONL through Datasets.
4. Format `messages` using the tokenizer chat template.
5. construct `SFTConfig` and `SFTTrainer` with gradient checkpointing and `bf16=True` when supported.
6. Train, save only the adapter and tokenizer, and write `training_summary.json` containing config, package versions, GPU, counts, elapsed time, and final metrics.

- [ ] **Step 5: Run unit tests**

```powershell
python -m pytest tests/test_llm_training.py -q
```

- [ ] **Step 6: Run an eight-record GPU smoke train**

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.train_qlora --config llm_lab/configs/qwen3_1_7b_qlora.json --max-train-samples 8 --max-steps 2 --output-dir llm_lab/checkpoints/smoke
```

Expected: CUDA is used, two optimizer steps complete without out-of-memory, and adapter files are written under `llm_lab/checkpoints/smoke`.

- [ ] **Step 7: Run the full training job**

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.train_qlora --config llm_lab/configs/qwen3_1_7b_qlora.json
```

Expected: adapter saved to `llm_lab/adapters/qwen3-1.7b-desktop-pet-v1` and a complete training summary written beside it.

- [ ] **Step 8: Commit training code, not generated weights**

```powershell
git add llm_lab/model_factory.py llm_lab/train_qlora.py tests/test_llm_training.py
git commit -m "feat: add qwen3 qlora trainer"
```

## Task 6: Add Baseline Chat and Fixed Evaluation

**Files:**
- Create: `llm_lab/chat_cli.py`
- Create: `llm_lab/evaluate_model.py`
- Create: `llm_lab/data/evaluation_prompts.jsonl`
- Create: `tests/test_llm_evaluation.py`
- Modify: `llm_lab/README.md`

- [ ] **Step 1: Write failing evaluation tests**

Tests must verify that prompt IDs are unique, exactly 100 prompts are loaded, base and adapter outputs use identical generation settings, result ordering is blinded, and aggregate reports include response success rate, average length, latency, repetition flags, and human preference counts.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
python -m pytest tests/test_llm_evaluation.py -q
```

- [ ] **Step 3: Implement the local chat CLI**

Support `--base-only` and `--adapter PATH`. Keep up to 10 user-assistant rounds, cap model context at approximately 2048 tokens by dropping the oldest complete round, and expose `/clear` and `/quit` commands.

Run both modes:

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.chat_cli --base-only
& ".\.venv-llm\python.exe" -m llm_lab.chat_cli --adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
```

- [ ] **Step 4: Implement reproducible evaluation**

The 100 prompts must cover the five taxonomy categories with the same proportions as training data and must not duplicate training prompts. `evaluate_model.py` generates both outputs, records latency and token counts, randomizes A/B labels using seed 42, then opens a terminal scorer with `a`, `b`, `tie`, and `bad` decisions.

Run:

```powershell
& ".\.venv-llm\python.exe" -m llm_lab.evaluate_model --config llm_lab/configs/qwen3_1_7b_qlora.json --adapter llm_lab/adapters/qwen3-1.7b-desktop-pet-v1 --prompts llm_lab/data/evaluation_prompts.jsonl --report llm_lab/reports/qwen3-1.7b-v1.json
```

- [ ] **Step 5: Enforce the v1 acceptance gate**

The adapter is accepted for desktop integration only when all conditions hold:

- At least 95 of 100 prompts produce a non-empty response without exception.
- No response includes chat-template control tokens or Python exception text.
- At least 60 percent of non-tied human comparisons prefer the adapter.
- Safety-boundary prompts have zero newly introduced severe violations versus the base model.
- Median generation latency for 128 new tokens is recorded and judged usable on the target machine.

If the gate fails, record failure categories, revise only affected examples or training parameters, create a `v2` config, and rerun training. Never overwrite the v1 config or report.

- [ ] **Step 6: Run all training-pipeline tests**

```powershell
python -m pytest tests/test_llm_layout.py tests/test_llm_config.py tests/test_llm_data.py tests/test_llm_candidate_tools.py tests/test_llm_training.py tests/test_llm_evaluation.py -q
```

- [ ] **Step 7: Commit evaluation code and fixed prompts**

```powershell
git add llm_lab/chat_cli.py llm_lab/evaluate_model.py llm_lab/data/evaluation_prompts.jsonl llm_lab/README.md tests/test_llm_evaluation.py
git commit -m "feat: add local llm evaluation gate"
```

## Task 7: Final Training Deliverable Check

- [ ] Run the entire desktop and LLM unit-test suite with the normal Python environment:

```powershell
python -m pytest -q
```

- [ ] Confirm generated model artifacts are ignored and source data is tracked:

```powershell
git status --short
git check-ignore llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
git ls-files llm_lab/data/accepted_conversations.jsonl llm_lab/data/processed/train.jsonl
```

- [ ] Record the accepted adapter path and evaluation report path for the runtime plan:

```text
Adapter: llm_lab/adapters/qwen3-1.7b-desktop-pet-v1
Report: llm_lab/reports/qwen3-1.7b-v1.json
```

- [ ] Inspect the final commit series:

```powershell
git log --oneline -7
```

Expected: environment, config, data pipeline, reviewed corpus, trainer, and evaluation changes are separate reviewable commits.
