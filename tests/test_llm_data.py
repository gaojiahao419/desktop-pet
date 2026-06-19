import copy
import json
import math
import subprocess
import sys
from collections import Counter
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from llm_lab.data_io import (
    DatasetSplit,
    load_jsonl,
    split_records,
    validate_dataset,
    validate_record,
    write_jsonl,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "llm_conversations.jsonl"
TAXONOMY_PATH = ROOT / "llm_lab" / "data" / "taxonomy.json"
SEED_PATH = ROOT / "llm_lab" / "data" / "seed" / "seed_conversations.jsonl"
PROCESSED_DIR = ROOT / "llm_lab" / "data" / "processed"
CONFIG_PATH = ROOT / "llm_lab" / "configs" / "qwen3_1_7b_qlora.json"

EXPECTED_TARGETS = {
    "daily_chat": 300,
    "emotion_support": 100,
    "light_humor": 100,
    "pet_persona": 50,
    "safety_boundary": 50,
}
EXPECTED_SEED_COUNTS = {
    "daily_chat": 60,
    "emotion_support": 20,
    "light_humor": 20,
    "pet_persona": 10,
    "safety_boundary": 10,
}


def _record(
    record_id="daily-0001",
    category="daily_chat",
    messages=None,
):
    if messages is None:
        messages = [
            {"role": "user", "content": "今天午饭吃什么？"},
            {"role": "assistant", "content": "想省事的话，可以来一碗番茄鸡蛋面。"},
        ]
    return {"id": record_id, "category": category, "messages": messages}


def _category_records(category, count):
    return [
        _record(record_id=f"{category}-{index:04d}", category=category)
        for index in range(count)
    ]


def _ids(records):
    return {record["id"] for record in records}


def _distribution(records):
    return Counter(record["category"] for record in records)


def test_dataset_split_is_frozen():
    split = DatasetSplit(train=[], validation=[], test=[])

    with pytest.raises(FrozenInstanceError):
        split.train = ["changed"]


def test_validate_record_accepts_valid_alternating_conversation():
    record = _record(
        messages=[
            {"role": "user", "content": "今天下雨了。"},
            {"role": "assistant", "content": "出门记得带伞，鞋子也尽量选防滑的。"},
            {"role": "user", "content": "晚上会冷吗？"},
            {"role": "assistant", "content": "可以先带件薄外套，按体感增减。"},
        ]
    )

    assert validate_record(record, EXPECTED_TARGETS) is None


@pytest.mark.parametrize(
    ("record", "error_pattern"),
    [
        (_record(record_id="   "), "id"),
        (_record(category="unknown"), "daily-0001.*category|category.*daily-0001"),
        ({"id": "daily-0001", "category": "daily_chat", "messages": {}}, "messages"),
        (_record(messages=[{"role": "user", "content": " "}]), "content"),
        (
            _record(messages=[{"role": "system", "content": "你好"}]),
            "role",
        ),
        (
            _record(
                messages=[
                    {"role": "assistant", "content": "你好"},
                    {"role": "user", "content": "你好"},
                ]
            ),
            "start.*user|user.*start",
        ),
        (
            _record(
                messages=[
                    {"role": "user", "content": "先说一件事"},
                    {"role": "user", "content": "再说一件事"},
                    {"role": "assistant", "content": "我在听"},
                ]
            ),
            "alternate|交替",
        ),
        (
            _record(messages=[{"role": "user", "content": "有人吗？"}]),
            "assistant",
        ),
        (
            _record(
                messages=[
                    {"role": "user", "content": "第一句"},
                    {"role": "assistant", "content": "第二句"},
                    {"role": "user", "content": "第三句"},
                ]
            ),
            "end.*assistant|assistant.*end",
        ),
    ],
)
def test_validate_record_rejects_invalid_records(record, error_pattern):
    with pytest.raises(ValueError, match=error_pattern):
        validate_record(record, EXPECTED_TARGETS)


@pytest.mark.parametrize("record", [None, [], "record"])
def test_validate_record_rejects_non_mapping_values(record):
    with pytest.raises(ValueError, match="record.*object|object.*record"):
        validate_record(record, EXPECTED_TARGETS)


def test_validate_dataset_rejects_duplicate_ids_with_identifier():
    records = [_record(), copy.deepcopy(_record())]

    with pytest.raises(ValueError, match="duplicate.*daily-0001|daily-0001.*duplicate"):
        validate_dataset(records, EXPECTED_TARGETS)


def test_load_jsonl_rejects_non_object_line_with_line_number(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"id":"ok"}\n[]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 2.*object|object.*line 2"):
        load_jsonl(path)


def test_load_jsonl_reports_invalid_json_line_number(tmp_path):
    path = tmp_path / "bad-json.jsonl"
    path.write_text('{"id":"ok"}\n{bad-json}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 2"):
        load_jsonl(path)


def test_utf8_jsonl_round_trip_creates_parent_directory(tmp_path):
    records = [_record(messages=[
        {"role": "user", "content": "晚饭吃饺子吗？"},
        {"role": "assistant", "content": "可以，配一碟醋和清爽小菜正合适。"},
    ])]
    path = tmp_path / "nested" / "中文对话.jsonl"

    write_jsonl(path, records)

    assert path.read_text(encoding="utf-8").count("\n") == 1
    assert "晚饭吃饺子吗" in path.read_text(encoding="utf-8")
    assert load_jsonl(path) == records


def test_fixture_contains_all_five_valid_categories():
    records = load_jsonl(FIXTURE_PATH)

    validate_dataset(records, EXPECTED_TARGETS)
    assert _distribution(records) == Counter({category: 1 for category in EXPECTED_TARGETS})


def test_split_records_is_deterministic_disjoint_and_does_not_mutate_input():
    records = sum(
        (_category_records(category, 20) for category in EXPECTED_TARGETS),
        [],
    )
    original = copy.deepcopy(records)

    first = split_records(records, seed=123)
    second = split_records(records, seed=123)

    assert first == second
    assert records == original
    assert not (_ids(first.train) & _ids(first.validation))
    assert not (_ids(first.train) & _ids(first.test))
    assert not (_ids(first.validation) & _ids(first.test))
    assert _ids(first.train) | _ids(first.validation) | _ids(first.test) == _ids(records)


def test_split_records_stratifies_twenty_records_as_16_2_2():
    records = _category_records("daily_chat", 20)

    split = split_records(records, seed=42)

    assert [len(split.train), len(split.validation), len(split.test)] == [16, 2, 2]
    assert all(record["category"] == "daily_chat" for record in split.train)


@pytest.mark.parametrize(
    ("ratios", "error_pattern"),
    [
        ((0.8, 0.1, 0.2), "ratios.*sum|sum.*ratios"),
        ((0.8, 0.2, 0.0), "ratios.*positive|positive.*ratios"),
        ((math.nan, 0.1, 0.9), "ratios.*finite|finite.*ratios"),
    ],
)
def test_split_records_rejects_invalid_ratios(ratios, error_pattern):
    with pytest.raises(ValueError, match=error_pattern):
        split_records(
            _category_records("daily_chat", 20),
            train_ratio=ratios[0],
            validation_ratio=ratios[1],
            test_ratio=ratios[2],
        )


def test_split_records_rejects_category_too_small_for_validation_and_test():
    records = _category_records("daily_chat", 2)

    with pytest.raises(ValueError, match="daily_chat.*validation.*test|daily_chat.*non-empty"):
        split_records(records)


def test_taxonomy_is_machine_readable_and_has_expected_targets():
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

    assert isinstance(taxonomy, dict)
    assert taxonomy["total_target"] == 600
    assert set(taxonomy["categories"]) == set(EXPECTED_TARGETS)
    for category, target_count in EXPECTED_TARGETS.items():
        definition = taxonomy["categories"][category]
        assert definition["target_count"] == target_count
        assert isinstance(definition["description"], str)
        assert definition["description"].strip()


def test_seed_dataset_has_exact_counts_valid_format_and_unique_content():
    records = load_jsonl(SEED_PATH)

    validate_dataset(records, EXPECTED_TARGETS)
    assert len(records) == 120
    assert _distribution(records) == Counter(EXPECTED_SEED_COUNTS)
    assert len(_ids(records)) == 120
    conversations = [
        tuple((message["role"], message["content"]) for message in record["messages"])
        for record in records
    ]
    assert len(set(conversations)) == 120
    assert {len(record["messages"]) for record in records} <= {2, 4, 6}
    for record in records:
        assert record["id"].startswith(
            {
                "daily_chat": "daily-",
                "emotion_support": "emotion-",
                "light_humor": "humor-",
                "pet_persona": "pet-",
                "safety_boundary": "safety-",
            }[record["category"]]
        )
        assert all(
            message["content"] == message["content"].strip()
            for message in record["messages"]
        )


def test_seed_dataset_avoids_prohibited_capability_claims():
    text = "\n".join(
        message["content"]
        for record in load_jsonl(SEED_PATH)
        for message in record["messages"]
        if message["role"] == "assistant"
    )
    prohibited_claims = (
        "我可以联网",
        "我能联网",
        "我刚刚上网",
        "我会永久记住",
        "我已经替你下单",
        "我已经帮你登录",
        "我已经替你打电话",
        "我是医生",
        "保证治愈",
    )

    assert not [claim for claim in prohibited_claims if claim in text]


def test_checked_in_processed_splits_have_expected_counts_and_distribution():
    train = load_jsonl(PROCESSED_DIR / "train.jsonl")
    validation = load_jsonl(PROCESSED_DIR / "validation.jsonl")
    test = load_jsonl(PROCESSED_DIR / "test.jsonl")

    assert [len(train), len(validation), len(test)] == [96, 12, 12]
    assert _distribution(train) == Counter(
        {
            "daily_chat": 48,
            "emotion_support": 16,
            "light_humor": 16,
            "pet_persona": 8,
            "safety_boundary": 8,
        }
    )
    assert _distribution(validation) == _distribution(test) == Counter(
        {
            "daily_chat": 6,
            "emotion_support": 2,
            "light_humor": 2,
            "pet_persona": 1,
            "safety_boundary": 1,
        }
    )
    validate_dataset(train + validation + test, EXPECTED_TARGETS)


def test_prepare_dataset_cli_writes_splits_and_reports_to_stderr(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "llm_lab.prepare_dataset",
            "--input",
            str(SEED_PATH),
            "--output-dir",
            str(tmp_path),
            "--config",
            str(CONFIG_PATH),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "total=120" in result.stderr
    assert "train=96" in result.stderr
    assert "validation=12" in result.stderr
    assert "test=12" in result.stderr
    for split_name in ("train", "validation", "test"):
        assert f"{split_name} categories:" in result.stderr
        assert (tmp_path / f"{split_name}.jsonl").is_file()


def test_prepare_dataset_cli_returns_nonzero_for_invalid_data(tmp_path):
    invalid_input = tmp_path / "invalid.jsonl"
    invalid_input.write_text(
        json.dumps(_record(messages=[{"role": "user", "content": "只有提问"}]), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "llm_lab.prepare_dataset",
            "--input",
            str(invalid_input),
            "--output-dir",
            str(tmp_path / "output"),
            "--config",
            str(CONFIG_PATH),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "assistant" in result.stderr
    assert "Traceback" not in result.stderr
