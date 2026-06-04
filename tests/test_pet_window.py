import pet_window


class FakeVideoSource:
    pass


def test_select_video_source_prefers_source_bound_to_active_state():
    fallback = FakeVideoSource()
    idle_source = FakeVideoSource()
    happy_source = FakeVideoSource()

    source = pet_window.select_video_source_for_state(
        "happy",
        {"idle": idle_source, "happy": happy_source},
        fallback,
    )

    assert source is happy_source


def test_select_video_source_falls_back_to_default_source():
    fallback = FakeVideoSource()
    idle_source = FakeVideoSource()

    source = pet_window.select_video_source_for_state(
        "sleep",
        {"idle": idle_source},
        fallback,
    )

    assert source is fallback
