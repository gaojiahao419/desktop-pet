from pet_settings import PetSettings, load_settings, save_settings


def test_settings_round_trip_persists_state_materials(tmp_path):
    path = tmp_path / "pet_settings.json"
    settings = PetSettings(
        background_color=(0, 255, 0),
        tolerance=42,
        scale=1.4,
        state_materials={"idle": "D:/assets/idle.mp4", "happy": "D:/assets/happy.mp4"},
    )

    save_settings(path, settings)
    loaded = load_settings(path)

    assert loaded == settings


def test_missing_settings_returns_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.json")

    assert settings.background_color == (0, 255, 0)
    assert settings.tolerance == 35
    assert settings.scale == 1.0
    assert settings.state_materials == {}
