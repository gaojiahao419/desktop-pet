from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import imageio.v3 as iio
import numpy as np
from PIL import Image

try:
    from scipy import ndimage
except ImportError:  # pragma: no cover - optional quality improvement
    ndimage = None


Color = Tuple[int, int, int]
DEFAULT_BACKGROUND_COLOR: Color = (0, 255, 0)
HAS_SCIPY = ndimage is not None


def clamp_scale(value: float) -> float:
    return max(0.5, min(2.5, float(value)))


def clamp_tolerance(value: int) -> int:
    return max(0, min(120, int(value)))


def detect_background_color(frame: np.ndarray) -> Color:
    array = np.asarray(frame, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError(f"Unsupported video frame shape: {array.shape}")

    height, width = array.shape[:2]
    patch = max(1, min(width, height) // 20)
    rgb = array[:, :, :3]
    corners = [
        rgb[:patch, :patch],
        rgb[:patch, -patch:],
        rgb[-patch:, :patch],
        rgb[-patch:, -patch:],
    ]
    pixels = np.concatenate([corner.reshape(-1, 3) for corner in corners], axis=0)
    color = np.median(pixels, axis=0).astype(np.uint8)
    return tuple(int(value) for value in color)


def resolve_background_color(frame: np.ndarray, background_color: Color) -> Color:
    requested = tuple(int(value) for value in background_color)
    detected = detect_background_color(frame)
    if requested != DEFAULT_BACKGROUND_COLOR:
        return requested

    distance = max(abs(detected[index] - requested[index]) for index in range(3))
    if distance > 80:
        return detected
    return requested


def frame_to_rgba_image(
    frame: np.ndarray,
    background_color: Color,
    tolerance: int,
    feather: int = 35,
) -> Image.Image:
    array = np.asarray(frame, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError(f"Unsupported video frame shape: {array.shape}")

    if array.shape[2] == 4:
        return Image.fromarray(array).convert("RGBA")

    rgb = array[:, :, :3].astype(np.float32)
    bg = np.array(background_color, dtype=np.float32)
    distance = np.max(np.abs(rgb - bg), axis=2)
    tolerance = clamp_tolerance(tolerance)
    feather = max(1, int(feather))

    alpha = np.clip((distance - tolerance) * 255 / feather, 0, 255).astype(np.uint8)
    alpha_float = alpha.astype(np.float32) / 255
    edge = (alpha > 0) & (alpha < 255)
    corrected = rgb.copy()
    if np.any(edge):
        corrected[edge] = (rgb[edge] - bg * (1 - alpha_float[edge, None])) / alpha_float[edge, None]
        corrected = np.clip(corrected, 0, 255)

    rgba = np.dstack((corrected.astype(np.uint8), alpha))
    rgba = clean_foreground_artifacts(rgba)
    return Image.fromarray(rgba).convert("RGBA")


def clean_foreground_artifacts(rgba: np.ndarray) -> np.ndarray:
    if ndimage is None:
        return rgba

    cleaned = rgba.copy()
    alpha = cleaned[:, :, 3]
    if alpha.size < 4096:
        return cleaned

    mask = alpha > 8
    if not np.any(mask):
        return cleaned

    rgb = cleaned[:, :, :3].astype(np.float32)
    inside_distance = ndimage.distance_transform_edt(mask)
    max_channel = rgb.max(axis=2)
    min_channel = rgb.min(axis=2)
    saturation = np.zeros_like(max_channel)
    nonzero = max_channel > 0
    saturation[nonzero] = (max_channel[nonzero] - min_channel[nonzero]) / max_channel[nonzero]

    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]
    warm_artifact_color = ((red > 130) & (green > 80) & (blue < 120)) | (
        (red > 130) & (green < 120) & (blue < 120)
    )
    artifact = mask & (inside_distance < 22) & (saturation > 0.45) & warm_artifact_color
    alpha = np.where(artifact, 0, alpha).astype(np.uint8)

    mask = alpha > 8
    labels, count = ndimage.label(mask)
    if count:
        sizes = np.bincount(labels.ravel())
        sizes[0] = 0
        min_area = max(1, int(mask.size * 0.0002))
        keep_labels = np.flatnonzero(sizes >= min_area)
        keep = np.isin(labels, keep_labels)
        alpha = np.where(keep, alpha, 0).astype(np.uint8)

    cleaned[:, :, 3] = alpha
    return cleaned


def filter_outlier_frames(frames: Sequence[Image.Image]) -> List[Image.Image]:
    if len(frames) < 4:
        return list(frames)

    areas = []
    for frame in frames:
        alpha = np.asarray(frame.convert("RGBA"))[:, :, 3]
        areas.append(int((alpha > 8).sum()))

    median_area = float(np.median(areas))
    if median_area <= 0:
        return list(frames)

    filtered = [frame for frame, area in zip(frames, areas) if area <= median_area * 1.25]
    return filtered or list(frames)


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
        background_color: Color = DEFAULT_BACKGROUND_COLOR,
        tolerance: int = 35,
        max_frames: int = 600,
    ) -> "VideoPetSource":
        video_path = Path(path)
        if video_path.suffix.lower() != ".mp4":
            raise ValueError("请选择 MP4 文件")

        frames = []
        key_color = None
        for frame in iio.imiter(video_path):
            if key_color is None:
                key_color = resolve_background_color(frame, background_color)
            frames.append(frame_to_rgba_image(frame, key_color, tolerance))
            if len(frames) >= max_frames:
                break

        if not frames:
            raise ValueError("无法读取视频帧")
        frames = filter_outlier_frames(frames)
        return cls(frames, source_path=str(video_path))

    @classmethod
    def from_arrays(
        cls,
        frames: Iterable[np.ndarray],
        background_color: Color = DEFAULT_BACKGROUND_COLOR,
        tolerance: int = 35,
    ) -> "VideoPetSource":
        images = [frame_to_rgba_image(frame, background_color, tolerance) for frame in frames]
        return cls(images)

    def next_frame(self) -> Image.Image:
        frame = self.frames[self.next_frame_index()]
        return frame

    def next_frame_index(self) -> int:
        index = self.index
        self.index = (self.index + 1) % len(self.frames)
        return index
