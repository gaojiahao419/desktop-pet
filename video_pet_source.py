from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import imageio.v3 as iio
import numpy as np
from PIL import Image


Color = Tuple[int, int, int]


def clamp_scale(value: float) -> float:
    return max(0.5, min(2.5, float(value)))


def clamp_tolerance(value: int) -> int:
    return max(0, min(120, int(value)))


def frame_to_rgba_image(frame: np.ndarray, background_color: Color, tolerance: int) -> Image.Image:
    array = np.asarray(frame, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError(f"Unsupported video frame shape: {array.shape}")

    if array.shape[2] == 4:
        return Image.fromarray(array).convert("RGBA")

    rgb = array[:, :, :3]
    alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    bg = np.array(background_color, dtype=np.int16)
    diff = np.abs(rgb.astype(np.int16) - bg)
    mask = np.max(diff, axis=2) <= clamp_tolerance(tolerance)
    alpha[mask] = 0
    rgba = np.dstack((rgb, alpha))
    return Image.fromarray(rgba).convert("RGBA")


class VideoPetSource:
    def __init__(self, frames: Sequence[Image.Image], source_path: str = "") -> None:
        if not frames:
            raise ValueError("Video source requires at least one frame")
        self.frames: List[Image.Image] = [frame.convert("RGBA") for frame in frames]
        self.source_path = source_path
        self.index = 0

    @classmethod
    def from_path(
        cls,
        path: str,
        background_color: Color = (0, 255, 0),
        tolerance: int = 35,
        max_frames: int = 600,
    ) -> "VideoPetSource":
        video_path = Path(path)
        if video_path.suffix.lower() != ".mp4":
            raise ValueError("请选择 MP4 文件")

        frames = []
        for frame in iio.imiter(video_path):
            frames.append(frame_to_rgba_image(frame, background_color, tolerance))
            if len(frames) >= max_frames:
                break

        if not frames:
            raise ValueError("无法读取视频帧")
        return cls(frames, source_path=str(video_path))

    @classmethod
    def from_arrays(
        cls,
        frames: Iterable[np.ndarray],
        background_color: Color = (0, 255, 0),
        tolerance: int = 35,
    ) -> "VideoPetSource":
        images = [frame_to_rgba_image(frame, background_color, tolerance) for frame in frames]
        return cls(images)

    def next_frame(self) -> Image.Image:
        frame = self.frames[self.index]
        self.index = (self.index + 1) % len(self.frames)
        return frame
