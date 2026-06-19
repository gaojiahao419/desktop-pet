import copy
import json
import math
import subprocess
import sys
from collections import Counter
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import get_type_hints

import pytest

import llm_lab.data_io as data_io
import llm_lab.prepare_dataset as prepare_dataset
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
    "daily_chat": 600,
    "emotion_support": 200,
    "light_humor": 200,
    "pet_persona": 100,
    "safety_boundary": 100,
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
    "validator",
    [
        pytest.param(lambda record: validate_record(record), id="record"),
        pytest.param(lambda record: validate_dataset([record]), id="dataset"),
    ],
)
def test_default_validation_rejects_unknown_categories(validator):
    record = _record(category="unknown")

    with pytest.raises(ValueError, match="unknown category"):
        validator(record)


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


def test_write_jsonl_serializes_every_record_before_replacing_target(tmp_path):
    path = tmp_path / "records.jsonl"
    old_content = b'{"old":true}\n'
    path.write_bytes(old_content)
    invalid_record = _record(record_id="daily-0002")
    invalid_record["unserializable"] = object()

    with pytest.raises(TypeError):
        write_jsonl(path, [_record(), invalid_record])

    assert path.read_bytes() == old_content
    assert set(tmp_path.iterdir()) == {path}


def test_write_jsonl_write_failure_preserves_target_and_cleans_temp(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "records.jsonl"
    old_content = b'{"old":true}\n'
    path.write_bytes(old_content)
    original_open = Path.open

    class FailingWriter:
        def __init__(self, file_object):
            self.file_object = file_object

        def __enter__(self):
            self.file_object.__enter__()
            return self

        def __exit__(self, *args):
            return self.file_object.__exit__(*args)

        def write(self, content):
            self.file_object.write(content[:8])
            raise OSError("simulated disk write failure")

    def fail_only_temp_writes(open_path, mode="r", *args, **kwargs):
        opened = original_open(open_path, mode, *args, **kwargs)
        if open_path.parent == tmp_path and open_path != path and "w" in mode:
            return FailingWriter(opened)
        return opened

    monkeypatch.setattr(Path, "open", fail_only_temp_writes)

    with pytest.raises(OSError, match="simulated disk write failure"):
        write_jsonl(path, [_record()])

    assert path.read_bytes() == old_content
    assert set(tmp_path.iterdir()) == {path}


def test_load_jsonl_rejects_blank_lines_with_line_number(tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_text(json.dumps(_record(), ensure_ascii=False) + "\n\n", encoding="utf-8")

    with pytest.raises(ValueError, match="blank JSONL line 2"):
        load_jsonl(path)


def test_load_jsonl_accepts_utf8_bom_at_file_start(tmp_path):
    path = tmp_path / "bom.jsonl"
    payload = json.dumps(_record(), ensure_ascii=False).encode("utf-8") + b"\n"
    path.write_bytes(b"\xef\xbb\xbf" + payload)

    assert load_jsonl(path) == [_record()]


def test_load_jsonl_reports_invalid_utf8_with_path(tmp_path):
    path = tmp_path / "invalid-utf8.jsonl"
    path.write_bytes(b'{"id":"broken","content":"\xff"}\n')

    with pytest.raises(ValueError, match=r"invalid-utf8\.jsonl.*UTF-8"):
        load_jsonl(path)


def test_public_jsonl_types_describe_conversation_records():
    assert hasattr(data_io, "Message")
    assert hasattr(data_io, "ConversationRecord")
    assert set(data_io.Message.__annotations__) == {"role", "content"}
    assert set(data_io.ConversationRecord.__annotations__) == {
        "id",
        "category",
        "messages",
    }
    assert get_type_hints(data_io.load_jsonl)["return"] == list[
        data_io.ConversationRecord
    ]


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


def test_split_records_has_exact_per_category_counts_for_seed_distribution():
    records = sum(
        (
            _category_records(category, count)
            for category, count in EXPECTED_SEED_COUNTS.items()
        ),
        [],
    )

    split = split_records(records, seed=42)

    assert [len(split.train), len(split.validation), len(split.test)] == [96, 12, 12]
    assert _distribution(split.train) == Counter(
        {
            "daily_chat": 48,
            "emotion_support": 16,
            "light_humor": 16,
            "pet_persona": 8,
            "safety_boundary": 8,
        }
    )
    expected_evaluation = Counter(
        {
            "daily_chat": 6,
            "emotion_support": 2,
            "light_humor": 2,
            "pet_persona": 1,
            "safety_boundary": 1,
        }
    )
    assert _distribution(split.validation) == expected_evaluation
    assert _distribution(split.test) == expected_evaluation


def test_adding_unrelated_category_does_not_change_existing_split_membership():
    allowed_categories = {"daily_chat", "custom_category"}
    daily_records = _category_records("daily_chat", 20)
    custom_records = _category_records("custom_category", 20)

    original = split_records(
        daily_records,
        seed=42,
        allowed_categories=allowed_categories,
    )
    augmented = split_records(
        daily_records + custom_records,
        seed=42,
        allowed_categories=allowed_categories,
    )

    def daily_assignments(split):
        return {
            record["id"]: split_name
            for split_name, records in (
                ("train", split.train),
                ("validation", split.validation),
                ("test", split.test),
            )
            for record in records
            if record["category"] == "daily_chat"
        }

    assert daily_assignments(augmented) == daily_assignments(original)


@pytest.mark.parametrize(
    ("count", "expected_counts"),
    [
        (3, (1, 1, 1)),
        (9, (7, 1, 1)),
        (10, (8, 1, 1)),
        (11, (9, 1, 1)),
        (12, (10, 1, 1)),
        (19, (15, 2, 2)),
    ],
)
def test_largest_remainder_split_boundaries(count, expected_counts):
    split = split_records(_category_records("daily_chat", count), seed=42)

    actual_counts = (len(split.train), len(split.validation), len(split.test))
    assert actual_counts == expected_counts
    assert sum(actual_counts) == count
    assert all(split_count > 0 for split_count in actual_counts)


def test_largest_remainder_supports_non_default_ratios():
    split = split_records(
        _category_records("daily_chat", 11),
        seed=42,
        train_ratio=0.6,
        validation_ratio=0.2,
        test_ratio=0.2,
    )

    assert (len(split.train), len(split.validation), len(split.test)) == (7, 2, 2)


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


@pytest.mark.parametrize("count", [1, 2])
def test_split_records_rejects_categories_with_fewer_than_three_records(count):
    records = _category_records("daily_chat", count)

    with pytest.raises(ValueError, match="daily_chat.*at least 3|at least 3.*daily_chat"):
        split_records(records)


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param(lambda: validate_dataset([]), id="validate"),
        pytest.param(lambda: split_records([]), id="split"),
    ],
)
def test_empty_datasets_are_rejected(operation):
    with pytest.raises(ValueError, match="empty|at least one"):
        operation()


def test_split_records_accepts_explicit_custom_category():
    split = split_records(
        _category_records("custom_category", 10),
        allowed_categories={"custom_category"},
    )

    assert (len(split.train), len(split.validation), len(split.test)) == (8, 1, 1)


def test_taxonomy_is_machine_readable_and_has_expected_targets():
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

    assert isinstance(taxonomy, dict)
    assert taxonomy["total_target"] == 1200
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


def test_seed_dataset_conversations_and_role_contents_are_unique():
    records = load_jsonl(SEED_PATH)
    conversations = [
        tuple((message["role"], message["content"]) for message in record["messages"])
        for record in records
    ]
    user_contents = [
        message["content"]
        for record in records
        for message in record["messages"]
        if message["role"] == "user"
    ]
    assistant_contents = [
        message["content"]
        for record in records
        for message in record["messages"]
        if message["role"] == "assistant"
    ]

    assert len(records) == 120
    assert len(conversations) == len(set(conversations))
    assert len(user_contents) == len(set(user_contents))
    assert len(assistant_contents) == len(set(assistant_contents))


def test_humor_seed_0018_avoids_body_evaluation():
    record = next(
        record for record in load_jsonl(SEED_PATH) if record["id"] == "humor-0018"
    )

    assert record["messages"][-1]["content"] == (
        "日历今天很忙，因为每一页都有安排。"
    )


def test_safety_seed_records_warn_and_offer_safe_next_steps():
    records = [
        record
        for record in load_jsonl(SEED_PATH)
        if record["category"] == "safety_boundary"
    ]
    warning_keywords = (
        "不能",
        "不要",
        "危险",
        "风险",
        "紧急",
        "不安全",
    )
    safe_step_keywords = (
        "请",
        "联系",
        "求助",
        "选择",
        "改乘",
        "远离",
        "就医",
        "撤离",
        "核实",
    )

    assert len(records) == 10
    for record in records:
        assistant_text = "\n".join(
            message["content"]
            for message in record["messages"]
            if message["role"] == "assistant"
        )
        assert any(keyword in assistant_text for keyword in warning_keywords), (
            f"{record['id']}: assistant must state a refusal or risk warning"
        )
        assert any(keyword in assistant_text for keyword in safe_step_keywords), (
            f"{record['id']}: assistant must offer a safe alternative or help step"
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


def test_checked_in_processed_splits_have_expected_counts_and_distribution(tmp_path):
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

    regenerated_dir = tmp_path / "regenerated"
    prepare_dataset.run(SEED_PATH, regenerated_dir, CONFIG_PATH)
    for split_name in ("train", "validation", "test"):
        assert (regenerated_dir / f"{split_name}.jsonl").read_bytes() == (
            PROCESSED_DIR / f"{split_name}.jsonl"
        ).read_bytes()


def test_prepare_dataset_staging_failure_preserves_all_existing_splits(
    tmp_path,
    monkeypatch,
):
    output_dir = tmp_path / "processed"
    output_dir.mkdir()
    old_contents = {}
    for split_name in ("train", "validation", "test"):
        path = output_dir / f"{split_name}.jsonl"
        old_contents[split_name] = f"old-{split_name}\n".encode("utf-8")
        path.write_bytes(old_contents[split_name])

    original_write_jsonl = prepare_dataset.write_jsonl
    write_count = 0

    def fail_second_staged_write(path, records):
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("simulated staging failure")
        original_write_jsonl(path, records)

    monkeypatch.setattr(prepare_dataset, "write_jsonl", fail_second_staged_write)

    with pytest.raises(OSError, match="simulated staging failure"):
        prepare_dataset.run(SEED_PATH, output_dir, CONFIG_PATH)

    for split_name, old_content in old_contents.items():
        assert (output_dir / f"{split_name}.jsonl").read_bytes() == old_content
    assert set(tmp_path.iterdir()) == {output_dir}


def test_prepare_dataset_cli_accepts_taxonomy_defined_custom_category(
    tmp_path,
    monkeypatch,
    capsys,
):
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(
        json.dumps(
            {
                "total_target": 10,
                "categories": {
                    "custom_category": {
                        "description": "自定义测试类别",
                        "target_count": 10,
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    input_path = tmp_path / "custom.jsonl"
    write_jsonl(input_path, _category_records("custom_category", 10))
    output_dir = tmp_path / "output"
    monkeypatch.setattr(prepare_dataset, "TAXONOMY_PATH", taxonomy_path)

    return_code = prepare_dataset.main(
        [
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--config",
            str(CONFIG_PATH),
        ]
    )

    captured = capsys.readouterr()
    assert return_code == 0, captured.err
    assert captured.out == ""
    assert [
        len(load_jsonl(output_dir / f"{split_name}.jsonl"))
        for split_name in ("train", "validation", "test")
    ] == [8, 1, 1]


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


def test_prepare_dataset_cli_rejects_empty_jsonl_without_outputs(tmp_path):
    empty_input = tmp_path / "empty.jsonl"
    empty_input.write_bytes(b"")
    output_dir = tmp_path / "output"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "llm_lab.prepare_dataset",
            "--input",
            str(empty_input),
            "--output-dir",
            str(output_dir),
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
    assert "empty" in result.stderr or "at least one" in result.stderr
    assert not any(
        (output_dir / f"{split_name}.jsonl").exists()
        for split_name in ("train", "validation", "test")
    )
