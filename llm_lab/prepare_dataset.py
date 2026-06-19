from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

from llm_lab.config import load_training_config
from llm_lab.data_io import (
    DatasetSplit,
    load_jsonl,
    split_records,
    validate_dataset,
    write_jsonl,
)


TAXONOMY_PATH = Path(__file__).resolve().parent / "data" / "taxonomy.json"


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and split chat JSONL data")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    return parser.parse_args(argv)


def _load_allowed_categories(path: Path) -> list[str]:
    try:
        with path.open(encoding="utf-8") as taxonomy_file:
            taxonomy = json.load(taxonomy_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Taxonomy file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid taxonomy JSON in {path}: {exc.msg}") from exc
    if not isinstance(taxonomy, dict) or not isinstance(
        taxonomy.get("categories"), dict
    ):
        raise ValueError("Taxonomy must contain a categories object")
    categories = list(taxonomy["categories"])
    if not categories:
        raise ValueError("Taxonomy categories must not be empty")
    return categories


def _format_distribution(records: list[dict], categories: Sequence[str]) -> str:
    counts = Counter(record["category"] for record in records)
    return ", ".join(f"{category}={counts[category]}" for category in categories)


def _report(split: DatasetSplit, total: int, categories: Sequence[str]) -> None:
    print(
        f"total={total} train={len(split.train)} "
        f"validation={len(split.validation)} test={len(split.test)}",
        file=sys.stderr,
    )
    for name, records in (
        ("train", split.train),
        ("validation", split.validation),
        ("test", split.test),
    ):
        print(
            f"{name} categories: {_format_distribution(records, categories)}",
            file=sys.stderr,
        )


def run(input_path: Path, output_dir: Path, config_path: Path) -> None:
    config = load_training_config(config_path)
    categories = _load_allowed_categories(TAXONOMY_PATH)
    records = load_jsonl(input_path)
    validate_dataset(records, categories)
    split = split_records(
        records,
        seed=config.seed,
        train_ratio=config.train_ratio,
        validation_ratio=config.validation_ratio,
        test_ratio=config.test_ratio,
    )
    write_jsonl(output_dir / "train.jsonl", split.train)
    write_jsonl(output_dir / "validation.jsonl", split.validation)
    write_jsonl(output_dir / "test.jsonl", split.test)
    _report(split, len(records), categories)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        run(args.input, args.output_dir, args.config)
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
