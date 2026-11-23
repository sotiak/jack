"""Integration tests on the four serialized faces."""

import tempfile
import tomllib
import unicodedata
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from mono.build import (
    FAMILY,
    FILE_PREFIX,
    INPUT,
    STYLE_LABELS,
    STYLES,
    build_face,
    font_revision,
    normalize_overlap,
    project_version,
    source_paths,
)
from mono.paths import CONFIG, DIST

CFG = tomllib.loads(CONFIG.read_text())
JP = CFG["japanese"]
GLYPHS = CFG["glyphs"]
VERSION = project_version()
ROWS = [
    ("const 合計 = 配列[0] + 42;", 26),
    ("if (値 != 0) { return 値; }", 27),
    ("|AB|CD|EF|GH|", 13),
    ("|日　本|日  本|", 15),
    ("|Ａ|ｶﾅ|09|。|", 13),
]


def render(style, image, y):
    raster = ImageFont.truetype(
        DIST / f"{FILE_PREFIX}-{style}.ttf", 32, layout_engine=ImageFont.Layout.RAQM
    )
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


def feature(font, tag):
    for record in font["GSUB"].table.FeatureList.FeatureRecord:
        if record.FeatureTag == tag:
            return record.Feature
    return None


def substitution(font, tag):
    record = feature(font, tag)
    assert record is not None and record.LookupListIndex
    lookup = font["GSUB"].table.LookupList.Lookup[record.LookupListIndex[0]]
    return lookup.SubTable[0].mapping


class FontTests(unittest.TestCase):
    def test_sources_layout_and_tables(self):
        for style, weight in STYLES.items():
            with (
                self.subTest(style=style),
                TTFont(INPUT / f"Iosevka-{style}.ttf") as base,
                TTFont(DIST / f"{FILE_PREFIX}-{style}.ttf", checkChecksums=2) as out,
            ):
                out.ensureDecompiled()
                order = out.getGlyphOrder()
                base_order = base.getGlyphOrder()
                base_cmap = base.getBestCmap()
                half = base["hmtx"][base_cmap[32]][0]
                self.assertEqual(order[: len(base_order)], base_order)
                self.assertEqual(len(order), out["maxp"].numGlyphs)
                self.assertEqual(set(order), set(out["hmtx"].metrics))
                self.assertEqual(out["head"].unitsPerEm, base["head"].unitsPerEm)
                for tag in ("GPOS", "GDEF", "prep", "cvt ", "fpgm", "gasp"):
                    self.assertEqual(tag in out, tag in base, tag)
                    if tag in base:
                        self.assertEqual(base.reader[tag], out.reader[tag], tag)

                base_table = base["GSUB"].table
                out_table = out["GSUB"].table
                base_tags = {record.FeatureTag for record in base_table.FeatureList.FeatureRecord}
                out_tags = {record.FeatureTag for record in out_table.FeatureList.FeatureRecord}
                expected_tags = base_tags | {"ss19", "ss20"}
                if style in ("Italic", "BoldItalic"):
                    expected_tags.add("ss01")
                self.assertEqual(out_tags, expected_tags)
                self.assertGreater(feature(out, "calt").LookupCount, 0)
                self.assertEqual(feature(out, "ss19").LookupCount, 1)
                self.assertNotEqual(feature(out, "ss19").LookupListIndex, [])
                if style in ("Italic", "BoldItalic"):
                    script = {out.getBestCmap()[ord(char)]: f"{char}.ss01" for char in "fklrsoO"}
                    self.assertEqual(substitution(out, "ss01"), script)
                    for char in "fklrsoO":
                        name = f"{char}.ss01"
                        self.assertIn(name, order)
                        self.assertEqual(out["hmtx"][name][0], half)
                        glyph = out["glyf"][name]
                        self.assertGreaterEqual(glyph.xMin, 0)
                        self.assertLessEqual(glyph.xMax, half)
                else:
                    self.assertIsNone(feature(out, "ss01"))
                ss19 = out_table.LookupList.Lookup[feature(out, "ss19").LookupListIndex[0]]
                self.assertEqual(ss19.LookupType, 4)
                for sequence in ("->", "<-", "=>", "==", "!=", "::", "||", "&&", "<=>"):
                    names = [out.getBestCmap()[ord(char)] for char in sequence]
                    ligature = next(
                        lig
                        for table in ss19.SubTable
                        for lig in table.ligatures.get(names[0], [])
                        if [names[0], *lig.Component] == names
                    )
                    self.assertEqual(ligature.LigGlyph, "lig." + "_".join(names))
                    lig = out["glyf"][ligature.LigGlyph]
                    self.assertEqual(out["hmtx"][ligature.LigGlyph][0], half * len(sequence))
                    self.assertGreaterEqual(lig.xMin, 0)
                    self.assertLessEqual(lig.xMax, half * len(sequence))
                    self.assertEqual(
                        lig.numberOfContours,
                        sum(
                            len(out["glyf"][name].getCoordinates(out["glyf"])[1]) for name in names
                        ),
                    )
                marker = (
                    "ideographicSpaceBlank"
                    if GLYPHS.get("visible_fullwidth_space")
                    else "ideographicSpaceMarker"
                )
                self.assertEqual(substitution(out, "ss20"), {out.getBestCmap()[0x3000]: marker})
                self.assertGreater(
                    len(out_table.LookupList.Lookup), len(base_table.LookupList.Lookup)
                )
                hybrid = {"a", "f", "y", "g"} if style in ("Italic", "BoldItalic") else set()
                single_g = {"g"} if style in ("Regular", "Bold") else set()
                rounded = {"W", "w"}
                flat_t = {"t"}
                wider = {"r"}
                serifs = {"i", "j", "dotlessi", "uni0237"}
                hanging_m = {"M"}
                affected = set(hybrid) | single_g | rounded | flat_t | wider | serifs | hanging_m
                # a/f/y are direct copies in italic and can match the base once
                # their hints are restored; the donor check covers them.
                rebuilt = single_g | rounded | flat_t | wider | serifs | hanging_m
                if hybrid:
                    rebuilt.add("g")
                    with TTFont(INPUT / f"Iosevka-{style}True.ttf") as donor:
                        donor_cmap = donor.getBestCmap()
                        for char in "afy":
                            target = base_cmap[ord(char)]
                            source = donor_cmap[ord(char)]
                            points, ends, _ = donor["glyf"][source].getCoordinates(donor["glyf"])
                            glyph = out["glyf"][target]
                            self.assertEqual(list(glyph.coordinates), list(points), target)
                            self.assertEqual(glyph.endPtsOfContours, list(ends), target)
                            self.assertEqual(out["hmtx"][target], donor["hmtx"][source])
                changed = True
                while changed:
                    changed = False
                    for name in base_order:
                        glyph = base["glyf"][name]
                        if (
                            glyph.numberOfContours < 0
                            and name not in affected
                            and any(c.glyphName in affected for c in glyph.components)
                        ):
                            affected.add(name)
                            changed = True
                for name in base_order:
                    normalize_overlap(base["glyf"][name])
                    normalize_overlap(out["glyf"][name])
                    if name in affected:
                        self.assertEqual(out["hmtx"][name][0], half, name)
                        if name in rebuilt:
                            self.assertNotEqual(
                                base["glyf"][name].compile(base["glyf"]),
                                out["glyf"][name].compile(out["glyf"]),
                                name,
                            )
                    else:
                        self.assertEqual(base["hmtx"][name], out["hmtx"][name], name)
                        self.assertEqual(
                            base["glyf"][name].compile(base["glyf"]),
                            out["glyf"][name].compile(out["glyf"]),
                            name,
                        )

                cmap = out.getBestCmap()
                donor_points = set()
                for path in source_paths(style):
                    with TTFont(path) as donor:
                        donor_points.update(donor.getBestCmap())
                if GLYPHS.get("nerd_icons"):
                    with TTFont(INPUT / "NerdSymbols.ttf") as donor:
                        for cp, name in donor.getBestCmap().items():
                            if (
                                unicodedata.category(chr(cp)) == "Co"
                                and donor["glyf"][name].numberOfContours
                            ):
                                donor_points.add(cp)
                                if cmap[cp].startswith("nerd"):
                                    self.assertEqual(out["hmtx"][cmap[cp]][0], half)
                                    glyph = out["glyf"][cmap[cp]]
                                    self.assertGreaterEqual(glyph.xMin, 0)
                                    self.assertLessEqual(glyph.xMax, half)
                self.assertEqual(set(cmap), donor_points | set(base_cmap))
                widened = {
                    cp
                    for cp, name in base_cmap.items()
                    if unicodedata.east_asian_width(chr(cp)) in {"W", "F"}
                    and base["hmtx"][name][0] == half
                }
                for cp, name in base_cmap.items():
                    self.assertEqual(cmap[cp], f"wide{cp:04X}" if cp in widened else name, hex(cp))
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
                self.assertEqual(names.getDebugName(2), STYLE_LABELS[style])
                self.assertEqual(names.getDebugName(3), f"{VERSION};{FILE_PREFIX}-{style}")
                self.assertEqual(names.getDebugName(5), f"Version {font_revision(VERSION):.4f}")
                self.assertEqual(names.getDebugName(6), f"{FILE_PREFIX}-{style}")
                self.assertAlmostEqual(
                    out["head"].fontRevision, font_revision(VERSION), delta=0.5 / 65536
                )
                self.assertEqual(out["OS/2"].usWeightClass, weight)
                self.assertEqual(bool(out["head"].macStyle & 1), weight == 700)
                self.assertEqual(bool(out["OS/2"].fsSelection & 32), weight == 700)
                self.assertEqual(out["head"].macStyle, base["head"].macStyle)
                self.assertEqual(out["OS/2"].fsSelection, base["OS/2"].fsSelection)
                self.assertEqual(out["post"].italicAngle, base["post"].italicAngle)
                for cp, name in cmap.items():
                    width = out["hmtx"][name][0]
                    self.assertIn(width, (0, half, half * 2), hex(cp))
                    if width and unicodedata.east_asian_width(chr(cp)) in {"W", "F"}:
                        self.assertEqual(width, 2 * half, hex(cp))
                for ch in "ｱｶﾅ ABC09!=":
                    self.assertEqual(out["hmtx"][cmap[ord(ch)]][0], half)
                for ch in "漢字あア、。「」Ａ０　":
                    self.assertEqual(out["hmtx"][cmap[ord(ch)]][0], 2 * half)

    def test_rebuilt_glyphs_keep_hinting(self):
        for style in STYLES:
            with (
                self.subTest(style=style),
                TTFont(INPUT / f"Iosevka-{style}.ttf") as base,
                TTFont(DIST / f"{FILE_PREFIX}-{style}.ttf") as out,
            ):
                hinted = {
                    name
                    for name in base.getGlyphOrder()
                    if base["glyf"][name].numberOfContours > 0
                    and base["glyf"][name].program.getBytecode()
                }
                # Iosevka ships i and j as composites; the build flattens both.
                hinted.update(("i", "j"))
                for name in hinted:
                    glyph = out["glyf"][name]
                    if glyph.numberOfContours > 0:
                        self.assertTrue(glyph.program.getBytecode(), f"{style}: {name}")

    def test_ots_overlap_flag(self):
        for style in STYLES:
            with self.subTest(style=style), TTFont(DIST / f"{FILE_PREFIX}-{style}.ttf") as font:
                for name in font.getGlyphOrder():
                    glyph = font["glyf"][name]
                    if glyph.numberOfContours > 0 and glyph.flags:
                        later = [i for i, flag in enumerate(glyph.flags) if i and flag & 0x40]
                        self.assertEqual(later, [], name)

    def test_family_vertical_metrics(self):
        metrics = {}
        for style in STYLES:
            with TTFont(DIST / f"{FILE_PREFIX}-{style}.ttf") as font:
                os2 = font["OS/2"]
                metrics[style] = (
                    font["hhea"].ascent,
                    font["hhea"].descent,
                    font["hhea"].lineGap,
                    os2.sTypoAscender,
                    os2.sTypoDescender,
                    os2.sTypoLineGap,
                    os2.usWinAscent,
                    os2.usWinDescent,
                )
        self.assertEqual(len(set(metrics.values())), 1, metrics)

    def test_upright_single_storey_g_centered(self):
        for style in ("Regular", "Bold"):
            with self.subTest(style=style), TTFont(DIST / f"{FILE_PREFIX}-{style}.ttf") as font:
                name = font.getBestCmap()[ord("g")]
                glyph = font["glyf"][name]
                advance = font["hmtx"][name][0]
                self.assertAlmostEqual((glyph.xMin + glyph.xMax) / 2, advance / 2, delta=1)

    def test_japanese_italic(self):
        for style, roman in (("Italic", "Regular"), ("BoldItalic", "Bold")):
            with (
                TTFont(DIST / f"{FILE_PREFIX}-{style}.ttf") as italic,
                TTFont(DIST / f"{FILE_PREFIX}-{roman}.ttf") as upright,
            ):
                for ch in "日あカ。、ｱ":
                    a = italic["glyf"][italic.getBestCmap()[ord(ch)]]
                    b = upright["glyf"][upright.getBestCmap()[ord(ch)]]
                    if JP.get("italic_degrees", 8) >= 1:
                        self.assertNotEqual(a.coordinates, b.coordinates, ch)
                        self.assertGreaterEqual(a.xMin, 0)
                        self.assertLessEqual(
                            a.xMax, italic["hmtx"][italic.getBestCmap()[ord(ch)]][0]
                        )
                    elif JP.get("italic_degrees", 8) == 0 and (
                        style == "BoldItalic"
                        or JP.get("italic_strength", 0) == JP.get("regular_strength", 0)
                    ):
                        self.assertEqual(a.coordinates, b.coordinates, ch)

    def test_render(self):
        sheet = Image.new("RGB", (660, 311 * len(STYLES) + 10), "#fafcfb")
        for i, style in enumerate(STYLES):
            raster = render(style, sheet, 12 + i * 311)
            visible = GLYPHS.get("visible_fullwidth_space", False)
            self.assertEqual(bool(raster.getmask("　").getbbox()), visible)
            self.assertEqual(bool(raster.getmask("　", features=["-ss20"]).getbbox()), visible)
            self.assertEqual(bool(raster.getmask("　", features=["ss20"]).getbbox()), not visible)
            self.assertEqual(raster.getlength("　", features=["ss20"]), raster.getlength("　"))
            with TTFont(DIST / f"{FILE_PREFIX}-{style}.ttf") as face:
                marker = face["glyf"]["ideographicSpaceMarker"]
                half = face["hmtx"][face.getBestCmap()[32]][0]
                self.assertEqual(marker.numberOfContours, 8)
                self.assertEqual(marker.xMin + marker.xMax, 2 * half)
                glyf = face["glyf"]
                for base, alternate in (("m", "m.tlh.both"), ("i", "i.tlh.left")):
                    source = glyf[base]
                    changed = glyf[alternate]
                    if base == "m":
                        # Texture Healing moves the outer stems without rescaling them:
                        # every point of the left stem shifts by the same amount.
                        points = source.getCoordinates(glyf)[0]
                        moved = changed.getCoordinates(glyf)[0]
                        band = [
                            index
                            for index, (x, _) in enumerate(points)
                            if x < source.xMin + 0.2 * (source.xMax - source.xMin)
                        ]
                        deltas = {round(moved[index][0] - points[index][0]) for index in band}
                        self.assertEqual(len(deltas), 1)
                        self.assertLess(deltas.pop(), 0)
                        self.assertLess(changed.xMin, source.xMin)
                        self.assertGreater(changed.xMax, source.xMax)
                    else:
                        self.assertEqual(changed.xMax - changed.xMin, source.xMax - source.xMin)
                        self.assertEqual(face["hmtx"][alternate][0], face["hmtx"][base][0])
                # Diagonal-only w widens evenly from its anchoring left edge.
                self.assertEqual(glyf["w.tlh.right"].xMin, glyf["w"].xMin)
                self.assertGreater(glyf["w.tlh.right"].xMax, glyf["w"].xMax)
            self.assertIsNone(raster.getmask(" ").getbbox())
            self.assertEqual(raster.getlength("　"), raster.getlength("  "))
            original = ImageFont.truetype(
                INPUT / f"Iosevka-{style}.ttf", 32, layout_engine=ImageFont.Layout.RAQM
            )

            def original_mask(text, original=original):
                return bytes(original.getmask(text, features=["-calt"]))

            for line, cells in ROWS:
                self.assertAlmostEqual(
                    raster.getlength(line), raster.getlength("0") * cells, delta=0.25
                )
            for line in ("Il1|O {} [] => != <=>", "123456789"):
                self.assertEqual(
                    bytes(raster.getmask(line, features=["-calt"])), original_mask(line)
                )
            for sequence in ("->", "=>", "==", "!=", "::", "||", "&&", "<=>"):
                self.assertEqual(
                    bytes(raster.getmask(sequence, features=["-ss19"])),
                    bytes(raster.getmask(sequence)),
                    sequence,
                )
                self.assertNotEqual(
                    bytes(raster.getmask(sequence, features=["ss19"])),
                    bytes(raster.getmask(sequence)),
                    sequence,
                )
                self.assertAlmostEqual(
                    raster.getlength(sequence, features=["ss19"]),
                    raster.getlength(sequence),
                    delta=0.25,
                    msg=sequence,
                )
            if style in ("Italic", "BoldItalic"):
                self.assertNotEqual(
                    bytes(raster.getmask("self")),
                    bytes(raster.getmask("self", features=["ss01"])),
                )
                self.assertEqual(
                    raster.getlength("self", features=["ss01"]), raster.getlength("self")
                )
            else:
                self.assertEqual(
                    bytes(raster.getmask("self")),
                    bytes(raster.getmask("self", features=["ss01"])),
                )
            for text in ("im", "ml", "filming", "winning", "FT"):
                self.assertNotEqual(
                    bytes(raster.getmask(text)),
                    bytes(raster.getmask(text, features=["-calt"])),
                    text,
                )
                self.assertEqual(
                    raster.getlength(text),
                    raster.getlength(text, features=["-calt"]),
                    text,
                )
            self.assertEqual(raster.getlength("0"), original.getlength("0"))
            self.assertEqual(bytes(raster.getmask("0")), original_mask("0"))
            if GLYPHS.get("nerd_icons"):
                sample = "    󰀄 日本語"
                self.assertAlmostEqual(
                    raster.getlength(sample), raster.getlength("0") * 16, delta=0.25
                )
                self.assertTrue(all(raster.getmask(ch).getbbox() for ch in sample if ch != " "))
                ImageDraw.Draw(sheet).text((200, 12 + i * 311), sample, font=raster, fill="#15232b")
            for line in ("日本語", "ｶﾅ", "Ａ０"):
                self.assertTrue(raster.getmask(line).getbbox())

    def test_opentype_specimen_features(self):
        raster = ImageFont.truetype(
            DIST / f"{FILE_PREFIX}-Regular.ttf", 48, layout_engine=ImageFont.Layout.RAQM
        )
        self.assertNotEqual(
            bytes(raster.getmask("日　本", features=["-ss20"])),
            bytes(raster.getmask("日　本", features=["ss20"])),
        )

    def test_space_feature_with_opposite_default(self):
        visible = not GLYPHS.get("visible_fullwidth_space", False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{FILE_PREFIX}-Regular.ttf"
            build_face("Regular", path, JP["scale"], JP["baseline_shift"], visible, version=VERSION)
            raster = ImageFont.truetype(path, 32, layout_engine=ImageFont.Layout.RAQM)
            self.assertEqual(bool(raster.getmask("　").getbbox()), visible)
            self.assertEqual(bool(raster.getmask("　", features=["ss20"]).getbbox()), not visible)
            self.assertEqual(raster.getlength("　", features=["ss20"]), raster.getlength("  "))


if __name__ == "__main__":
    unittest.main()
