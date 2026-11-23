"""Build the single-page specimen with subset webfonts."""

import html
import shutil
import string
from html.parser import HTMLParser

from fontTools import subset
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from mono.build import FILE_PREFIX, project_version
from mono.paths import DIST, INPUT, LICENSE, LICENSES, PROJECT_ROOT

SITE = DIST / "site"
STYLES = {
    "Regular": (400, "normal"),
    "Italic": (400, "italic"),
    "Bold": (700, "normal"),
    "BoldItalic": (700, "italic"),
}
DESIGNS = ["r", "g", "j", "Ww", "t", "M"]
COMPARE_SAMPLE = """fun main() {
  val s = "agijr WwtM 0O 1Il"
  val ok = s.length > 8
  if (ok) print(s) else println(s)
}"""
CHARACTERS = {
    "Basic latin": string.ascii_uppercase + "\n" + string.ascii_lowercase,
    "数字・記号": string.digits + string.punctuation,
    "ひらがな・カタカナ": "".join(chr(cp) for cp in range(0x3041, 0x3097))
    + "".join(chr(cp) for cp in range(0x30A1, 0x30FB)),
    "漢字": "日本語文字書体等幅大小上下左右天地山川海空雨雪風花鳥月火水木金土人男女子年月日時分秒春夏秋冬東西南北学校会社仕事生活読書文章数字記号開発設計実装試験生成表示入力出力保存変更設定有効無効全角半角太字斜体余白調整比較関数配列条件結果",
    "記号・罫線": "←↑→↓↔↕⇒⇐∀∃∅∆∇∈∉∑−√∞∧∨∩∪≈≠≡≤≥⌘⌥⌫─│┌┐└┘├┤┬┴┼━┃┏┓┗┛┣┫┳┻╋╭╮╯╰░▒▓█■□▲△●○◆◇「」『』【】〈〉《》、。・！？",
    "Nerd Fonts": "".join(chr(cp) for cp in range(0xF000, 0xF028)),
}
CHARACTER_WIDTHS = {
    "Basic latin": 1,
    "数字・記号": 1,
    "ひらがな・カタカナ": 2,
    "漢字": 2,
    "Nerd Fonts": 1,
}


class TextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ignore = 0
        self.characters = set()

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignore += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignore -= 1

    def handle_data(self, data):
        if not self.ignore:
            self.characters.update(data)


def design_svg(font, text, variant, *, highlight_bar=False, label_guides=False):
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    paths = []
    x = 0
    for char in text:
        pen = SVGPathPen(glyphs)
        glyphs[cmap[ord(char)]].draw(pen)
        paths.append(f'<path transform="translate({x},0)" d="{pen.getCommands()}"/>')
        x += font["hmtx"][cmap[ord(char)]][0]

    upm = font["head"].unitsPerEm
    top, bottom = -upm, int(upm * 0.3)
    left = -100
    right = x + 200
    hhea, os2 = font["hhea"], font["OS/2"]
    highlight = ""
    if highlight_bar:
        highlight = (
            f'<rect class="bar-band" x="{left}" y="{-os2.sxHeight}" '
            f'width="{right - left}" height="{round(upm * 0.073)}" '
            'fill="currentColor" opacity=".18"/>'
            f'<line class="bar-band" x1="{left}" y1="{-os2.sxHeight}" '
            f'x2="{right}" y2="{-os2.sxHeight}" stroke="currentColor" '
            'stroke-width="10" opacity=".65"/>'
        )
    labels = ""
    if label_guides:
        spans = []
        for key, y, name in (
            ("asc", hhea.ascender, "ASC"),
            ("cap", os2.sCapHeight, "CAP"),
            ("x", os2.sxHeight, "X-HEIGHT"),
            ("base", 0, "BASE"),
            ("desc", hhea.descender, "DESC"),
        ):
            percent = ((-y) - top) / (bottom - top) * 100
            spans.append(
                f'<span class="{key}" style="top:{percent:.2f}%">{name} <b>{abs(y)}</b></span>'
            )
        labels = f'<div class="plan-labels">{"".join(spans)}</div>'
    guides = (
        (hhea.ascender, "8 16", ".35", 10),
        (os2.sCapHeight, "18 12", ".5", 10),
        (os2.sxHeight, "36 18", ".7", 10),
        (0, "", ".85", 12),
        (hhea.descender, "8 16", ".35", 10),
    )
    metrics = "".join(
        f'<line x1="{left}" y1="{-y}" x2="{right}" y2="{-y}" '
        f'stroke-width="{stroke}" stroke-dasharray="{dash}" stroke-opacity="{opacity}"/>'
        for y, dash, opacity, stroke in guides
    )
    view = f"{left} {top} {right - left} {bottom - top}"
    return (
        f'<div class="plan-frame plan-{variant}">'
        f'<svg class="plan-guides" viewBox="{view}" preserveAspectRatio="none" '
        f'aria-hidden="true" focusable="false">'
        f'<g fill="none" stroke="currentColor">{metrics}</g></svg>'
        f'<svg class="plan-glyph" viewBox="{view}" role="img" '
        f'aria-label="{html.escape(text)}の輪郭とメトリクス（{variant}）">'
        f"{highlight}"
        f'<g transform="scale(1,-1)" fill="currentColor">{"".join(paths)}</g></svg>'
        f"{labels}</div>"
    )


def render_design(font, italic_font):
    cards = []
    for text in DESIGNS:
        views = "".join(
            design_svg(face, text, variant)
            for face, variant in ((font, "roman"), (italic_font, "italic"))
        )
        cards.append(f'<article class="design-card">{views}</article>')
    return "\n".join(cards)


def render_alignment(font, italic_font):
    return "".join(
        design_svg(face, "ftij", variant, highlight_bar=True, label_guides=True)
        for face, variant in ((font, "roman"), (italic_font, "italic"))
    )


def subset_font(source, destination, characters, *, comparison=False):
    with TTFont(source) as font:
        available = set(font.getBestCmap())
        missing = {ord(c) for c in characters if not c.isspace()} - available
        if missing and not comparison:
            raise ValueError(f"{source.name}: missing {sorted(missing)}")
        options = subset.Options()
        options.layout_features = ["calt", "ss01", "ss19", "ss20"]
        options.recalc_timestamp = False
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes={ord(c) for c in characters} & available)
        subsetter.subset(font)
        font.flavor = "woff2"
        font.save(destination)


def build_site():
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "fonts").mkdir(exist_ok=True)
    template = (PROJECT_ROOT / "site/index.html").read_text()
    with (
        TTFont(DIST / f"{FILE_PREFIX}-Regular.ttf") as font,
        TTFont(DIST / f"{FILE_PREFIX}-Italic.ttf") as italic,
    ):
        cmap = font.getBestCmap()
        groups = []
        for title, text in CHARACTERS.items():
            text = "".join(c for c in text if c.isspace() or ord(c) in cmap)
            width = CHARACTER_WIDTHS.get(title)
            attr = f' data-width="{width}"' if width else ""
            groups.append(
                f'<div class="character-group"{attr}><h3>{title}</h3>'
                f'<p class="characters">{html.escape(text)}</p></div>'
            )
        values = {
            "version": project_version(),
            "half": str(font["hmtx"][cmap[ord("A")]][0]),
            "full": str(font["hmtx"][cmap[ord("日")]][0]),
            "upm": str(font["head"].unitsPerEm),
            "design": render_design(font, italic),
            "alignment": render_alignment(font, italic),
            "compare": html.escape(COMPARE_SAMPLE),
            "characters": "\n".join(groups),
        }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    collector = TextCollector()
    collector.feed(template)
    characters = collector.characters | set(chr(cp) for cp in range(32, 127))
    # Include strings produced by controls, not just the initial HTML.
    characters.update("ライトダークに切替")
    css = []
    for style, (weight, slope) in STYLES.items():
        subset_font(DIST / f"{FILE_PREFIX}-{style}.ttf", SITE / f"fonts/{style}.woff2", characters)
        css.append(
            f'@font-face{{font-family:"Sotiak Mono";src:url("fonts/{style}.woff2") '
            f'format("woff2");font-weight:{weight};font-style:{slope};font-display:swap;}}'
        )
    subset_font(
        INPUT / "Iosevka-Regular.ttf",
        SITE / "fonts/Iosevka.woff2",
        set(COMPARE_SAMPLE),
        comparison=True,
    )
    css.append(
        '@font-face{font-family:"Iosevka SS03";src:url("fonts/Iosevka.woff2") '
        'format("woff2");font-weight:400;font-style:normal;font-display:swap;}'
    )
    (SITE / "fonts.css").write_text("\n".join(css))
    (SITE / "index.html").write_text(template)
    for filename in ("style.css", "site.js"):
        shutil.copyfile(PROJECT_ROOT / "site" / filename, SITE / filename)
    shutil.copytree(LICENSES, SITE / "licenses", dirs_exist_ok=True)
    shutil.copyfile(LICENSE, SITE / "licenses/OFL.txt")
    return SITE


def main():
    from mono.screenshots import render

    build_site()
    render(pdf=True)
    print(f"Built {SITE}")
