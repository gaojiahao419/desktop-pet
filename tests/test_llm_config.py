import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from llm_lab.config import TrainingConfig, load_training_config


CONFIG_PATH = Path("llm_lab/configs/qwen3_1_7b_qlora.json")

EXPECTED_CONFIG = {
    "model_id": "Qwen/Qwen3-1.7B",
    "output_dir": "llm_lab/adapters/qwen3-1.7b-desktop-pet-v1",
    "train_file": "llm_lab/data/processed/train.jsonl",
    "validation_file": "llm_lab/data/processed/validation.jsonl",
    "test_file": "llm_lab/data/processed/test.jsonl",
    "seed": 42,
    "train_ratio": 0.8,
    "validation_ratio": 0.1,
    "test_ratio": 0.1,
    "load_in_4bit": True,
    "quant_type": "nf4",
    "double_quant": True,
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
    "enable_thinking": False,
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
}


def test_checked_in_config_matches_v1_design():
    config = load_training_config(CONFIG_PATH)

    assert config.model_id == "Qwen/Qwen3-1.7B"
    assert config.load_in_4bit is True
    assert config.quant_type == "nf4"
    assert config.lora_r == 16
    assert config.max_seq_length == 1024
    assert config.max_new_tokens == 128
    assert config.enable_thinking is False


def test_checked_in_config_has_exact_v1_content_and_json_types():
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        raw_config = json.load(config_file)

    assert raw_config == EXPECTED_CONFIG
    assert all(
        type(raw_config[key]) is type(value)
        for key, value in EXPECTED_CONFIG.items()
    )


def test_training_config_is_frozen():
    config = TrainingConfig()

    with pytest.raises(FrozenInstanceError):
        config.model_id = "another-model"


def test_invalid_split_is_rejected():
    with pytest.raises(ValueError, match="split ratios"):
        TrainingConfig(train_ratio=0.8, validation_ratio=0.2, test_ratio=0.2)


@pytest.mark.parametrize(
    "ratio_name", ["train_ratio", "validation_ratio", "test_ratio"]
)
def test_non_positive_split_ratio_is_rejected(ratio_name):
    ratios = {"train_ratio": 0.8, "validation_ratio": 0.1, "test_ratio": 0.1}
    ratios[ratio_name] = 0

    with pytest.raises(ValueError, match="split ratios"):
        TrainingConfig(**ratios)


def test_split_ratio_sum_uses_tolerant_float_comparison():
    config = TrainingConfig(
        train_ratio=0.1,
        validation_ratio=0.2,
        test_ratio=0.7000000000000001,
    )

    ratio_sum = config.train_ratio + config.validation_ratio + config.test_ratio
    assert ratio_sum == pytest.approx(1)


@pytest.mark.parametrize(
    "field_name",
    [
        "max_seq_length",
        "per_device_train_batch_size",
        "gradient_accumulation_steps",
        "num_train_epochs",
        "max_new_tokens",
        "lora_r",
        "lora_alpha",
        "top_k",
    ],
)
@pytest.mark.parametrize("invalid_value", [0, -1])
def test_non_positive_training_values_are_rejected(field_name, invalid_value):
    with pytest.raises(ValueError, match=field_name):
        TrainingConfig(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("learning_rate", 0),
        ("learning_rate", 1.0),
        ("lora_dropout", -0.1),
        ("lora_dropout", 1.0),
        ("temperature", 0),
        ("temperature", 2.1),
        ("top_p", 0),
        ("top_p", 1.1),
    ],
)
def test_bounded_training_values_are_rejected(field_name, invalid_value):
    with pytest.raises(ValueError, match=field_name):
        TrainingConfig(**{field_name: invalid_value})


@pytest.mark.parametrize("quant_type", ["int4", "NF4", ""])
def test_invalid_quant_type_is_rejected(quant_type):
    with pytest.raises(ValueError, match="quant_type"):
        TrainingConfig(quant_type=quant_type)


@pytest.mark.parametrize("compute_dtype", ["bfloat32", "int8", ""])
def test_invalid_compute_dtype_is_rejected(compute_dtype):
    with pytest.raises(ValueError, match="compute_dtype"):
        TrainingConfig(compute_dtype=compute_dtype)


def test_missing_json_file_has_clear_error(tmp_path):
    missing_path = tmp_path / "missing.json"

    error_pattern = r"Training config file not found: .*missing\.json"
    with pytest.raises(FileNotFoundError, match=error_pattern):
        load_training_config(missing_path)


def test_invalid_json_has_clear_error(tmp_path):
    config_path = tmp_path / "invalid.json"
    config_path.write_text("{not-json", encoding="utf-8")

    error_pattern = r"Invalid JSON in training config .*invalid\.json"
    with pytest.raises(ValueError, match=error_pattern):
        load_training_config(config_path)


def test_json_root_must_be_an_object(tmp_path):
    config_path = tmp_path / "list.json"
    config_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a JSON object"):
        load_training_config(config_path)


def test_unknown_json_field_is_not_ignored(tmp_path):
    config_path = tmp_path / "unknown.json"
    config_path.write_text(json.dumps({"unknown_field": True}), encoding="utf-8")

    with pytest.raises(TypeError, match="unknown_field"):
        load_training_config(config_path)
