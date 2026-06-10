import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple


SETTINGS_PATH = Path("pet_settings.json")


@dataclass(frozen=True)
class PetSettings:
    background_color: Tuple[int, int, int] = (0, 255, 0)
    tolerance: int = 35
    scale: float = 1.0
    state_materials: Dict[str, str] = field(default_factory=dict)


def load_settings(path: Path = SETTINGS_PATH) -> PetSettings:
    if not path.exists():
        return PetSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PetSettings()

    color = data.get("background_color", PetSettings().background_color)
    if not isinstance(color, list) or len(color) != 3:
        color = PetSettings().background_color

    materials = data.get("state_materials", {})
    if not isinstance(materials, dict):
        materials = {}

    return PetSettings(
        background_color=tuple(int(value) for value in color),
        tolerance=int(data.get("tolerance", PetSettings().tolerance)),
        scale=float(data.get("scale", PetSettings().scale)),
        state_materials={str(key): str(value) for key, value in materials.items()},
    )


def save_settings(path: Path, settings: PetSettings) -> None:
    data = {
        "background_color": list(settings.background_color),
        "tolerance": settings.tolerance,
        "scale": settings.scale,
        "state_materials": settings.state_materials,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
