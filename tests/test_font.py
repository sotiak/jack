"""Integration tests on the four serialized faces; also write the mixed-text specimen."""

import tomllib
import unicodedata
import unittest

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from jack.build import FAMILY, INPUT, STYLES, font_revision, project_version, source_paths
from jack.paths import CONFIG, DIST
from jack.specimen import specimen as render_specimen

CFG = tomllib.loads(CONFIG.read_text())
VERSION = project_version()
ROWS = [
    ("const 合計 = 配列[0] + 42;", 26),
    ("if (値 != 0) { return 値; }", 27),
    ("|AB|CD|EF|GH|", 13),
    ("|日　本|日  本|", 15),
    ("|Ａ|ｶﾅ|09|。|", 13),
]


def render(style, image, y):
    raster = ImageFont.truetype(DIST / f"Jack-{style}.ttf", 32, layout_engine=ImageFont.Layout.RAQM)
    draw = ImageDraw.Draw(image)
    draw.text((26, y), style.replace("BoldItalic", "Bold Italic"), font=raster, fill="#366070")
    cell = raster.getlength("0")
    for row, (line, cells) in enumerate(ROWS):
        top = y + 52 + row * 48
        for i in range(cells + 1):
            x = round(26 + i * cell)
            draw.line((x, top, x, top + 40), fill="#dce5e6")
        draw.text((26, top + 30), line, font=raster, fill="#15232b", anchor="ls")
    return raster


class FontTests(unittest.TestCase):
    def test_sources_layout_and_tables(self):
        for style, weight in STYLES.items():
            with (
                self.subTest(style=style),
                TTFont(INPUT / f"Hack-{style}.ttf") as base,
                TTFont(DIST / f"Jack-{style}.ttf", checkChecksums=2) as out,
            ):
                out.ensureDecompiled()
                order = out.getGlyphOrder()
                self.assertEqual(order[: len(base.getGlyphOrder())], base.getGlyphOrder())
                self.assertEqual(len(order), out["maxp"].numGlyphs)
                self.assertEqual(set(order), set(out["hmtx"].metrics))
                self.assertEqual(out["head"].unitsPerEm, base["head"].unitsPerEm)
                for tag in ("GSUB", "GPOS", "GDEF", "prep", "cvt ", "fpgm", "gasp"):
                    self.assertEqual(tag in out, tag in base)
                    if tag == "GSUB" and "zero.slash" in order:
                        table = out[tag].table
                        feature = table.FeatureList.FeatureRecord.pop()
                        self.assertEqual(feature.FeatureTag, "zero")
                        table.FeatureList.FeatureCount -= 1
                        lookup = table.LookupList.Lookup.pop()
                        self.assertEqual(
                            lookup.SubTable[0].mapping, {base.getBestCmap()[48]: "zero.slash"}
                        )
                        table.LookupList.LookupCount -= 1
                        for record in table.ScriptList.ScriptRecord:
                            script = record.Script
                            for lang in [script.DefaultLangSys] + [
                                r.LangSys for r in script.LangSysRecord
                            ]:
                                self.assertEqual(
                                    lang.FeatureIndex.pop(), table.FeatureList.FeatureCount
                                )
                                lang.FeatureCount -= 1
                        self.assertEqual(out[tag].compile(out), base[tag].compile(base))
                        continue
                    if tag in base:
                        self.assertEqual(base.reader[tag], out.reader[tag], tag)
                if CFG.get("zero_style") == "feature":
                    ends = out["glyf"]["zero.slash"].endPtsOfContours
                    self.assertEqual(ends[2] - ends[1], 4)  # A slash quad, not the dot.
                slash = CFG.get("zero_style") == "slash"
                for n in base.getGlyphOrder():
                    self.assertEqual(base["hmtx"][n], out["hmtx"][n], n)
                    compare = (
                        self.assertNotEqual
                        if slash and n == base.getBestCmap()[48]
                        else self.assertEqual
                    )
                    compare(
                        base["glyf"][n].compile(base["glyf"]),
                        out["glyf"][n].compile(out["glyf"]),
                        n,
                    )
                cmap = out.getBestCmap()
                donor_points = set()
                for path in source_paths(style):
                    with TTFont(path) as donor:
                        donor_points.update(donor.getBestCmap())
                if CFG.get("nerd_icons"):
                    with TTFont(INPUT / "NerdSymbols.ttf") as donor:
                        for cp, n in donor.getBestCmap().items():
                            if (
                                unicodedata.category(chr(cp)) == "Co"
                                and donor["glyf"][n].numberOfContours
                            ):
                                donor_points.add(cp)
                                self.assertEqual(out["hmtx"][cmap[cp]][0], 1233)
                                if cmap[cp].startswith("nerd"):
                                    g = out["glyf"][cmap[cp]]
                                    self.assertGreaterEqual(g.xMin, 0)
                                    self.assertLessEqual(g.xMax, 1233)
                self.assertEqual(set(cmap), donor_points | set(base.getBestCmap()))
                for cp, name in base.getBestCmap().items():
                    if cp not in (0x25FD, 0x25FE):
                        self.assertEqual(cmap[cp], name, hex(cp))
                for table in out["cmap"].tables:
                    if table.format == 14:
                        for pairs in table.uvsDict.values():
                            for cp, name in pairs:
                                self.assertIn(cp, cmap)
                                if name:
                                    self.assertIn(name, out["hmtx"].metrics)
                                    self.assertEqual(out["hmtx"][name][0], out["hmtx"][cmap[cp]][0])
                    else:
                        self.assertEqual(
                            table.cmap,
                            {cp: n for cp, n in cmap.items() if table.format == 12 or cp <= 0xFFFF},
                        )
                names = out["name"]
                self.assertEqual(names.getDebugName(1), FAMILY)
                self.assertEqual(names.getDebugName(2), base["name"].getDebugName(2))
                self.assertEqual(names.getDebugName(3), f"{VERSION};Jack-{style}")
                self.assertEqual(names.getDebugName(5), f"Version {VERSION}")
                self.assertEqual(names.getDebugName(6), f"Jack-{style}")
                self.assertAlmostEqual(
                    out["head"].fontRevision, font_revision(VERSION), delta=0.5 / 65536
                )
                self.assertEqual(out["OS/2"].usWeightClass, weight)
                self.assertEqual(bool(out["head"].macStyle & 1), weight == 700)
                self.assertEqual(bool(out["OS/2"].fsSelection & 32), weight == 700)
                self.assertEqual(out["head"].macStyle, base["head"].macStyle)
                self.assertEqual(out["OS/2"].fsSelection, base["OS/2"].fsSelection)
                self.assertEqual(out["post"].italicAngle, base["post"].italicAngle)
                half = base["hmtx"][base.getBestCmap()[32]][0]
                for cp, n in cmap.items():
                    width = out["hmtx"][n][0]
                    self.assertIn(width, (0, half, half * 2), hex(cp))
                    if width and unicodedata.east_asian_width(chr(cp)) in {"W", "F"}:
                        self.assertEqual(width, 2 * half, hex(cp))
                for ch in "ｱｶﾅ ABC09!=":
                    self.assertEqual(out["hmtx"][cmap[ord(ch)]][0], half)
                for ch in "漢字あア、。「」Ａ０　":
                    self.assertEqual(out["hmtx"][cmap[ord(ch)]][0], 2 * half)

    def test_japanese_italic(self):
        for style, roman in (("Italic", "Regular"), ("BoldItalic", "Bold")):
            with (
                TTFont(DIST / f"Jack-{style}.ttf") as italic,
                TTFont(DIST / f"Jack-{roman}.ttf") as upright,
            ):
                for ch in "日あカ。、ｱ":
                    a = italic["glyf"][italic.getBestCmap()[ord(ch)]]
                    b = upright["glyf"][upright.getBestCmap()[ord(ch)]]
                    if CFG.get("japanese_italic_degrees", 8) >= 1:
                        self.assertNotEqual(a.coordinates, b.coordinates, ch)
                        self.assertGreaterEqual(a.xMin, 0)
                        self.assertLessEqual(
                            a.xMax, italic["hmtx"][italic.getBestCmap()[ord(ch)]][0]
                        )
                    elif CFG.get("japanese_italic_degrees", 8) == 0 and (
                        style == "BoldItalic"
                        or CFG.get("japanese_italic_strength", 0)
                        == CFG.get("japanese_regular_strength", 0)
                    ):
                        self.assertEqual(a.coordinates, b.coordinates, ch)

    def test_render(self):
        sheet = Image.new("RGB", (660, 311 * len(STYLES) + 10), "#fafcfb")
        for i, style in enumerate(STYLES):
            raster = render(style, sheet, 12 + i * 311)
            visible = CFG.get("visible_fullwidth_space", False)
            self.assertEqual(bool(raster.getmask("　").getbbox()), visible)
            if visible:
                with TTFont(DIST / f"Jack-{style}.ttf") as face:
                    marker = face["glyf"][face.getBestCmap()[0x3000]]
                    self.assertEqual(marker.numberOfContours, 8)
                    self.assertEqual(marker.xMin + marker.xMax, 2466)
            self.assertIsNone(raster.getmask(" ").getbbox())
            self.assertEqual(raster.getlength("　"), raster.getlength("  "))
            original = ImageFont.truetype(INPUT / f"Hack-{style}.ttf", 32)
            for line, cells in ROWS:
                self.assertAlmostEqual(
                    raster.getlength(line), raster.getlength("0") * cells, delta=0.25
                )
            for line in ("Il1|O {} [] => != <=>", "123456789"):
                self.assertEqual(bytes(raster.getmask(line)), bytes(original.getmask(line)))
            self.assertEqual(raster.getlength("0"), original.getlength("0"))
            slash = CFG.get("zero_style") == "slash"
            self.assertEqual(bytes(raster.getmask("0")) != bytes(original.getmask("0")), slash)
            if CFG.get("zero_style") == "feature":

                def mask(text, setting, raster=raster):
                    return bytes(raster.getmask(text, features=[setting]))

                self.assertNotEqual(mask("0", "zero"), mask("0", "-zero"))
                self.assertEqual(mask("0", "-zero"), bytes(original.getmask("0")))
                self.assertEqual(mask("O０", "zero"), mask("O０", "-zero"))
                self.assertEqual(raster.getlength("0", features=["zero"]), original.getlength("0"))
            if CFG.get("nerd_icons"):
                sample = "    󰀄 日本語"
                self.assertAlmostEqual(
                    raster.getlength(sample), raster.getlength("0") * 16, delta=0.25
                )
                self.assertTrue(all(raster.getmask(ch).getbbox() for ch in sample if ch != " "))
                ImageDraw.Draw(sheet).text((200, 12 + i * 311), sample, font=raster, fill="#15232b")
            for line in ("日本語", "ｶﾅ", "Ａ０"):
                self.assertTrue(raster.getmask(line).getbbox())
        sheet.save(DIST / "mixed.png")

        specimen = Image.new("RGB", (820, 212), "#fafcfb")
        draw = ImageDraw.Draw(specimen)
        for row, style in enumerate(("Regular", "Italic", "Bold", "BoldItalic")):
            font = ImageFont.truetype(DIST / f"Jack-{style}.ttf", 26)
            top = 12 + row * 50
            draw.text(
                (18, top), style.replace("BoldItalic", "Bold Italic"), font=font, fill="#366070"
            )
            draw.text((210, top), "off  0x0F", font=font, features=["-zero"], fill="#15232b")
            draw.text((420, top), "on  0x0F", font=font, features=["zero"], fill="#15232b")
        specimen.save(DIST / "styles.png")
        render_specimen()


if __name__ == "__main__":
    unittest.main()
