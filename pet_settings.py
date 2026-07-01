import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from video_pet_source import VALID_LOOP_MODES, clamp_playback_speed


SETTINGS_PATH = Path("pet_settings.json")


@dataclass(frozen=True)
class PetSettings:
    scale: float = 1.0
    black_background_transparent: bool = False
    state_materials: Dict[str, str] = field(default_factory=dict)
    state_scales: Dict[str, float] = field(default_factory=dict)
    state_playback_speeds: Dict[str, float] = field(default_factory=dict)
    state_loop_modes: Dict[str, str] = field(default_factory=dict)


def load_settings(path: Path = SETTINGS_PATH) -> PetSettings:
    if not path.exists():
        return PetSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PetSettings()

    materials = data.get("state_materials", {})
    if not isinstance(materials, dict):
        materials = {}
    state_scales = data.get("state_scales", {})
    if not isinstance(state_scales, dict):
        state_scales = {}
    state_scales = {
        str(key): float(value)
        for key, value in state_scales.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    state_playback_speeds = data.get("state_playback_speeds", {})
    if not isinstance(state_playback_speeds, dict):
        state_playback_speeds = {}
    state_playback_speeds = {
        str(key): clamp_playback_speed(value)
        for key, value in state_playback_speeds.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    state_loop_modes = data.get("state_loop_modes", {})
    if not isinstance(state_loop_modes, dict):
        state_loop_modes = {}
    state_loop_modes = {
        str(key): str(value)
        for key, value in state_loop_modes.items()
        if str(value) in VALID_LOOP_MODES
    }
    black_background_transparent = data.get(
        "black_background_transparent",
        PetSettings().black_background_transparent,
    )
    if not isinstance(black_background_transparent, bool):
        black_background_transparent = PetSettings().black_background_transparent

    return PetSettings(
        scale=float(data.get("scale", PetSettings().scale)),
        black_background_transparent=black_background_transparent,
        state_materials={str(key): str(value) for key, value in materials.items()},
        state_scales=state_scales,
        state_playback_speeds=state_playback_speeds,
        state_loop_modes=state_loop_modes,
    )


def save_settings(path: Path, settings: PetSettings) -> None:
    data = {
        "scale": settings.scale,
        "black_background_transparent": settings.black_background_transparent,
        "state_materials": settings.state_materials,
        "state_scales": settings.state_scales,
        "state_playback_speeds": settings.state_playback_speeds,
        "state_loop_modes": settings.state_loop_modes,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
