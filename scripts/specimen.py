"""Render editable, three-times-resolution specimens directly from the built fonts."""

import re
from functools import lru_cache

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from jack.build import FILE_PREFIX
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
        path = path or DIST / f"{FILE_PREFIX}-{style}.ttf"
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
    "吾輩はCatである。Nameはまだない。どこでBornしたかとんとMemoryにない。"
    "何でも薄暗いPlaceでニャーニャーCryしていたことだけはRememberしている。"
    "吾輩はここで初めてHumanなるものをSeeした。"
    "しかもあとでHearすると、それは書生というHumanの中で一番DangerousなSpeciesであったそうだ。"
    "書生というのは時々我々をCatchしてBoilしてEatするというStoryである。"
    "まったくWhat a terrible Worldであろう。"
)


def specimen():
    page = Sheet(960, 820)
    page.text(32, 15, "Sotiak Mono", 52, "Bold")
    page.rule(97)
    font = face(DIST / f"{FILE_PREFIX}-Regular.ttf", 21)
    cell = font.getlength("0")
    columns = int(896 * SCALE // cell)
    lines = [""]
    # Keep Latin words whole; Japanese can break between characters.
    for token in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*\s*|.", BODY):
        if lines[-1] and round(font.getlength(lines[-1] + token) / cell) > columns:
            lines.append("")
            token = token.lstrip()
        lines[-1] += token
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
    page.text(32, y, "Sotiak Mono OpenType Features", 24, "Bold")
    y += 44
    page.text(32, y, "setting", 15, color=MUTED)
    page.text(150, y, "effect", 15, color=MUTED)
    page.text(520, y, "default", 15, color=MUTED)
    page.text(720, y, "changed", 15, color=MUTED)
    y += 26
    features = (
        ("calt", "余白を調整する", "filming im ml", ["calt"], ["-calt"], "Regular"),
        ("ss01", "0xProtoスクリプト体", "fklrsoO", ["-ss01"], ["ss01"], "Italic"),
        ("ss19", "合字を有効にする", "-> <- == != ||", ["-ss19"], ["ss19"], "Regular"),
        ("ss20", "全角スペースを非表示にする", "日　本", ["-ss20"], ["ss20"], "Regular"),
    )
    for i, (tag, effect, sample, default_features, changed_features, style) in enumerate(features):
        row = y + i * 64
        page.rule(row)
        page.text(32, row + 16, tag, 20, "Bold")
        page.text(150, row + 20, effect, 16, color=MUTED)
        page.text(500, row + 13, sample, 24, style, features=default_features)
        page.text(720, row + 13, sample, 24, style, color="#0f766e", features=changed_features)
    page.save("specimen.png")


if __name__ == "__main__":
    specimen()
