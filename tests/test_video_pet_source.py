import numpy as np

from video_pet_source import (
    VideoPetSource,
    clamp_scale,
    clamp_playback_speed,
    frame_to_rgba_image,
    normalize_loop_mode,
    playback_frame_stride,
    playback_interval_ms,
    sampled_video_fps,
)


def test_four_channel_frame_preserves_alpha():
    frame = np.zeros((2, 2, 4), dtype=np.uint8)
    frame[:, :, 0] = 10
    frame[:, :, 1] = 20
    frame[:, :, 2] = 30
    frame[:, :, 3] = [[0, 64], [128, 255]]

    image = frame_to_rgba_image(frame)

    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((1, 0))[3] == 64
    assert image.getpixel((0, 1))[3] == 128
    assert image.getpixel((1, 1))[3] == 255


def test_three_channel_frame_stays_opaque_without_keying():
    frame = np.array(
        [
            [[0, 255, 0], [200, 10, 10]],
            [[0, 0, 0], [30, 40, 50]],
        ],
        dtype=np.uint8,
    )

    image = frame_to_rgba_image(frame)

    assert image.getpixel((0, 0)) == (0, 255, 0, 255)
    assert image.getpixel((0, 1)) == (0, 0, 0, 255)


def test_black_background_transparency_option_keys_black_pixels():
    frame = np.array(
        [
            [[0, 0, 0], [12, 12, 12], [50, 50, 50]],
            [[210, 120, 80], [0, 0, 40], [255, 255, 255]],
        ],
        dtype=np.uint8,
    )

    image = frame_to_rgba_image(frame, black_background_transparent=True)

    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((1, 0))[3] == 0
    assert image.getpixel((2, 0))[3] == 255
    assert image.getpixel((1, 1))[3] == 255


def test_black_background_transparency_preserves_internal_black_details():
    frame = np.full((5, 5, 3), 220, dtype=np.uint8)
    frame[0, :, :] = 0
    frame[-1, :, :] = 0
    frame[:, 0, :] = 0
    frame[:, -1, :] = 0
    frame[2, 2, :] = 0

    image = frame_to_rgba_image(frame, black_background_transparent=True)

    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((4, 4))[3] == 0
    assert image.getpixel((2, 2))[3] == 255


def test_clamp_scale_limits_range():
    assert clamp_scale(-0.1) == 0.0
    assert clamp_scale(0.0) == 0.0
    assert clamp_scale(0.1) == 0.1
    assert clamp_scale(1.25) == 1.25
    assert clamp_scale(3.0) == 2.5


def test_playback_speed_limits_range():
    assert clamp_playback_speed(0.1) == 0.25
    assert clamp_playback_speed(1.5) == 1.5
    assert clamp_playback_speed(5.0) == 3.0


def test_normalize_loop_mode_falls_back_to_loop():
    assert normalize_loop_mode("loop") == "loop"
    assert normalize_loop_mode("once") == "once"
    assert normalize_loop_mode("bad") == "loop"


def test_playback_stride_downsamples_high_fps_video_to_30fps():
    stride = playback_frame_stride(60.0)

    assert stride == 2
    assert sampled_video_fps(60.0, stride) == 30.0


def test_playback_interval_matches_effective_video_fps():
    assert playback_interval_ms(30.0) == 33
    assert playback_interval_ms(24.0) == 42
    assert playback_interval_ms(30.0, playback_speed=2.0) == 17
    assert playback_interval_ms(30.0, playback_speed=0.5) == 67


def test_video_source_loops_frames_from_arrays():
    frames = [
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.full((1, 1, 3), 255, dtype=np.uint8),
    ]
    source = VideoPetSource.from_arrays(frames)

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
    source = VideoPetSource.from_arrays(frames)

    assert source.next_frame_index() == 0
    assert source.next_frame_index() == 1
    assert source.next_frame_index() == 0


def test_video_source_once_loop_mode_holds_last_frame():
    frames = [
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.full((1, 1, 3), 255, dtype=np.uint8),
    ]
    source = VideoPetSource.from_arrays(frames)

    assert source.next_frame_index("once") == 0
    assert source.next_frame_index("once") == 1
    assert source.next_frame_index("once") == 1

    source.reset()
    assert source.next_frame_index("once") == 0


def test_video_source_keeps_source_frame_size():
    frame = np.zeros((20, 30, 4), dtype=np.uint8)
    frame[5:10, 7:12, 3] = 255

    source = VideoPetSource.from_arrays([frame])

    assert source.size == (30, 20)
    assert source.next_frame().size == (30, 20)


def test_video_source_reports_whether_frames_have_transparency():
    transparent = np.zeros((2, 2, 4), dtype=np.uint8)
    transparent[:, :, 3] = [[0, 255], [255, 255]]
    opaque = np.zeros((2, 2, 3), dtype=np.uint8)

    assert VideoPetSource.from_arrays([transparent]).has_transparency is True
    assert VideoPetSource.from_arrays([opaque]).has_transparency is False


def test_video_source_reports_transparency_after_black_keying():
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    frame[1, 1] = [255, 255, 255]

    source = VideoPetSource.from_arrays([frame], black_background_transparent=True)

    assert source.has_transparency is True
    assert source.next_frame().getpixel((0, 0))[3] == 0
