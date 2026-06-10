import numpy as np
from PIL import Image

from video_pet_source import (
    DEFAULT_BACKGROUND_COLOR,
    HAS_SCIPY,
    VideoPetSource,
    clamp_scale,
    crop_frames_to_content,
    detect_background_color,
    filter_outlier_frames,
    frame_to_rgba_image,
    resolve_background_color,
)

import pytest


def test_four_channel_frame_preserves_alpha():
    frame = np.zeros((2, 2, 4), dtype=np.uint8)
    frame[:, :, 0] = 10
    frame[:, :, 1] = 20
    frame[:, :, 2] = 30
    frame[:, :, 3] = [[0, 64], [128, 255]]

    image = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=35)

    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((1, 0))[3] == 64
    assert image.getpixel((0, 1))[3] == 128
    assert image.getpixel((1, 1))[3] == 255


def test_three_channel_green_background_becomes_transparent():
    frame = np.array(
        [
            [[0, 255, 0], [200, 10, 10]],
            [[0, 250, 0], [30, 40, 50]],
        ],
        dtype=np.uint8,
    )

    image = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=10)

    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((0, 1))[3] == 0
    assert image.getpixel((1, 0))[3] == 255
    assert image.getpixel((1, 1))[3] == 255


def test_tolerance_changes_transparent_pixel_count():
    frame = np.array([[[0, 255, 0], [0, 200, 0], [50, 50, 50]]], dtype=np.uint8)

    strict = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=10)
    loose = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=80)

    strict_alpha = [strict.getpixel((x, 0))[3] for x in range(3)]
    loose_alpha = [loose.getpixel((x, 0))[3] for x in range(3)]
    assert strict_alpha.count(0) == 1
    assert loose_alpha.count(0) == 2


def test_detect_background_color_uses_frame_corners():
    frame = np.full((20, 20, 3), [0, 0, 0], dtype=np.uint8)
    frame[8:12, 8:12] = [240, 240, 240]

    assert detect_background_color(frame) == (0, 0, 0)


def test_default_green_key_auto_switches_to_detected_black_background():
    frame = np.full((20, 20, 3), [0, 0, 0], dtype=np.uint8)
    frame[8:12, 8:12] = [240, 240, 240]

    color = resolve_background_color(frame, DEFAULT_BACKGROUND_COLOR)

    assert color == (0, 0, 0)


def test_feathered_key_creates_partial_alpha_on_edge_pixels():
    frame = np.array([[[0, 255, 0], [0, 235, 0], [100, 100, 100]]], dtype=np.uint8)

    image = frame_to_rgba_image(frame, background_color=(0, 255, 0), tolerance=10, feather=30)

    assert image.getpixel((0, 0))[3] == 0
    assert 0 < image.getpixel((1, 0))[3] < 255
    assert image.getpixel((2, 0))[3] == 255


def test_warm_edge_artifacts_are_removed_when_scipy_is_available():
    if not HAS_SCIPY:
        pytest.skip("scipy is not installed")
    frame = np.zeros((120, 120, 3), dtype=np.uint8)
    frame[36:84, 36:84] = [240, 240, 240]
    frame[52:68, 35] = [255, 230, 0]

    image = frame_to_rgba_image(frame, background_color=(0, 0, 0), tolerance=10, feather=30)

    assert image.getpixel((35, 60))[3] == 0
    assert image.getpixel((60, 60))[3] == 255


def test_clamp_scale_limits_range():
    assert clamp_scale(0.1) == 0.5
    assert clamp_scale(1.25) == 1.25
    assert clamp_scale(3.0) == 2.5


def test_video_source_loops_frames_from_arrays():
    frames = [
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.full((1, 1, 3), 255, dtype=np.uint8),
    ]
    source = VideoPetSource.from_arrays(frames, background_color=(0, 255, 0), tolerance=35)

    first = source.next_frame()
    second = source.next_frame()
    third = source.next_frame()

    assert first.getpixel((0, 0)) != second.getpixel((0, 0))
    assert third.getpixel((0, 0)) == first.getpixel((0, 0))


def test_video_source_exposes_looping_frame_indexes():
    frames = [
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.full((1, 1, 3), 255, dtype=np.uint8),
    ]
    source = VideoPetSource.from_arrays(frames, background_color=(0, 255, 0), tolerance=35)

    assert source.next_frame_index() == 0
    assert source.next_frame_index() == 1
    assert source.next_frame_index() == 0


def test_filter_outlier_frames_removes_oversized_dirty_frames():
    clean = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for x in range(6, 14):
        for y in range(6, 14):
            clean.putpixel((x, y), (255, 255, 255, 255))
    dirty = Image.new("RGBA", (20, 20), (255, 255, 0, 255))

    frames = filter_outlier_frames([dirty, clean, clean, clean])

    assert frames == [clean, clean, clean]


def test_crop_frames_to_content_uses_common_content_box():
    first = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    first.paste((255, 255, 255, 255), (5, 6, 12, 14))
    second = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    second.paste((255, 255, 255, 255), (8, 3, 16, 18))

    cropped = crop_frames_to_content([first, second])

    assert [frame.size for frame in cropped] == [(11, 15), (11, 15)]
    assert cropped[0].getbbox() == (0, 3, 7, 11)
    assert cropped[1].getbbox() == (3, 0, 11, 15)
