import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _requirement_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"[A-Za-z0-9_.-]+", line.strip())
        if match:
            names.add(match.group(0).lower().replace("_", "-"))
    return names


def test_llm_dependencies_are_isolated_from_desktop_pet() -> None:
    desktop_dependencies = _requirement_names(ROOT / "requirements.txt")
    llm_dependencies = _requirement_names(ROOT / "requirements-llm.txt")

    assert "transformers" not in desktop_dependencies
    assert {"transformers", "peft", "trl", "bitsandbytes"} <= llm_dependencies
