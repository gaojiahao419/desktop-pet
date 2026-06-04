from pet_animator import PetAnimator


def test_default_state_is_idle():
    animator = PetAnimator()
    assert animator.state == "idle"


def test_click_cycle_from_idle_to_happy():
    animator = PetAnimator()
    animator.next_click_state()
    assert animator.state == "happy"


def test_click_cycle_wraps_through_states():
    animator = PetAnimator()
    seen = []
    for _ in range(4):
        animator.next_click_state()
        seen.append(animator.state)
    assert seen == ["happy", "idle", "walk", "sleep"]


def test_click_while_talking_goes_to_happy():
    animator = PetAnimator()
    animator.say("你好")
    animator.next_click_state()
    assert animator.state == "happy"
    assert animator.speech_text == ""


def test_advance_returns_frame_data():
    animator = PetAnimator()
    frame = animator.advance()
    assert frame.state == "idle"
    assert isinstance(frame.tick, int)
