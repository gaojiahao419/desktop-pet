from pathlib import Path
from typing import Iterable, List, Sequence

import imageio
import imageio.v3 as iio
import numpy as np
from PIL import Image


BLACK_BACKGROUND_THRESHOLD = 24
DEFAULT_VIDEO_FPS = 30.0
MAX_PLAYBACK_FPS = 30.0
MIN_PLAYBACK_SPEED = 0.25
MAX_PLAYBACK_SPEED = 3.0
LOOP_MODE_LOOP = "loop"
LOOP_MODE_ONCE = "once"
VALID_LOOP_MODES = {LOOP_MODE_LOOP, LOOP_MODE_ONCE}


def clamp_scale(value: float) -> float:
    return max(0.0, min(2.5, float(value)))


def clamp_playback_speed(value: float) -> float:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not np.isfinite(speed):
        return 1.0
    return max(MIN_PLAYBACK_SPEED, min(MAX_PLAYBACK_SPEED, speed))


def normalize_loop_mode(value: str) -> str:
    if value in VALID_LOOP_MODES:
        return value
    return LOOP_MODE_LOOP


def normalize_fps(value: float) -> float:
    try:
        fps = float(value)
    except (TypeError, ValueError):
        return DEFAULT_VIDEO_FPS
    if not np.isfinite(fps) or fps <= 0:
        return DEFAULT_VIDEO_FPS
    return max(1.0, min(120.0, fps))


def playback_frame_stride(fps: float, max_playback_fps: float = MAX_PLAYBACK_FPS) -> int:
    max_fps = normalize_fps(max_playback_fps)
    return max(1, int(round(normalize_fps(fps) / max_fps)))


def sampled_video_fps(fps: float, stride: int) -> float:
    return normalize_fps(fps) / max(1, int(stride))


def playback_interval_ms(fps: float, playback_speed: float = 1.0) -> int:
    effective_fps = normalize_fps(fps) * clamp_playback_speed(playback_speed)
    return max(8, int(round(1000 / effective_fps)))


def read_video_fps(path: Path) -> float:
    reader = None
    try:
        reader = imageio.get_reader(path)
        metadata = reader.get_meta_data()
        return normalize_fps(metadata.get("fps"))
    except Exception:
        return DEFAULT_VIDEO_FPS
    finally:
        if reader is not None:
            reader.close()


def black_background_mask(black_mask: np.ndarray) -> np.ndarray:
    if black_mask.ndim != 2:
        raise ValueError("black_background_mask requires a 2D mask")

    height, width = black_mask.shape
    if height == 0 or width == 0:
        return np.zeros(black_mask.shape, dtype=bool)

    foreground = ~black_mask
    rows_with_foreground = foreground.any(axis=1)
    left = np.argmax(foreground, axis=1)
    right = width - 1 - np.argmax(foreground[:, ::-1], axis=1)
    left = np.where(rows_with_foreground, left, width)
    right = np.where(rows_with_foreground, right, -1)

    columns_with_foreground = foreground.any(axis=0)
    top = np.argmax(foreground, axis=0)
    bottom = height - 1 - np.argmax(foreground[::-1, :], axis=0)
    top = np.where(columns_with_foreground, top, height)
    bottom = np.where(columns_with_foreground, bottom, -1)

    x = np.arange(width)[None, :]
    y = np.arange(height)[:, None]
    outside_row_span = (x < left[:, None]) | (x > right[:, None])
    outside_column_span = (y < top[None, :]) | (y > bottom[None, :])
    return black_mask & (outside_row_span | outside_column_span)


def frame_to_rgba_image(
    frame: np.ndarray,
    black_background_transparent: bool = False,
    black_threshold: int = BLACK_BACKGROUND_THRESHOLD,
) -> Image.Image:
    array = np.asarray(frame, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError(f"Unsupported video frame shape: {array.shape}")
    if black_background_transparent and array.shape[2] == 3:
        rgb = array[:, :, :3]
        black_mask = np.max(rgb, axis=2) <= int(black_threshold)
        background_mask = black_background_mask(black_mask)
        alpha = np.where(background_mask, 0, 255).astype(np.uint8)
        return Image.fromarray(np.dstack((rgb, alpha))).convert("RGBA")
    return Image.fromarray(array).convert("RGBA")


class VideoPetSource:
    def __init__(
        self,
        frames: Sequence[Image.Image],
        source_path: str = "",
        fps: float = DEFAULT_VIDEO_FPS,
    ) -> None:
        if not frames:
            raise ValueError("Video source requires at least one frame")
        self.frames: List[Image.Image] = [frame.convert("RGBA") for frame in frames]
        self.size = self.frames[0].size
        self.has_transparency = any(frame.getextrema()[3][0] < 255 for frame in self.frames)
        self.source_path = source_path
        self.fps = normalize_fps(fps)
        self.index = 0

    @classmethod
    def from_path(
        cls,
        path: str,
        black_background_transparent: bool = False,
        max_frames: int = 600,
        max_playback_fps: float = MAX_PLAYBACK_FPS,
    ) -> "VideoPetSource":
        video_path = Path(path)
        if video_path.suffix.lower() != ".mp4":
            raise ValueError("Please choose an MP4 file")

        source_fps = read_video_fps(video_path)
        stride = playback_frame_stride(source_fps, max_playback_fps)
        frames = []
        for frame_index, frame in enumerate(iio.imiter(video_path)):
            if frame_index % stride != 0:
                continue
            frames.append(
                frame_to_rgba_image(
                    frame,
                    black_background_transparent=black_background_transparent,
                )
            )
            if len(frames) >= max_frames:
                break

        if not frames:
            raise ValueError("Could not read any video frames")
        return cls(frames, source_path=str(video_path), fps=sampled_video_fps(source_fps, stride))

    @classmethod
    def from_arrays(
        cls,
        frames: Iterable[np.ndarray],
        black_background_transparent: bool = False,
        fps: float = DEFAULT_VIDEO_FPS,
    ) -> "VideoPetSource":
        images = [
            frame_to_rgba_image(frame, black_background_transparent=black_background_transparent)
            for frame in frames
        ]
        return cls(images, fps=fps)

    def frame_interval_ms(self, playback_speed: float = 1.0) -> int:
        return playback_interval_ms(self.fps, playback_speed=playback_speed)

    def next_frame(self, loop_mode: str = LOOP_MODE_LOOP) -> Image.Image:
        frame = self.frames[self.next_frame_index(loop_mode)]
        return frame

    def next_frame_index(self, loop_mode: str = LOOP_MODE_LOOP) -> int:
        mode = normalize_loop_mode(loop_mode)
        index = self.index
        if mode == LOOP_MODE_ONCE:
            self.index = min(len(self.frames) - 1, self.index + 1)
            return min(index, len(self.frames) - 1)
        self.index = (self.index + 1) % len(self.frames)
        return index

    def reset(self) -> None:
        self.index = 0
