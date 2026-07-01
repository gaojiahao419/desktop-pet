from dataclasses import dataclass
from math import sin


VALID_STATES = {"idle", "happy", "sleep", "angry", "walk", "talk", "hidden"}
CLICK_SEQUENCE = ["idle", "happy", "angry", "sleep"]


@dataclass(frozen=True)
class PetFrame:
    state: str
    tick: int
    body_y: int
    eye_closed: bool
    mouth_open: bool
    walk_dx: int


class PetAnimator:
    def __init__(self) -> None:
        self.state = "idle"
        self.tick = 0
        self.speech_text = ""
        self.speech_ticks_left = 0
        self._click_index = 0

    def set_state(self, state: str) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported pet state: {state}")
        self.state = state
        if state != "talk":
            self.clear_speech()

    def say(self, text: str, duration_ticks: int = 80, preserve_state: bool = False) -> None:
        if not preserve_state:
            self.state = "talk"
        self.speech_text = text
        self.speech_ticks_left = duration_ticks

    def clear_speech(self) -> None:
        self.speech_text = ""
        self.speech_ticks_left = 0

    def next_click_state(self) -> str:
        if self.state == "talk":
            self.set_state("happy")
            self._click_index = CLICK_SEQUENCE.index("happy")
            return self.state

        self._click_index = (self._click_index + 1) % len(CLICK_SEQUENCE)
        next_state = CLICK_SEQUENCE[self._click_index]
        self.set_state(next_state)
        return self.state

    def advance(self) -> PetFrame:
        self.tick += 1
        if self.speech_ticks_left > 0:
            self.speech_ticks_left -= 1
            if self.speech_ticks_left == 0:
                was_talking = self.state == "talk"
                self.clear_speech()
                if was_talking:
                    self.state = "idle"

        return PetFrame(
            state=self.state,
            tick=self.tick,
            body_y=self._body_y(),
            eye_closed=self._eye_closed(),
            mouth_open=self._mouth_open(),
            walk_dx=self._walk_dx(),
        )

    def _body_y(self) -> int:
        if self.state == "happy":
            return -6 if (self.tick // 6) % 2 == 0 else 0
        if self.state == "angry":
            return -3 if (self.tick // 4) % 2 == 0 else 1
        if self.state == "sleep":
            return 2
        return int(sin(self.tick / 8) * 2)

    def _eye_closed(self) -> bool:
        if self.state == "sleep":
            return True
        return self.tick % 90 in (0, 1, 2, 3)

    def _mouth_open(self) -> bool:
        return self.state == "talk" and (self.tick // 8) % 2 == 0

    def _walk_dx(self) -> int:
        if self.state != "walk":
            return 0
        return 2 if (self.tick // 10) % 2 == 0 else -2
