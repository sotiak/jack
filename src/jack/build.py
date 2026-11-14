"""Build static TrueType faces with Hack as the original glyph-ID prefix."""

import math
import os
import re
import shutil
import tempfile
import tomllib
import unicodedata
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.otlLib.builder import buildLookup, buildSingleSubstSubtable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
from fontTools.ttLib.tables.ttProgram import Program

from .embolden import embolden
from .fetch import BIZ_NUMBERS, BIZ_SUBSETS, ensure_inputs
from .paths import CONFIG, DIST, INPUT, LICENSES, PYPROJECT

FAMILY = "Back"
STYLES = {"Regular": 400, "Bold": 700, "Italic": 400, "BoldItalic": 700}


def project_version():
    """Return the release version advertised by the generated fonts."""
    version = tomllib.loads(PYPROJECT.read_text())["project"]["version"]
    font_revision(version)
    return version


def font_revision(version):
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)", version):
        raise ValueError("Version must be MAJOR.MINOR.PATCH with minor and patch in 0..99")
    major, minor, patch = map(int, version.split("."))
    if major > 32767:
        raise ValueError("Version major must be in 0..32767 for head.fontRevision")
    # Four decimal places keep each release distinct after 16.16 fixed-point rounding.
    return major + minor / 100 + patch / 10000


def source_paths(style):
    weight = STYLES[style]
    paths = [INPUT / f"biz-udgothic-{subset}-{weight}-normal.woff" for subset in BIZ_SUBSETS]
    paths.extend(INPUT / f"biz-udgothic-{number}-{weight}-normal.woff" for number in BIZ_NUMBERS)
    return sorted(paths)


def advance(cp, original, em, half):
    ch = chr(cp)
    if not original or unicodedata.category(ch) in {"Mn", "Me", "Cf"}:
        return 0
    width = unicodedata.east_asian_width(ch)
    if width in {"W", "F"}:
        return 2 * half
    if width in {"H", "Na"}:
        return half
    return 2 * half if original > em / 2 else half


def centered(src, name, scale, shift, width):
    # Flatten components before the transform so IDs and hint programs do not
    # refer back to the donor font. Center the source advance box (punctuation
    # intentionally has asymmetric ink and bearings).
    table = src["glyf"]
    points, ends, flags = table[name].getCoordinates(table)
    glyph = Glyph()
    if not ends:
        return glyph, 0
    old_width = src["hmtx"][name][0]
    offset = (width - old_width * scale) / 2
    glyph.numberOfContours = len(ends)
    glyph.coordinates = GlyphCoordinates(
        (otRound(x * scale + offset), otRound(y * scale + shift)) for x, y in points
    )
    glyph.endPtsOfContours = list(ends)
    glyph.flags = bytearray(flags)
    glyph.program = Program()
    glyph.program.fromBytecode(b"")
    glyph.recalcBounds(table)
    return glyph, glyph.xMin


def slash_zero(glyf, name):
    """Drop Hack's center dot and cross the bowl with a matching slash."""
    source = glyf[name]
    points, ends, flags = source.getCoordinates(glyf)
    # Hack's zero is bowl, counter, dot; keep the first two.
    ring_end = ends[1] + 1
    ring = points[:ring_end]
    counter = points[ends[0] + 1 : ring_end]
    inner_left, inner_right = min(x for x, _ in counter), max(x for x, _ in counter)
    inner_bottom, inner_top = min(y for _, y in counter), max(y for _, y in counter)
    y0 = inner_bottom + 0.13 * (inner_top - inner_bottom)
    y1 = inner_top - 0.13 * (inner_top - inner_bottom)
    center_x = (inner_left + inner_right) / 2
    # Lean the slash diagonally, but keep its band to a third of the counter
    # so it reads as a line rather than filling the bowl at bold weights.
    dx = 0.68 * (y1 - y0) / 2
    half_band = 0.17 * (inner_right - inner_left)
    corners = (
        (center_x - dx - half_band, y0),
        (center_x + dx - half_band, y1),
        (center_x + dx + half_band, y1),
        (center_x - dx + half_band, y0),
    )
    glyph = Glyph()
    glyph.numberOfContours = 3
    glyph.coordinates = GlyphCoordinates(
        [tuple(p) for p in ring] + [(otRound(x), otRound(y)) for x, y in corners]
    )
    glyph.endPtsOfContours = [ends[0], ends[1], ring_end + 3]
    glyph.flags = bytearray(flags[:ring_end]) + bytearray([1] * 4)
    glyph.program = Program()
    glyph.program.fromBytecode(b"")
    return glyph


def add_nerd_icons(font, cmap, half):
    """Fit the symbols-only donor's PUA outlines in a single Back cell."""
    with TTFont(INPUT / "NerdSymbols.ttf") as donor:
        for cp, name in sorted(donor.getBestCmap().items()):
            if cp in cmap or unicodedata.category(chr(cp)) != "Co":
                continue
            source = donor["glyf"][name]
            if not source.numberOfContours:
                continue
            # Cached bounds can differ by a unit between otherwise identical
            # upstream builds; use the outline itself for scaling.
            source.recalcBounds(donor["glyf"])
            width = max(1, source.xMax - source.xMin)
            height = max(1, source.yMax - source.yMin)
            ascent, descent = font["hhea"].ascent, font["hhea"].descent
            scale = min(
                font["head"].unitsPerEm / donor["head"].unitsPerEm,
                half / width,
                (ascent - descent) / height,
            )
            shift = (ascent + descent - scale * (source.yMax + source.yMin)) / 2
            glyph, _ = centered(donor, name, scale, shift, half)
            dx = otRound((half - glyph.xMax - glyph.xMin) / 2)
            glyph.coordinates.translate((dx, 0))
            glyph.recalcBounds(font["glyf"])
            target = f"nerd{cp:X}"
            font["glyf"][target] = glyph
            font["hmtx"][target] = (half, glyph.xMin)
            cmap[cp] = target
        return donor["name"].getDebugName(0)


def set_names(font, style, donor_notice, version):
    names = newTable("name")
    names.names = []
    copyright_text = font["name"].getDebugName(0) + "\n" + donor_notice
    terms = "\n\n".join((LICENSES / f).read_text() for f in ("BIZ-OFL.txt", "Hack.txt"))
    label = font["name"].getDebugName(2)
    values = {
        0: copyright_text,
        1: FAMILY,
        2: label,
        3: f"{version};Back-{style}",
        4: f"{FAMILY} {label}",
        5: f"Version {version}",
        6: f"Back-{style}",
        13: terms,
        14: "https://openfontlicense.org/",
        16: FAMILY,
        17: label,
    }
    for key, value in values.items():
        names.setName(value, key, 3, 1, 0x409)
    font["name"] = names
    font["head"].fontRevision = font_revision(version)


def space_marker(half, em, style):
    pen = TTGlyphPen(None)
    center_y = otRound(em * 0.35)
    radius = otRound(em * 0.36)
    leg = otRound(em * 0.135)
    stroke = otRound(em * (0.060 if STYLES[style] == 700 else 0.046))
    dash = otRound(em * 0.085)
    # Draw one rounded corner and the middle dash, rotating both to each edge.
    for quadrant in range(4):

        def point(x, y, rotation=quadrant):
            for _ in range(rotation):
                x, y = -y, x
            return half + x, center_y + y

        r = radius
        pen.moveTo(point(r - leg, r))
        pen.qCurveTo(point(r, r), point(r, r - leg))
        pen.lineTo(point(r - stroke, r - leg))
        pen.qCurveTo(point(r - stroke, r - stroke), point(r - leg, r - stroke))
        pen.closePath()
        pen.moveTo(point(-dash, r))
        pen.lineTo(point(dash, r))
        pen.lineTo(point(dash, r - stroke))
        pen.lineTo(point(-dash, r - stroke))
        pen.closePath()
    return pen.glyph(), half - radius


def add_zero_feature(font, original, alternate):
    table = font["GSUB"].table
    lookups = table.LookupList
    feature = otTables.FeatureRecord()
    feature.FeatureTag = "zero"  # Sorts after every feature in the pinned Hack inputs.
    feature.Feature = otTables.Feature()
    feature.Feature.FeatureParams = None
    feature.Feature.LookupListIndex = [len(lookups.Lookup)]
    feature.Feature.LookupCount = 1
    lookups.Lookup.append(buildLookup([buildSingleSubstSubtable({original: alternate})]))
    lookups.LookupCount = len(lookups.Lookup)
    features = table.FeatureList
    index = len(features.FeatureRecord)
    features.FeatureRecord.append(feature)
    features.FeatureCount = index + 1
    for record in table.ScriptList.ScriptRecord:
        script = record.Script
        languages = [r.LangSys for r in script.LangSysRecord]
        if script.DefaultLangSys:
            languages.append(script.DefaultLangSys)
        for lang in languages:
            lang.FeatureIndex.append(index)
            lang.FeatureCount = len(lang.FeatureIndex)


def build_face(
    style,
    dest,
    scale,
    shift,
    visible_space=False,
    nerd_icons=False,
    jp_slant=8,
    zero_style="dot",
    bold_strength=0,
    regular_strength=0,
    italic_strength=0,
    *,
    version,
):
    with TTFont(INPUT / f"Hack-{style}.ttf", recalcTimestamp=False) as font:
        cmap = dict(font.getBestCmap())
        half = font["hmtx"][cmap[32]][0]
        em = font["head"].unitsPerEm
        # Load before appending, while the original GIDs still resolve.
        glyf = font["glyf"]
        metrics = font["hmtx"].metrics
        if zero_style in ("slash", "feature"):
            original = cmap[ord("0")]
            name = "zero.slash" if zero_style == "feature" else original
            metrics[name] = metrics[original]
            glyf[name] = slash_zero(glyf, original)
            glyf[name].flags[0] |= 0x40  # OVERLAP_SIMPLE: slash intersects the bowl.
            glyf[name].recalcBounds(glyf)
            if glyf[name].xMin != metrics[name][1]:
                raise ValueError(f"{style}: slash zero left bearing differs from Hack")
            if zero_style == "feature":
                add_zero_feature(font, original, name)
        for cp, name in list(cmap.items()):
            if unicodedata.east_asian_width(chr(cp)) in {"W", "F"} and metrics[name][0] == half:
                new_name = f"wide{cp:04X}"
                glyf[new_name], bearing = centered(font, name, 1, 0, 2 * half)
                metrics[new_name] = (2 * half, bearing)
                cmap[cp] = new_name

        shear = math.tan(math.radians(jp_slant)) if "Italic" in style else 0
        strength = {"Regular": regular_strength, "Italic": italic_strength}.get(
            style, bold_strength
        )
        variations = {}
        notices = set()
        for path in source_paths(style):
            with TTFont(path) as donor:
                notices.add(donor["name"].getDebugName(0))
                src_em = donor["head"].unitsPerEm
                local = {}

                def add(name, width, local=local, src_em=src_em, donor=donor):
                    key = (name, width)
                    if key not in local:
                        new_name = f"jp{len(glyf):05d}"
                        glyph, lsb = centered(donor, name, scale * em / src_em, shift, width)
                        if strength and glyph.numberOfContours:
                            embolden(glyph, strength)
                            glyph.recalcBounds(donor["glyf"])
                            lsb = glyph.xMin
                        if shear and glyph.numberOfContours:
                            # Pivot about the vertical middle of the ink. Keep
                            # spacing glyphs inside the cell after shearing.
                            mid = (glyph.yMin + glyph.yMax) / 2
                            points = [(x + shear * (y - mid), y) for x, y in glyph.coordinates]
                            left = min(x for x, _ in points)
                            right = max(x for x, _ in points)
                            fit = min(1, width / max(1, right - left)) if width else 1
                            offset = min(max(0, -left * fit), width - right * fit) if width else 0
                            glyph.coordinates = GlyphCoordinates(
                                (otRound(x * fit + offset), y) for x, y in points
                            )
                            glyph.recalcBounds(donor["glyf"])
                            lsb = glyph.xMin
                        glyf[new_name] = glyph
                        metrics[new_name] = (width, lsb)
                        local[key] = new_name
                    return local[key]

                mapping = donor.getBestCmap()
                for cp, name in sorted(mapping.items()):
                    if cp not in cmap:
                        cmap[cp] = add(name, advance(cp, donor["hmtx"][name][0], src_em, half))
                for table in donor["cmap"].tables:
                    if table.format == 14:
                        for selector, entries in table.uvsDict.items():
                            for cp, name in entries:
                                if cp in cmap:
                                    variations[cp, selector] = (
                                        add(name, metrics[cmap[cp]][0]) if name else None
                                    )

        if nerd_icons:
            notices.add(add_nerd_icons(font, cmap, half))
        if visible_space:
            name = "ideographicSpaceMarker"
            glyf[name], bearing = space_marker(half, em, style)
            glyf[name].recalcBounds(glyf)
            metrics[name] = (2 * half, bearing)
            cmap[0x3000] = name
        font.setGlyphOrder(list(glyf.glyphOrder))
        uvs = [(cp, sel, name) for (cp, sel), name in sorted(variations.items())]
        FontBuilder(font=font).setupCharacterMap(cmap, uvs=uvs, allowFallback=True)
        os2 = font["OS/2"]
        os2.recalcUnicodeRanges(font)
        os2.recalcCodePageRanges(font)
        # Include transformed glyphs in Windows clipping metrics.
        for glyph_name in glyf.glyphOrder:
            glyph = glyf[glyph_name]
            if glyph.numberOfContours:
                os2.usWinAscent = max(os2.usWinAscent, glyph.yMax)
                os2.usWinDescent = max(os2.usWinDescent, -glyph.yMin)
        set_names(font, style, "\n".join(sorted(notices)), version)
        if nerd_icons:
            terms = font["name"].getDebugName(13)
            terms += "\nNerd Fonts 3.3.0: see accompanying nerd/ licenses and attributions."
            font["name"].setName(terms, 13, 3, 1, 0x409)
        for tag in ("DSIG", "TTFA"):
            if tag in font:
                del font[tag]
        font.save(dest)


def main():
    ensure_inputs()
    cfg = tomllib.loads(CONFIG.read_text())
    scale, shift = cfg["japanese_scale"], cfg["baseline_shift"]
    if (
        not math.isfinite(scale)
        or not 0 < scale <= 2
        or type(shift) is not int
        or abs(shift) > 2048
    ):
        raise ValueError(
            "Expected 0 < japanese_scale <= 2 and an integer baseline_shift within ±2048"
        )
    visible = cfg.get("visible_fullwidth_space", False)
    if type(visible) is not bool:
        raise ValueError("visible_fullwidth_space must be true or false")
    nerd = cfg.get("nerd_icons", False)
    if type(nerd) is not bool:
        raise ValueError("nerd_icons must be true or false")
    angle = cfg.get("japanese_italic_degrees", 8)
    if type(angle) not in (int, float) or not 0 <= angle <= 15:
        raise ValueError("japanese_italic_degrees must be between 0 and 15")
    zero_style = cfg.get("zero_style", "dot")
    if zero_style not in ("feature", "slash", "dot"):
        raise ValueError("zero_style must be feature, slash or dot")
    strength = cfg.get("japanese_bold_strength", 0)
    if type(strength) is not int or not 0 <= strength <= 48:
        raise ValueError("japanese_bold_strength must be an integer from 0 to 48")
    regular_strength = cfg.get("japanese_regular_strength", 0)
    if type(regular_strength) is not int or not 0 <= regular_strength <= 48:
        raise ValueError("japanese_regular_strength must be an integer from 0 to 48")
    italic_strength = cfg.get("japanese_italic_strength", 0)
    if type(italic_strength) is not int or not 0 <= italic_strength <= 48:
        raise ValueError("japanese_italic_strength must be an integer from 0 to 48")
    out = DIST
    version = project_version()
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        for style in STYLES:
            build_face(
                style,
                Path(tmp) / f"Back-{style}.ttf",
                scale,
                shift,
                visible,
                nerd,
                angle,
                zero_style,
                strength,
                regular_strength,
                italic_strength,
                version=version,
            )
        for path in sorted(Path(tmp).glob("*.ttf")):
            os.replace(path, out / path.name)
    for path in LICENSES.iterdir():
        if path.is_dir():
            shutil.copytree(path, out / path.name, dirs_exist_ok=True)
        else:
            shutil.copyfile(path, out / path.name)


if __name__ == "__main__":
    main()
