from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import tempfile
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast


DEFAULT_CATEGORIES = frozenset(
    {
        "daily_chat",
        "emotion_support",
        "light_humor",
        "pet_persona",
        "safety_boundary",
    }
)


class Message(TypedDict):
    role: str
    content: str


class ConversationRecord(TypedDict):
    id: str
    category: str
    messages: list[Message]


@dataclass(frozen=True)
class DatasetSplit:
    train: list[ConversationRecord]
    validation: list[ConversationRecord]
    test: list[ConversationRecord]


def load_jsonl(path: Path) -> list[ConversationRecord]:
    jsonl_path = Path(path)
    records: list[ConversationRecord] = []
    try:
        with jsonl_path.open(encoding="utf-8-sig") as jsonl_file:
            for line_number, line in enumerate(jsonl_file, start=1):
                if not line.strip():
                    raise ValueError(
                        f"Invalid blank JSONL line {line_number} in {jsonl_path}"
                    )
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON in {jsonl_path} at line {line_number}: "
                        f"{exc.msg}"
                    ) from exc
                if not isinstance(value, dict):
                    raise ValueError(
                        f"JSONL line {line_number} in {jsonl_path} must be an object"
                    )
                records.append(cast(ConversationRecord, value))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Unable to decode {jsonl_path} as UTF-8: {exc.reason}"
        ) from exc
    return records


def write_jsonl(path: Path, records: Sequence[ConversationRecord]) -> None:
    jsonl_path = Path(path)
    serialized_records: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each JSONL record must be an object")
        serialized_records.append(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        )
    payload = "".join(f"{record}\n" for record in serialized_records)

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=jsonl_path.parent,
        prefix=f".{jsonl_path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    os.close(file_descriptor)
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as temp_file:
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, jsonl_path)
    finally:
        temp_path.unlink(missing_ok=True)


def validate_record(
    record: Mapping[str, object],
    allowed_categories: Collection[str] | None = None,
) -> None:
    if not isinstance(record, Mapping):
        raise ValueError("Dataset record must be a JSON object")

    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id.strip():
        raise ValueError("Record id must be a non-empty string")
    if record_id != record_id.strip():
        raise ValueError(f"Record {record_id!r} id must not contain surrounding whitespace")

    category = record.get("category")
    if not isinstance(category, str) or not category.strip():
        raise ValueError(f"Record {record_id} category must be a non-empty string")
    categories = (
        DEFAULT_CATEGORIES if allowed_categories is None else allowed_categories
    )
    if category not in categories:
        raise ValueError(f"Record {record_id} has unknown category {category!r}")

    messages = record.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"Record {record_id} messages must be a non-empty list")

    roles: list[str] = []
    for index, message in enumerate(messages, start=1):
        if not isinstance(message, Mapping):
            raise ValueError(f"Record {record_id} message {index} must be an object")
        role = message.get("role")
        if role not in {"user", "assistant"}:
            raise ValueError(
                f"Record {record_id} message {index} has unknown role {role!r}"
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"Record {record_id} message {index} content must be a non-empty string"
            )
        if content != content.strip():
            raise ValueError(
                f"Record {record_id} message {index} content must be trimmed"
            )
        roles.append(role)

    if roles[0] != "user":
        raise ValueError(f"Record {record_id} messages must start with user")
    if any(current == previous for previous, current in zip(roles, roles[1:])):
        raise ValueError(
            f"Record {record_id} roles must strictly alternate user and assistant"
        )
    if roles[-1] != "assistant":
        raise ValueError(f"Record {record_id} messages must end with assistant")


def validate_dataset(
    records: Sequence[Mapping[str, object]],
    allowed_categories: Collection[str] | None = None,
) -> None:
    if not records:
        raise ValueError("Dataset must contain at least one record; empty is invalid")
    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        try:
            validate_record(record, allowed_categories)
        except ValueError as exc:
            raise ValueError(f"Invalid record {index}: {exc}") from exc
        record_id = record["id"]
        if record_id in seen_ids:
            raise ValueError(f"Record {index} has duplicate id {record_id}")
        seen_ids.add(record_id)


def _derived_random(seed: int, namespace: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}\0{namespace}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def _validate_ratios(
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
) -> None:
    ratios = (train_ratio, validation_ratio, test_ratio)
    if any(
        isinstance(ratio, bool) or not isinstance(ratio, (int, float))
        for ratio in ratios
    ):
        raise ValueError("Split ratios must be finite numbers")
    if any(not math.isfinite(ratio) for ratio in ratios):
        raise ValueError("Split ratios must be finite numbers")
    if any(ratio <= 0 for ratio in ratios):
        raise ValueError("Split ratios must each be positive")
    if not math.isclose(sum(ratios), 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("Split ratios must sum to 1")


def _allocate_split_counts(
    count: int,
    ratios: tuple[float, float, float],
) -> tuple[int, int, int]:
    """Use largest remainders; ties follow train, validation, test order."""
    quotas = [count * ratio for ratio in ratios]
    counts = [math.floor(quota) for quota in quotas]
    remaining = count - sum(counts)
    remainder_order = sorted(
        range(3),
        key=lambda index: (-(quotas[index] - counts[index]), index),
    )
    for index in remainder_order[:remaining]:
        counts[index] += 1

    zero_indexes = [
        index for index, split_count in enumerate(counts) if split_count == 0
    ]
    for zero_index in zero_indexes:
        donor_index = min(
            (index for index, split_count in enumerate(counts) if split_count > 1),
            key=lambda index: (-counts[index], index),
        )
        counts[donor_index] -= 1
        counts[zero_index] += 1
    return cast(tuple[int, int, int], tuple(counts))


def split_records(
    records: Sequence[Mapping[str, object]],
    seed: int = 42,
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
    test_ratio: float = 0.1,
    allowed_categories: Collection[str] | None = None,
) -> DatasetSplit:
    _validate_ratios(train_ratio, validation_ratio, test_ratio)
    validate_dataset(records, allowed_categories)

    grouped: dict[str, list[ConversationRecord]] = defaultdict(list)
    for record in records:
        grouped[str(record["category"])].append(
            cast(ConversationRecord, copy.deepcopy(dict(record)))
        )

    train: list[ConversationRecord] = []
    validation: list[ConversationRecord] = []
    test: list[ConversationRecord] = []
    for category in sorted(grouped):
        category_records = grouped[category]
        _derived_random(seed, f"category:{category}").shuffle(category_records)
        count = len(category_records)
        if count < 3:
            raise ValueError(
                f"Category {category!r} must contain at least 3 records; got {count}"
            )
        train_count, validation_count, test_count = _allocate_split_counts(
            count,
            (train_ratio, validation_ratio, test_ratio),
        )

        train.extend(category_records[:train_count])
        validation.extend(
            category_records[train_count : train_count + validation_count]
        )
        test.extend(category_records[train_count + validation_count :])

    _derived_random(seed, "split:train").shuffle(train)
    _derived_random(seed, "split:validation").shuffle(validation)
    _derived_random(seed, "split:test").shuffle(test)
    return DatasetSplit(train=train, validation=validation, test=test)
