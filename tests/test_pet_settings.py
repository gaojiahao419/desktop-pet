from pet_settings import PetSettings, load_settings, save_settings


def test_settings_round_trip_persists_state_materials(tmp_path):
    path = tmp_path / "pet_settings.json"
    settings = PetSettings(
        scale=1.4,
        black_background_transparent=True,
        state_materials={"idle": "D:/assets/idle.mp4", "happy": "D:/assets/happy.mp4"},
        state_scales={"idle": 0.8, "happy": 1.4},
        state_playback_speeds={"idle": 0.75, "happy": 1.5},
        state_loop_modes={"idle": "loop", "happy": "once"},
    )

    save_settings(path, settings)
    loaded = load_settings(path)

    assert loaded == settings


def test_missing_settings_returns_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.json")

    assert settings.scale == 1.0
    assert settings.black_background_transparent is False
    assert settings.state_materials == {}
    assert settings.state_playback_speeds == {}
    assert settings.state_loop_modes == {}


def test_old_keying_settings_are_ignored(tmp_path):
    path = tmp_path / "pet_settings.json"
    path.write_text(
        '{"background_color":[0,255,0],"tolerance":42,"scale":1.2,"state_materials":{"idle":"idle.mp4"}}',
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings == PetSettings(scale=1.2, state_materials={"idle": "idle.mp4"})


def test_settings_load_state_scales(tmp_path):
    path = tmp_path / "pet_settings.json"
    path.write_text(
        '{"scale":1.0,"state_scales":{"idle":0.7,"happy":1.3,"bad":true}}',
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.state_scales == {"idle": 0.7, "happy": 1.3}


def test_settings_load_state_playback_speeds_and_loop_modes(tmp_path):
    path = tmp_path / "pet_settings.json"
    path.write_text(
        '{"state_playback_speeds":{"idle":0.75,"happy":1.5,"bad":true},'
        '"state_loop_modes":{"idle":"loop","happy":"once","bad":"invalid"}}',
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.state_playback_speeds == {"idle": 0.75, "happy": 1.5}
    assert settings.state_loop_modes == {"idle": "loop", "happy": "once"}
