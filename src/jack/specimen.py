"""Render editable, three-times-resolution specimens directly from the built fonts."""

import tomllib
from functools import lru_cache

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from .paths import CONFIG, DIST

SCALE = 3
INK = "#20262a"
MUTED = "#486263"
PAPER = "#fcfbf7"


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
        path = path or DIST / f"Back-{style}.ttf"
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
            fill="#cbd3cd",
            width=SCALE,
        )

    def save(self, name):
        self.image.save(DIST / name, dpi=(216, 216))


def specimen():
    page = Sheet(960, 920)
    page.text(32, 15, "Back", 52, "Bold")
    page.text(32, 87, "和欧混植とプログラミングの書体見本", 18, color=MUTED)
    page.rule(126)
    for i, (style, line) in enumerate(
        [
            ("Italic", "# 議事録から、状態ごとの件数を集計する"),
            ("Regular", "def summarize(records: list[str]) -> dict[str, int]:"),
            ("Regular", '    counts = {"完了": 0, "保留": 0}'),
            ("Regular", "    for status in records:"),
            ("Regular", "        counts[status] += 1"),
            ("Regular", "    return counts"),
        ]
    ):
        page.text(32, 143 + i * 28, line, 21, style, MUTED if i == 0 else INK)
    page.rule(324)
    rows = [
        ("欧文・数字", "Aa Bb Cc Dd Ee Ff Gg Qq Rr Ss Ww Xx Yy Zz   0123456789"),
        ("識別・演算子", "0O０  1lI|  2Z  5S  8B  rn/m   != <= >= => -> :: && ||"),
        ("ひらがな", "あいうえお　さしすせそ　ぬねの めれわ　がぎぐげご ぱぴぷぺぽ"),
        ("カタカナ", "シツ ソン ノメ ロコ　ヴァイオリン・キャッシュ　ｱｲｳｴｵ ｶﾞ ﾊﾟ"),
        ("漢字", "口日田目　永東国語　議事録・認証・鍵管理　高橋と髙橋"),
        ("約物・全角", "「読点、句点。」『引用』【注記】（全角）［配列］ ＡＢＣ１２３"),
        ("記号・数式", "α β γ Δ Ω   ± × ÷ ≠ ≈ ∞   ← ↑ → ↓   {} [] () # @ % &"),
    ]
    for i, (label, line) in enumerate(rows):
        y = 340 + i * 40
        page.text(32, y + 3, label, 13, color=MUTED)
        page.text(167, y, line, 20)
    page.rule(626)
    for i, style in enumerate(("Regular", "Italic", "Bold", "BoldItalic")):
        y = 642 + i * 36
        page.text(32, y + 2, style.replace("BoldItalic", "Bold Italic"), 15, style, MUTED)
        page.text(167, y, "if (値 >= 10) return 配列[i];  // 読み込み完了", 21, style)
    page.rule(800)
    cfg = tomllib.loads(CONFIG.read_text())
    page.text(32, 818, "zero OFF", 15, color=MUTED)
    page.text(167, 812, "0 O ０  0x0F", 23, features=["-zero"])
    page.text(480, 818, "zero ON", 15, color=MUTED)
    page.text(609, 812, "0 O ０  0x0F", 23, features=["zero"])
    page.text(32, 865, "空白・アイコン", 14, color=MUTED)
    page.text(167, 859, "日　本  |  日  本", 21)
    if cfg.get("nerd_icons"):
        page.text(480, 859, " main    src    code", 21)
    page.save("specimen.png")


def compare(original, style="Regular"):
    if style not in ("Regular", "Italic", "Bold", "BoldItalic"):
        raise ValueError(style)
    sheet = Sheet(1120, 556)
    sheet.text(32, 17, style.replace("BoldItalic", "Bold Italic"), 34, "Bold")
    sheet.text(32, 74, "+0" if style == "Italic" else "調整前", 19, color=MUTED)
    sheet.text(574, 74, "+8" if style == "Italic" else "調整後", 19, color=MUTED)
    for i, size in enumerate((14, 16, 20)):
        top = 111 + i * 144
        sheet.rule(top)
        for x, source in ((32, original), (574, DIST / f"Back-{style}.ttf")):
            sheet.text(x, top + 8, f"{size} px", 13, color=MUTED)
            lines = (
                "return 値; // 議事録と鍵の照合",
                "口日田目　永東国語　認識・警報",
                "ぬねめわ がぱ　シツソン　０0O 1Il",
            )
            if style == "Italic":
                lines = (
                    "// 議事録を読み込む",
                    "// かな・カナを照合し、結果を返す",
                    "// if (鍵 != 0) 再試行する",
                )
            for j, line in enumerate(lines):
                sheet.text(x, top + 31 + j * 31, line, size, path=source)
    sheet.save("weight.png" if style == "Regular" else f"weight-{style}.png")
