"""Render editable, three-times-resolution specimens directly from the built fonts."""

from functools import lru_cache

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from jack.paths import DIST, IMAGES

SCALE = 3
INK = "#202026"
MUTED = "#73737e"
PAPER = "#ffffff"


@lru_cache(maxsize=128)
def face(path, size):
    return ImageFont.truetype(path, size * SCALE, layout_engine=ImageFont.Layout.RAQM)


@lru_cache(maxsize=12)
def coverage(path):
    with TTFont(path) as font:
        return set(font.getBestCmap())


class Sheet:
    def __init__(self, width, height):
        self.image = Image.new("RGB", (width * SCALE, height * SCALE), PAPER)
        self.draw = ImageDraw.Draw(self.image)

    def text(self, x, y, text, size, style="Regular", color=INK, path=None, features=None):
        path = path or DIST / f"Jack-{style}.ttf"
        missing = {ch for ch in text if ord(ch) not in coverage(path)}
        if missing:
            raise ValueError(f"{path.name}: missing {missing}")
        font = face(path, size)
        origin = (x * SCALE, y * SCALE)
        bounds = self.draw.textbbox(origin, text, font=font, anchor="la", features=features)
        if (
            bounds[0] < 0
            or bounds[1] < 0
            or bounds[2] > self.image.width
            or bounds[3] > self.image.height
        ):
            raise ValueError(f"Text exceeds page: {text}")
        self.draw.text(origin, text, font=font, anchor="la", fill=color, features=features)

    def rule(self, y):
        self.draw.line(
            (32 * SCALE, y * SCALE, self.image.width - 32 * SCALE, y * SCALE),
            fill="#e8e8ed",
            width=SCALE,
        )

    def save(self, name):
        IMAGES.mkdir(parents=True, exist_ok=True)
        self.image.save(IMAGES / name, dpi=(216, 216))


BODY = (
    "Sherlock Holmesにとって、彼女はいつでも“the woman”だった。"
    "彼が彼女を別の名前で呼ぶのを、私はほとんど聞いたことがない。"
    "彼の目には、Irene Adlerという女性が、ほかのすべての女性を霞ませていた。"
    "しかし、それはloveに似た感情を抱いていたからではない。"
    "冷静で精緻な、そして見事に均衡の取れた彼の精神は、そのような感情を何よりも嫌っていた。"
)


def specimen():
    page = Sheet(960, 660)
    page.text(32, 15, "Jack", 52, "Bold")
    page.rule(97)
    font = face(DIST / "Jack-Regular.ttf", 21)
    cell = font.getlength("0")
    columns = int(896 * SCALE // cell)
    lines = [""]
    for ch in BODY:
        if round(font.getlength(lines[-1] + ch) / cell) > columns:
            lines.append("")
        lines[-1] += ch
    top = 115
    for i in range(columns + 1):
        x = 32 * SCALE + i * cell
        page.draw.line(
            (x, top * SCALE, x, (top + len(lines) * 30) * SCALE), fill="#e8e8ed", width=SCALE
        )
    for i, line in enumerate(lines):
        page.text(32, top + i * 30, line, 21)
    y = top + len(lines) * 30 + 8
    page.rule(y)
    y += 16
    for i, style in enumerate(("Regular", "Italic", "Bold", "BoldItalic")):
        row = y + i * 36
        page.text(32, row + 2, style.replace("BoldItalic", "Bold Italic"), 15, style, MUTED)
        page.text(167, row, "if (値 >= 10) return 配列[i];  // 読み込み完了", 21, style)
    y += 4 * 36 + 8
    page.rule(y)
    y += 16
    page.text(32, y, "Jack OpenType Features", 24, "Bold")
    y += 44
    page.text(32, y, "features", 15, color=MUTED)
    page.text(400, y, "default", 15, color=MUTED)
    page.text(660, y, "active", 15, color=MUTED)
    y += 26
    for i, (tag, sample) in enumerate((("zero", "0 O ０  0x0F"), ("ss20", "日　本"))):
        row = y + i * 64
        page.rule(row)
        page.text(32, row + 16, tag, 20, "Bold")
        page.text(400, row + 13, sample, 23, features=[f"-{tag}"])
        page.text(660, row + 13, sample, 23, color="#5e6ad2", features=[tag])
    page.save("specimen.png")


if __name__ == "__main__":
    specimen()
