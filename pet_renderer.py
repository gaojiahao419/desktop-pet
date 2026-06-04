from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pet_animator import PetFrame


class PetRenderer:
    def __init__(self, size: int = 220) -> None:
        self.size = size
        self.font = self._load_font()

    def render(self, frame: PetFrame, speech_text: str = "") -> Image.Image:
        image = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        cx = self.size // 2 + frame.walk_dx
        cy = 130 + frame.body_y
        body_color = self._body_color(frame.state)

        draw.ellipse(
            (cx - 48, cy - 55, cx + 48, cy + 45),
            fill=body_color,
            outline=(70, 56, 48, 255),
            width=3,
        )
        draw.polygon(
            [(cx - 40, cy - 40), (cx - 62, cy - 82), (cx - 18, cy - 58)],
            fill=body_color,
            outline=(70, 56, 48, 255),
        )
        draw.polygon(
            [(cx + 40, cy - 40), (cx + 62, cy - 82), (cx + 18, cy - 58)],
            fill=body_color,
            outline=(70, 56, 48, 255),
        )

        self._draw_face(draw, frame, cx, cy)
        self._draw_feet(draw, frame, cx, cy)

        if frame.state == "sleep":
            draw.text((cx + 44, cy - 80), "Z", fill=(55, 55, 70, 230), font=self.font)
            draw.text((cx + 60, cy - 96), "z", fill=(55, 55, 70, 200), font=self.font)

        if speech_text:
            self._draw_bubble(draw, speech_text)

        return image

    def _body_color(self, state: str) -> tuple:
        if state == "happy":
            return (255, 205, 111, 255)
        if state == "angry":
            return (238, 112, 92, 255)
        if state == "sleep":
            return (190, 204, 232, 255)
        if state == "walk":
            return (151, 215, 181, 255)
        if state == "talk":
            return (255, 185, 198, 255)
        return (246, 196, 132, 255)

    def _draw_face(self, draw: ImageDraw.ImageDraw, frame: PetFrame, cx: int, cy: int) -> None:
        if frame.state == "angry":
            draw.line((cx - 32, cy - 30, cx - 15, cy - 20), fill=(40, 40, 40, 255), width=4)
            draw.line((cx + 15, cy - 20, cx + 32, cy - 30), fill=(40, 40, 40, 255), width=4)
            draw.ellipse((cx - 30, cy - 21, cx - 16, cy - 7), fill=(30, 30, 35, 255))
            draw.ellipse((cx + 16, cy - 21, cx + 30, cy - 7), fill=(30, 30, 35, 255))
        elif frame.eye_closed:
            draw.arc((cx - 31, cy - 20, cx - 13, cy - 4), 0, 180, fill=(40, 40, 40, 255), width=3)
            draw.arc((cx + 13, cy - 20, cx + 31, cy - 4), 0, 180, fill=(40, 40, 40, 255), width=3)
        else:
            draw.ellipse((cx - 30, cy - 25, cx - 16, cy - 9), fill=(30, 30, 35, 255))
            draw.ellipse((cx + 16, cy - 25, cx + 30, cy - 9), fill=(30, 30, 35, 255))

        if frame.mouth_open:
            draw.ellipse((cx - 8, cy + 4, cx + 8, cy + 20), fill=(90, 45, 55, 255))
        elif frame.state == "happy":
            draw.arc((cx - 12, cy, cx + 12, cy + 18), 0, 180, fill=(90, 45, 55, 255), width=3)
        elif frame.state == "angry":
            draw.arc((cx - 12, cy + 8, cx + 12, cy + 26), 180, 360, fill=(90, 45, 55, 255), width=3)
        else:
            draw.line((cx - 8, cy + 10, cx + 8, cy + 10), fill=(90, 45, 55, 255), width=3)

    def _draw_feet(self, draw: ImageDraw.ImageDraw, frame: PetFrame, cx: int, cy: int) -> None:
        offset = 4 if frame.state == "walk" and frame.walk_dx > 0 else 0
        draw.ellipse((cx - 36 - offset, cy + 35, cx - 8 - offset, cy + 52), fill=(88, 92, 84, 255))
        draw.ellipse((cx + 8 + offset, cy + 35, cx + 36 + offset, cy + 52), fill=(88, 92, 84, 255))

    def _draw_bubble(self, draw: ImageDraw.ImageDraw, text: str) -> None:
        clean_text = text[:18]
        draw.rounded_rectangle(
            (18, 14, 202, 58),
            radius=12,
            fill=(255, 255, 255, 235),
            outline=(65, 65, 70, 230),
            width=2,
        )
        draw.text((30, 28), clean_text, fill=(35, 35, 40, 255), font=self.font)

    def _load_font(self) -> ImageFont.ImageFont:
        candidates = [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
        for path in candidates:
            if path.exists():
                return ImageFont.truetype(str(path), 14)
        return ImageFont.load_default()
