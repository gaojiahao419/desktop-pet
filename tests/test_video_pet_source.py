import numpy as np

from video_pet_source import VideoPetSource, clamp_scale, frame_to_rgba_image


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
