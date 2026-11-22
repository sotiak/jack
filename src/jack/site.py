"""Build the single-page specimen with subset webfonts."""

import html
import shutil
from html.parser import HTMLParser

from fontTools import subset
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from jack.build import FILE_PREFIX, project_version
from jack.paths import DIST, INPUT, LICENSE, LICENSES, PROJECT_ROOT

SITE = DIST / "site"
STYLES = {
    "Regular": (400, "normal"),
    "Italic": (400, "italic"),
    "Bold": (700, "normal"),
    "BoldItalic": (700, "italic"),
}
DESIGNS = [
    ("r", "横幅を1.13倍に。"),
    ("g", "シングルストーリー。下部は横に払う形。"),
    ("j", "横棒を長くし、正体の右端を調整。"),
    ("Ww", "側面が丸みを持つ字形。"),
    ("t", "短い首と平らなフック。"),
    ("M", "セリフのない、中央が下がる字形。"),
]
CHARACTERS = {
    "英数字": "".join(chr(cp) for cp in range(33, 127)),
    "ひらがな・カタカナ": "".join(chr(cp) for cp in range(0x3041, 0x3097))
    + "".join(chr(cp) for cp in range(0x30A1, 0x30FB)),
    "漢字": "日本語文字書体等幅大小上下左右天地山川海空雨雪風花鳥月火水木金土人男女子年月日時分秒春夏秋冬東西南北学校会社仕事生活読書文章数字記号開発設計実装試験生成表示入力出力保存変更設定有効無効全角半角太字斜体余白調整比較関数配列条件結果",
    "記号・罫線": "←↑→↓↔↕⇒⇐∀∃∅∆∇∈∉∑−√∞∧∨∩∪≈≠≡≤≥⌘⌥⌫─│┌┐└┘├┤┬┴┼━┃┏┓┗┛┣┫┳┻╋╭╮╯╰░▒▓█■□▲△●○◆◇「」『』【】〈〉《》、。・！？",
    "Nerd Fonts": "".join(chr(cp) for cp in range(0xF000, 0xF028)),
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


def render_design(font):
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    cards = []
    for text, caption in DESIGNS:
        paths = []
        for index, char in enumerate(text):
            pen = SVGPathPen(glyphs)
            glyphs[cmap[ord(char)]].draw(pen)
            paths.append(f'<path transform="translate({index * 650},0)" d="{pen.getCommands()}"/>')
        cards.append(
            f'<article class="design-card"><h3>{html.escape(text)}</h3>'
            f'<svg viewBox="-100 -1000 {max(1000, len(text) * 650)} 1300" '
            f'role="img" aria-label="{html.escape(text)}の輪郭">'
            '<path d="M-100 0H1400 M-100 -700H1400" stroke="currentColor" '
            'stroke-opacity=".15" fill="none" stroke-width="3"/>'
            f'<g transform="scale(1,-1)" fill="currentColor">{"".join(paths)}</g></svg>'
            f"<p>{caption}</p></article>"
        )
    return "\n".join(cards)


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
    with TTFont(DIST / f"{FILE_PREFIX}-Regular.ttf") as font:
        cmap = font.getBestCmap()
        groups = []
        for title, text in CHARACTERS.items():
            text = "".join(c for c in text if ord(c) in cmap)
            groups.append(
                f'<div class="character-group"><h3>{title}</h3>'
                f'<p class="characters">{html.escape(text)}</p></div>'
            )
        values = {
            "version": project_version(),
            "count": f"{len(cmap):,}",
            "half": str(font["hmtx"][cmap[ord("A")]][0]),
            "full": str(font["hmtx"][cmap[ord("日")]][0]),
            "upm": str(font["head"].unitsPerEm),
            "design": render_design(font),
            "characters": "\n".join(groups),
        }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    collector = TextCollector()
    collector.feed(template)
    characters = collector.characters | set(chr(cp) for cp in range(32, 127))
    # Include strings produced by controls, not just the initial HTML.
    characters.update("ライトダークに切替差分を重ねる有効無効")
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
        set("agijr WwtM0O1Il{}[]"),
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
    from jack.screenshots import render

    build_site()
    render(pdf=True)
    print(f"Built {SITE}")
