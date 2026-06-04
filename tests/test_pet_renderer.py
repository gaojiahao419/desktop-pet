from pet_animator import PetFrame
from pet_renderer import PetRenderer


def test_renderer_returns_transparent_rgba_image():
    renderer = PetRenderer()
    frame = PetFrame("idle", 1, 0, False, False, 0)
    image = renderer.render(frame)
    assert image.mode == "RGBA"
    assert image.size == (220, 220)
    assert image.getpixel((0, 0))[3] == 0


def test_renderer_draws_nontransparent_pet_pixels():
    renderer = PetRenderer()
    frame = PetFrame("happy", 1, -4, False, False, 0)
    image = renderer.render(frame)
    assert image.getbbox() is not None


def test_renderer_can_draw_speech_bubble():
    renderer = PetRenderer()
    frame = PetFrame("talk", 1, 0, False, True, 0)
    image = renderer.render(frame, speech_text="你好")
    assert image.getbbox() is not None
