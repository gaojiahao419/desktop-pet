import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    model_id: str = "Qwen/Qwen3-1.7B"
    output_dir: str = "llm_lab/adapters/qwen3-1.7b-desktop-pet-v1"
    train_file: str = "llm_lab/data/processed/train.jsonl"
    validation_file: str = "llm_lab/data/processed/validation.jsonl"
    test_file: str = "llm_lab/data/processed/test.jsonl"
    seed: int = 42
    train_ratio: float = 0.8
    validation_ratio: float = 0.1
    test_ratio: float = 0.1
    load_in_4bit: bool = True
    quant_type: str = "nf4"
    double_quant: bool = True
    compute_dtype: str = "bfloat16"
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: str = "all-linear"
    max_seq_length: int = 1024
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 16
    learning_rate: float = 0.0001
    num_train_epochs: int = 2
    max_new_tokens: int = 128
    enable_thinking: bool = False
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20

    def __post_init__(self) -> None:
        split_ratios = (self.train_ratio, self.validation_ratio, self.test_ratio)
        if any(ratio <= 0 for ratio in split_ratios) or not math.isclose(
            sum(split_ratios), 1.0, rel_tol=1e-9, abs_tol=1e-9
        ):
            raise ValueError("split ratios must each be positive and sum to 1")

        positive_fields = (
            "max_seq_length",
            "per_device_train_batch_size",
            "gradient_accumulation_steps",
            "num_train_epochs",
            "max_new_tokens",
            "lora_r",
            "lora_alpha",
            "top_k",
        )
        for field_name in positive_fields:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")

        if not 0 < self.learning_rate < 1:
            raise ValueError("learning_rate must be greater than 0 and less than 1")
        if not 0 <= self.lora_dropout < 1:
            raise ValueError("lora_dropout must be between 0 inclusive and 1 exclusive")
        if not 0 < self.temperature <= 2:
            raise ValueError("temperature must be greater than 0 and at most 2")
        if not 0 < self.top_p <= 1:
            raise ValueError("top_p must be greater than 0 and at most 1")
        if self.quant_type not in {"nf4", "fp4"}:
            raise ValueError("quant_type must be 'nf4' or 'fp4'")
        if self.compute_dtype not in {"bfloat16", "float16", "float32"}:
            raise ValueError(
                "compute_dtype must be 'bfloat16', 'float16', or 'float32'"
            )


def load_training_config(path: Path) -> TrainingConfig:
    config_path = Path(path)
    try:
        with config_path.open(encoding="utf-8") as config_file:
            raw_config = json.load(config_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Training config file not found: {config_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"Invalid JSON in training config {config_path}: {exc.msg}",
            exc.doc,
            exc.pos,
        ) from exc

    if not isinstance(raw_config, dict):
        raise ValueError("Training config root must be a JSON object")

    return TrainingConfig(**raw_config)
