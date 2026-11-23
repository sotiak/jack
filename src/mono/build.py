"""Build static TrueType faces with Iosevka as the original glyph-ID prefix."""

import math
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import unicodedata
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.misc.transform import Identity
from fontTools.otlLib.builder import (
    buildLigatureSubstSubtable,
    buildLookup,
    buildSingleSubstSubtable,
    buildStatTable,
)
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
from fontTools.ttLib.tables.ttProgram import Program

from .embolden import embolden
from .fetch import BIZ_STYLES, IOSEVKA_ITALIC_STYLES, ensure_inputs
from .glyphs import VARIANTS
from .paths import CONFIG, DIST, INPUT, LICENSE, LICENSES, PYPROJECT
from .script_variants import SCRIPT_VARIANTS

FAMILY = "Sotiak Mono"
FILE_PREFIX = "SotiakMono"
STYLES = {"Regular": 400, "Bold": 700, "Italic": 400, "BoldItalic": 700}
STYLE_LABELS = {
    "Regular": "Regular",
    "Bold": "Bold",
    "Italic": "Italic",
    "BoldItalic": "Bold Italic",
}
TEXTURE_GIVE = ("i", "l", "j", "t", "f", "F", "I", "one", "seven")
TEXTURE_TAKE = ("m", "w", "M", "W", "T", "at", "ampersand", "percent", "numbersign")
# Texture Healing never rescales stems: give shifts, take moves its outer bands only.
TEXTURE_GIVE_SHIFT = 0.1
TEXTURE_TAKE_GROW = 0.1
TEXTURE_HOLD = 0.3
TEXTURE_EDGE = 0.6
# Diagonal-only glyphs widen evenly; band warping would thicken their legs.
TEXTURE_SCALE_TAKE = ("w", "W")
TAIL_TOP = {"Regular": -149, "Bold": -122, "Italic": -149, "BoldItalic": -122}
TAIL_POINTS = {
    "Regular": {"g": (12, 56), "j": (6, 25)},
    "Bold": {"g": (12, 56), "j": (6, 25)},
    "Italic": {"g": (12, 56), "j": (12, 29)},
    "BoldItalic": {"g": (12, 56), "j": (12, 29)},
}
TEXTURE_STATIONARY = (
    "space",
    "period",
    "comma",
    "colon",
    "semicolon",
    "exclam",
    "question",
    "parenleft",
    "parenright",
    "bracketleft",
    "bracketright",
    "braceleft",
    "braceright",
    "slash",
    "backslash",
    "bar",
    "hyphen",
    "plus",
    "equal",
    "less",
    "greater",
    "quotedbl",
    "quotesingle",
    "grave",
)
SCRIPT_CHARS = "fklrsoO"
SCRIPT_STRENGTH = 30  # Approximates Iosevka's Regular-to-Bold stem gain at 1000 UPM.
# Top-serif left edges for i/j and their dotless forms: (Iosevka x, Sotiak Mono x).
# The dotless forms are used by accented composites.
SERIF_LEFTS = {
    "Regular": {"i": (115, 99), "j": (162, 74), "ı": (115, 99), "ȷ": (162, 74)},
    "Bold": {"i": (115, 99), "j": (162, 74), "ı": (115, 99), "ȷ": (162, 74)},
    "Italic": {"i": (137, 121), "j": (184, 96), "ı": (137, 121), "ȷ": (184, 96)},
    "BoldItalic": {"i": (135, 119), "j": (182, 94), "ı": (135, 119), "ȷ": (182, 94)},
}
# Upright j is shifted right to balance the cell; matches JetBrains Mono's right edge.
J_SHIFT = {"Regular": 31, "Bold": 31}
LIGATURES = (
    "***",
    "**",
    "<*>",
    "*>",
    "<*",
    "<|>",
    "|||",
    "||",
    "|||>",
    "||>",
    "|>",
    "|]",
    "[|",
    "<|||",
    "<||",
    "<|",
    "<>",
    "->",
    "<-",
    "::=",
    "===",
    "==",
    "<=>",
    "<=<",
    ">=>",
    "=>>",
    "=>",
    "=<<",
    "<<<",
    "<<",
    ">>>",
    ">>",
    "<+>",
    "+>",
    "<+",
    "!==",
    ".=",
    "=:=",
    ":=",
    ":::",
    "::",
    ":<:",
    ":>:",
    "=!=",
    "!=",
    "#=",
    "%%",
    "&&",
    "??",
    "<$>",
    "<$",
    "$>",
    "...",
    "..",
    ";;",
    "</>",
    "/>",
    "</",
)


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
    return [INPUT / f"BIZUDGothic-{BIZ_STYLES[STYLES[style]]}.ttf"]


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


def make_glyph(points, ends, flags):
    """Build an unhinted simple glyph; ttfautohint restores hints afterwards."""
    glyph = Glyph()
    glyph.numberOfContours = len(ends)
    glyph.coordinates = GlyphCoordinates(points)
    glyph.endPtsOfContours = list(ends)
    glyph.flags = bytearray(flags)
    glyph.program = Program()
    glyph.program.fromBytecode(b"")
    return glyph


def centered(src, name, scale, shift, width):
    # Flatten components before the transform so IDs and hint programs do not
    # refer back to the donor font. Center the source advance box (punctuation
    # intentionally has asymmetric ink and bearings).
    table = src["glyf"]
    points, ends, flags = table[name].getCoordinates(table)
    if not ends:
        return Glyph(), 0
    old_width = src["hmtx"][name][0]
    offset = (width - old_width * scale) / 2
    glyph = make_glyph(
        ((otRound(x * scale + offset), otRound(y * scale + shift)) for x, y in points),
        ends,
        flags,
    )
    glyph.recalcBounds(table)
    return glyph, glyph.xMin


def normalize_overlap(glyph):
    """Keep the overlap hint on the first point, the only place OTS allows it."""
    if glyph.numberOfContours > 0 and glyph.flags and any(flag & 0x40 for flag in glyph.flags):
        glyph.flags = bytearray(
            (flag & ~0x40) | (0x40 if index == 0 else 0) for index, flag in enumerate(glyph.flags)
        )


def refresh_composites(font, roots):
    """Recalculate composite bounds that depend on replaced base glyphs."""
    affected = set(roots)
    changed = True
    while changed:
        changed = False
        for name in font.getGlyphOrder():
            glyph = font["glyf"][name]
            if (
                glyph.numberOfContours < 0
                and name not in affected
                and any(component.glyphName in affected for component in glyph.components)
            ):
                affected.add(name)
                changed = True
    for name in font.getGlyphOrder():
        glyph = font["glyf"][name]
        if name in affected and glyph.numberOfContours < 0:
            glyph.recalcBounds(font["glyf"])


def copy_true_italic(font, style, cmap):
    """Borrow Iosevka's true-italic a/f/y/g, as JetBrains Mono does."""
    if style not in IOSEVKA_ITALIC_STYLES:
        return
    with TTFont(INPUT / f"Iosevka-{style}True.ttf") as donor:
        donor_cmap = donor.getBestCmap()
        for char in "afyg":
            target = cmap[ord(char)]
            source = donor_cmap[ord(char)]
            points, ends, flags = donor["glyf"][source].getCoordinates(donor["glyf"])
            glyph = make_glyph(points, ends, flags)
            glyph.recalcBounds(font["glyf"])
            normalize_overlap(glyph)
            advance, lsb = donor["hmtx"][source]
            if advance != font["hmtx"][target][0]:
                raise ValueError(f"{style}: true italic {char} advance differs from Iosevka")
            font["glyf"][target] = glyph
            font["hmtx"][target] = (advance, lsb)
        refresh_composites(font, {cmap[ord(char)] for char in "afyg"})


def copy_single_storey_g(font, style, cmap):
    """Unslant the true-italic g for the upright Regular and Bold faces."""
    if style not in ("Regular", "Bold"):
        return
    donor_style = "Italic" if style == "Regular" else "BoldItalic"
    with TTFont(INPUT / f"Iosevka-{donor_style}True.ttf") as donor:
        target = cmap[ord("g")]
        source = donor.getBestCmap()[ord("g")]
        points, ends, flags = donor["glyf"][source].getCoordinates(donor["glyf"])
        advance = donor["hmtx"][source][0]
        if advance != font["hmtx"][target][0]:
            raise ValueError(f"{style}: single-storey g advance differs from Iosevka")
        slope = math.tan(math.radians(9))
        unslanted = [(otRound(x - slope * y), otRound(y)) for x, y in points]
        # Unslanting about the baseline pulls the ink left; recenter it in the cell.
        left = min(x for x, _ in unslanted)
        right = max(x for x, _ in unslanted)
        dx = otRound((advance - left - right) / 2)
        glyph = make_glyph(((x + dx, y) for x, y in unslanted), ends, flags)
        glyph.recalcBounds(font["glyf"])
        normalize_overlap(glyph)
        font["glyf"][target] = glyph
        font["hmtx"][target] = (advance, glyph.xMin)
        refresh_composites(font, {target})


def copy_rounded_w(font, style, cmap):
    """Use Iosevka's cv32-34/cv57-34 W/w with rounded vertical sides."""
    variants = VARIANTS[style]
    roots = set()
    for char in ("W", "w"):
        target = cmap[ord(char)]
        spec = variants[char]
        glyph = make_glyph(spec["points"], spec["ends"], spec["flags"])
        glyph.recalcBounds(font["glyf"])
        normalize_overlap(glyph)
        if spec["advance"] != font["hmtx"][target][0]:
            raise ValueError(f"{style}: rounded {char} advance differs from Iosevka")
        font["glyf"][target] = glyph
        font["hmtx"][target] = (spec["advance"], spec["lsb"])
        roots.add(target)
    refresh_composites(font, roots)


def copy_flat_t(font, style, cmap):
    """Use Iosevka's cv54-8 t with a flat hook and short neck."""
    spec = VARIANTS[style]["t"]
    target = cmap[ord("t")]
    glyph = make_glyph(spec["points"], spec["ends"], spec["flags"])
    glyph.recalcBounds(font["glyf"])
    normalize_overlap(glyph)
    if spec["advance"] != font["hmtx"][target][0]:
        raise ValueError(f"{style}: flat t advance differs from Iosevka")
    font["glyf"][target] = glyph
    font["hmtx"][target] = (spec["advance"], spec["lsb"])
    refresh_composites(font, {target})


def copy_hanging_m(font, style, cmap):
    """Use Iosevka's cv23-1 M with a hanging serifless middle."""
    spec = VARIANTS[style]["M"]
    target = cmap[ord("M")]
    glyph = make_glyph(spec["points"], spec["ends"], spec["flags"])
    glyph.recalcBounds(font["glyf"])
    normalize_overlap(glyph)
    if spec["advance"] != font["hmtx"][target][0]:
        raise ValueError(f"{style}: hanging M advance differs from Iosevka")
    font["glyf"][target] = glyph
    font["hmtx"][target] = (spec["advance"], spec["lsb"])
    refresh_composites(font, {target})


def widen_r(font, style, cmap):
    """Widen the lowercase r by 13% around the cell center."""
    target = cmap[ord("r")]
    points, ends, flags = font["glyf"][target].getCoordinates(font["glyf"])
    glyph = make_glyph(((otRound(300 + (x - 300) * 1.13), y) for x, y in points), ends, flags)
    glyph.recalcBounds(font["glyf"])
    normalize_overlap(glyph)
    advance = font["hmtx"][target][0]
    font["glyf"][target] = glyph
    font["hmtx"][target] = (advance, glyph.xMin)
    refresh_composites(font, {target})


def lengthen_ij_serifs(font, style, cmap):
    """Lengthen the i/j top serifs toward JetBrains Mono proportions."""
    for char, (old, new) in SERIF_LEFTS[style].items():
        target = cmap[ord(char)]
        points, ends, flags = font["glyf"][target].getCoordinates(font["glyf"])
        moved = sum(1 for x, _ in points if x == old)
        if moved != 2:
            raise ValueError(f"{style}: expected 2 serif points on {char}, found {moved}")
        glyph = make_glyph(((new if x == old else x, y) for x, y in points), ends, flags)
        glyph.recalcBounds(font["glyf"])
        advance = font["hmtx"][target][0]
        font["glyf"][target] = glyph
        font["hmtx"][target] = (advance, glyph.xMin)
    refresh_composites(font, {cmap[ord(char)] for char in SERIF_LEFTS[style]})


def shift_j(font, style, cmap):
    """Shift upright j and its accented forms right to balance the cell."""
    dx = J_SHIFT.get(style, 0)
    if not dx:
        return
    roots = {cmap[ord("j")], cmap[0x0237]}
    for target in roots:
        points, ends, flags = font["glyf"][target].getCoordinates(font["glyf"])
        glyph = make_glyph(((x + dx, y) for x, y in points), ends, flags)
        glyph.recalcBounds(font["glyf"])
        advance = font["hmtx"][target][0]
        font["glyf"][target] = glyph
        font["hmtx"][target] = (advance, glyph.xMin)
    for name in font.getGlyphOrder():
        glyph = font["glyf"][name]
        if not glyph.isComposite() or not any(c.glyphName in roots for c in glyph.components):
            continue
        for component in glyph.components:
            if component.glyphName not in roots:
                component.x += dx
        glyph.recalcBounds(font["glyf"])
        font["hmtx"][name] = (font["hmtx"][name][0], glyph.xMin)
    refresh_composites(font, roots)


def add_nerd_icons(font, cmap, half):
    """Fit the symbols-only donor's PUA outlines in a single Sotiak Mono cell."""
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
    terms = "\n\n".join(
        (LICENSES / name).read_text()
        for name in ("BIZ-OFL.txt", "Iosevka-OFL.txt", "0xProto-OFL.txt")
    )
    label = STYLE_LABELS[style]
    values = {
        0: copyright_text,
        1: FAMILY,
        2: label,
        3: f"{version};{FILE_PREFIX}-{style}",
        4: f"{FAMILY} {label}",
        5: f"Version {font_revision(version):.4f}",
        6: f"{FILE_PREFIX}-{style}",
        13: terms,
        14: "https://openfontlicense.org/",
        16: FAMILY,
        17: label,
    }
    for key, value in values.items():
        names.setName(value, key, 3, 1, 0x409)
    font["name"] = names
    font["head"].fontRevision = font_revision(version)


def flatten_glyph(name, glyf, pen, transform=Identity):
    """Draw a glyph into pen with its component references resolved."""
    glyph = glyf[name]
    if glyph.isComposite():
        for component in glyph.components:
            component_name, component_transform = component.getComponentInfo()
            flatten_glyph(component_name, glyf, pen, transform.transform(component_transform))
    else:
        glyph.draw(TransformPen(pen, transform), glyf)


def decompose_nested_components(glyf):
    """Flatten composites that point at other composites, which some renderers mishandle."""
    # glyf iterates integer keys, so spell out .keys() for the glyph names.
    composites = {name for name in glyf.keys() if glyf[name].isComposite()}  # noqa: SIM118
    for name in list(glyf.keys()):
        glyph = glyf[name]
        if glyph.isComposite() and any(c.glyphName in composites for c in glyph.components):
            pen = TTGlyphPen(None)
            flatten_glyph(name, glyf, pen)
            glyf[name] = pen.glyph()
            glyf[name].recalcBounds(glyf)


def sanitize_glyph_name(name):
    """Return a PostScript-safe name as recommended by Microsoft's OpenType spec."""
    if name in {".notdef", ".null"} or name.startswith(".ttfautohint"):
        return name
    if name == "nonbreakingspace":
        return "uni00A0"
    name = name.lstrip(".").replace("-", "_")
    if not (name[0].isascii() and (name[0].isalpha() or name[0] == "_")):
        name = f"g{name}"
    return name


def set_glyph_names(font):
    """Rename glyphs in the post table so PDF and PostScript accept them."""
    post = font["post"]
    seen = set()
    for name in font.getGlyphOrder():
        safe = sanitize_glyph_name(name)
        if safe in seen:
            raise ValueError(f"Glyph name collision: {name} -> {safe}")
        seen.add(safe)
        if safe != name:
            post.mapping[name] = safe


def add_stat(font, style):
    """Describe weight and italic relationships in a STAT table."""
    weight = STYLES[style]
    weight_value = {"value": weight, "name": "Regular" if weight == 400 else "Bold"}
    if weight == 400:
        weight_value["flags"] = 0x2  # ELIDABLE_AXIS_VALUE_NAME
    if "Italic" in style:
        ital_value = {"value": 1, "name": "Italic"}
    else:
        # Roman links to the italic value, as the naming spec expects for statics.
        ital_value = {"value": 0, "name": "Roman", "flags": 0x2, "linkedValue": 1.0}
    buildStatTable(
        font,
        [
            {"tag": "wght", "name": "Weight", "ordering": 0, "values": [weight_value]},
            {"tag": "ital", "name": "Italic", "ordering": 1, "values": [ital_value]},
        ],
        elidedFallbackName="Regular",
        macNames=False,
    )


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


def add_feature(font, tag, lookup_indices):
    table = font["GSUB"].table
    feature = otTables.FeatureRecord()
    feature.FeatureTag = tag
    feature.Feature = otTables.Feature()
    feature.Feature.FeatureParams = None
    feature.Feature.LookupListIndex = list(lookup_indices)
    feature.Feature.LookupCount = len(lookup_indices)
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


def add_substitution_feature(font, tag, original, alternate):
    lookups = font["GSUB"].table.LookupList
    lookups.Lookup.append(buildLookup([buildSingleSubstSubtable({original: alternate})]))
    lookups.LookupCount = len(lookups.Lookup)
    add_feature(font, tag, [lookups.LookupCount - 1])


def disable_ligatures(font):
    """Turn Iosevka's ligatures off; ss19 carries the shape-preserving set."""
    if "GSUB" not in font:
        return
    table = font["GSUB"].table
    for record in table.FeatureList.FeatureRecord:
        if record.FeatureTag in ("calt", "liga"):
            record.Feature.LookupListIndex = []
            record.Feature.LookupCount = 0


def glyph_outline(font, name):
    points, ends, flags = font["glyf"][name].getCoordinates(font["glyf"])
    if not ends:
        raise ValueError(f"ligature: {name} has no contours")
    return list(points), list(ends), bytearray(flags)


def join_arrow(placed, sequence):
    """Stretch the hyphen into the chevron's notch so -> and <- read as arrows."""
    hyphen = 0 if sequence == "->" else 1
    chevron = 1 - hyphen
    points = placed[hyphen][0]
    center = (min(y for _, y in points) + max(y for _, y in points)) / 2
    facing_right = sequence == "->"
    candidates = [x for x, y in placed[chevron][0] if abs(y - center) <= 70]
    if not candidates:
        return
    notch = min(candidates) if facing_right else max(candidates)
    target = notch + 4 if facing_right else notch - 4
    edge = sorted(range(len(points)), key=lambda i: points[i][0], reverse=facing_right)[:2]
    for index in edge:
        points[index] = (target, points[index][1])


def add_spacing_ligatures(font, cmap):
    """Add 0xProto-style ligatures that tighten spacing without redrawing symbols."""
    if "GSUB" not in font:
        return
    glyf = font["glyf"]
    metrics = font["hmtx"].metrics
    half = metrics[cmap[32]][0]
    margin = otRound(half * 0.04)
    mapping = {}
    added = []
    for sequence in LIGATURES:
        names = [cmap[ord(char)] for char in sequence]
        parts = []
        for name in names:
            points, ends, flags = glyph_outline(font, name)
            parts.append(
                (
                    points,
                    ends,
                    flags,
                    min(x for x, _ in points),
                    max(x for x, _ in points),
                )
            )
        widths = [xmax - xmin for _, _, _, xmin, xmax in parts]
        gaps = [parts[index + 1][3] - parts[index][4] + half for index in range(len(parts) - 1)]
        gap = max(0.12 * half, 0.5 * min(gaps))
        room = len(parts) * half - 2 * margin - sum(widths)
        gap = max(0, min(gap, room / (len(parts) - 1)))
        left = (len(parts) * half - (sum(widths) + gap * (len(parts) - 1))) / 2
        placed = []
        x = left
        for (points, ends, flags, xmin, _), width in zip(parts, widths, strict=True):
            shift = x - xmin
            placed.append(([(px + shift, py) for px, py in points], ends, flags))
            x += width + gap
        if sequence in ("->", "<-"):
            join_arrow(placed, sequence)
        points = []
        ends = []
        flags = []
        count = 0
        for part_points, part_ends, part_flags in placed:
            points.extend((otRound(x), otRound(y)) for x, y in part_points)
            ends.extend(count + end for end in part_ends)
            flags.extend(part_flags)
            count += len(part_points)
        glyph = make_glyph(points, ends, flags)
        glyph.recalcBounds(glyf)
        normalize_overlap(glyph)
        name = "lig." + "_".join(names)
        glyf[name] = glyph
        metrics[name] = (len(names) * half, glyph.xMin)
        mapping[tuple(names)] = name
        added.append(name)
    if not mapping:
        return
    order = list(font.getGlyphOrder())
    order.extend(name for name in added if name not in order)
    font.setGlyphOrder(order)
    lookups = font["GSUB"].table.LookupList
    lookups.Lookup.append(buildLookup([buildLigatureSubstSubtable(mapping)]))
    lookups.LookupCount = len(lookups.Lookup)
    add_feature(font, "ss19", [lookups.LookupCount - 1])


def add_script_variants(font, style, cmap):
    """Use 0xProto's italic Script Variant as ss01 in the italic faces."""
    if style not in ("Italic", "BoldItalic") or "GSUB" not in font:
        return
    glyf = font["glyf"]
    metrics = font["hmtx"].metrics
    half = metrics[cmap[32]][0]
    margin = otRound(half * 0.04)
    strength = SCRIPT_STRENGTH if style == "BoldItalic" else 0
    ours = {}
    for char in ("o", "O"):
        glyph = glyf[cmap[ord(char)]]
        glyph.recalcBounds(glyf)
        ours[char] = glyph.yMax
    mapping = {}
    added = []
    for char in SCRIPT_CHARS:
        spec = SCRIPT_VARIANTS[char]
        points, ends, flags = spec["points"], spec["ends"], spec["flags"]
        scale_x = half / spec["advance"]
        scale_y = ours["O"] / spec["ymax"] if char == "O" else ours["o"] / spec["ymax"]
        points = [(x * scale_x, y * scale_y) for x, y in points]
        xmin = min(x for x, _ in points)
        xmax = max(x for x, _ in points)
        room = half - 2 * margin - strength
        if xmax - xmin > room:
            fit = room / (xmax - xmin)
            points = [(x * fit, y) for x, y in points]
            xmin *= fit
            xmax *= fit
        shift = (half - xmin - xmax) / 2
        glyph = make_glyph(((otRound(x + shift), otRound(y)) for x, y in points), ends, flags)
        glyph.recalcBounds(glyf)
        if strength:
            embolden(glyph, strength)
            glyph.recalcBounds(glyf)
            dx = otRound((half - glyph.xMin - glyph.xMax) / 2)
            glyph.coordinates.translate((dx, 0))
            glyph.recalcBounds(glyf)
        normalize_overlap(glyph)
        name = f"{char}.ss01"
        glyf[name] = glyph
        metrics[name] = (half, glyph.xMin)
        mapping[cmap[ord(char)]] = name
        added.append(name)
    order = list(font.getGlyphOrder())
    order.extend(name for name in added if name not in order)
    font.setGlyphOrder(order)
    lookups = font["GSUB"].table.LookupList
    lookups.Lookup.append(buildLookup([buildSingleSubstSubtable(mapping)]))
    lookups.LookupCount = len(lookups.Lookup)
    add_feature(font, "ss01", [lookups.LookupCount - 1])


def sweep_gj_tails(font, style, cmap):
    """Replace the g/j hooks with JetBrains-style horizontal feet."""
    glyf = font["glyf"]
    metrics = font["hmtx"].metrics
    top = TAIL_TOP[style]
    slant = math.tan(math.radians(9)) if style in ("Italic", "BoldItalic") else 0
    roots = set()
    targets = (
        ("g", cmap[ord("g")], 2),
        ("j", cmap[ord("j")], 2),
        ("j", cmap[0x0237], 1),
    )
    for family, target, contours in targets:
        top_keep, bottom_keep = TAIL_POINTS[style][family]
        source = glyf[target]
        points, ends, flags = source.getCoordinates(glyf)
        if len(ends) != contours:
            raise ValueError(f"{style}: expected {contours} contours on {target}")
        first_end = ends[0]
        left = otRound(points[0][0])
        top_y = otRound(points[top_keep][1])
        bottom = -223
        if top_y != top or otRound(points[bottom_keep][1]) != bottom:
            raise ValueError(f"{style}: unexpected {target} tail geometry")
        top_left = left + otRound(slant * (top_y - bottom))
        new_points = [(top_left, top_y)]
        new_flags = [1]
        for index in range(top_keep, bottom_keep + 1):
            new_points.append((otRound(points[index][0]), otRound(points[index][1])))
            new_flags.append(int(flags[index]))
        new_points.append((left, bottom))
        new_flags.append(1)
        if contours == 2:
            for index in range(first_end + 1, ends[1] + 1):
                new_points.append((otRound(points[index][0]), otRound(points[index][1])))
                new_flags.append(int(flags[index]))
        if family == "g":
            # Keep the tail's upper tip below the x-height. Hinting otherwise
            # snaps it into the top row as a detached right shoulder, making
            # the single-storey g look right-shifted at small sizes.
            tip = max(range(len(new_points)), key=lambda index: new_points[index][0])
            x_height = max(y for _, y in new_points)
            new_points[tip] = (new_points[tip][0], min(new_points[tip][1], x_height - 28))
        if contours == 2:
            end_pts = [len(new_points) - 1 - (ends[1] - first_end), len(new_points) - 1]
        else:
            end_pts = [len(new_points) - 1]
        glyph = make_glyph(new_points, end_pts, new_flags)
        glyph.recalcBounds(glyf)
        normalize_overlap(glyph)
        advance = font["hmtx"][target][0]
        glyf[target] = glyph
        metrics[target] = (advance, glyph.xMin)
        roots.add(target)
    refresh_composites(font, roots)


def add_texture_healing(font):
    """Add Monaspace-style Texture Healing alternates and calt lookups."""
    glyf = font["glyf"]
    metrics = font["hmtx"].metrics
    alternates = []

    def alternate(base, suffix, shift=0, grow_left=0, grow_right=0, scale=False):
        source = glyf[base]
        if source.numberOfContours <= 0:
            raise ValueError(f"texture healing: {base} is not a simple glyph")
        points, ends, flags = source.getCoordinates(glyf)
        if shift:
            moved = [(x + shift, y) for x, y in points]
        elif scale:
            factor = 1 + (grow_left + grow_right) / (source.xMax - source.xMin)
            if grow_left and grow_right:
                pivot = (source.xMin + source.xMax) / 2
            else:
                pivot = source.xMax if grow_left else source.xMin
            moved = [(otRound(pivot + (x - pivot) * factor), y) for x, y in points]
        elif grow_left or grow_right:
            # Rigid bands: the outer stems translate, the centre stays put, and
            # only the arches between them stretch.
            middle = (source.xMin + source.xMax) / 2
            half = (source.xMax - source.xMin) / 2
            moved = []
            for x, y in points:
                side = (x - middle) / half
                grow = grow_left if side < 0 else grow_right
                distance = abs(side)
                if not grow or distance <= TEXTURE_HOLD:
                    moved.append((x, y))
                    continue
                reach = min(1.0, (distance - TEXTURE_HOLD) / (TEXTURE_EDGE - TEXTURE_HOLD))
                offset = otRound(grow * reach)
                moved.append((x - offset if side < 0 else x + offset, y))
        else:
            moved = list(points)
        glyph = make_glyph(moved, ends, flags)
        glyph.recalcBounds(glyf)
        normalize_overlap(glyph)
        name = base + suffix
        glyf[name] = glyph
        metrics[name] = (font["hmtx"][base][0], glyph.xMin)
        alternates.append(name)

    for base in TEXTURE_GIVE:
        glyph = glyf[base]
        room = font["hmtx"][base][0] - glyph.xMax
        shift = otRound((glyph.xMax - glyph.xMin) * TEXTURE_GIVE_SHIFT)
        alternate(base, ".tlh.left", shift=-min(shift, glyph.xMin))
        alternate(base, ".tlh.right", shift=min(shift, room))
    for base in TEXTURE_TAKE:
        glyph = glyf[base]
        grow = otRound((glyph.xMax - glyph.xMin) * TEXTURE_TAKE_GROW)
        scale = base in TEXTURE_SCALE_TAKE
        alternate(base, ".tlh.left", grow_left=grow, scale=scale)
        alternate(base, ".tlh.right", grow_right=grow, scale=scale)
        alternate(base, ".tlh.both", grow_left=grow, grow_right=grow, scale=scale)

    order = list(font.getGlyphOrder())
    for name in alternates:
        if name not in order:
            order.append(name)
    font.setGlyphOrder(order)

    def glyph_class(names):
        return " ".join(names)

    give_left = [f"{name}.tlh.left" for name in TEXTURE_GIVE]
    give_right = [f"{name}.tlh.right" for name in TEXTURE_GIVE]
    take_left = [f"{name}.tlh.left" for name in TEXTURE_TAKE]
    take_right = [f"{name}.tlh.right" for name in TEXTURE_TAKE]
    take_both = [f"{name}.tlh.both" for name in TEXTURE_TAKE]
    glyph_names = set(font.getGlyphOrder())
    stationary = [name for name in TEXTURE_STATIONARY if name in glyph_names]
    feature = f"""
@give = [{glyph_class(TEXTURE_GIVE)}];
@give_left = [{glyph_class(give_left)}];
@give_right = [{glyph_class(give_right)}];
@take = [{glyph_class(TEXTURE_TAKE)}];
@take_left = [{glyph_class(take_left)}];
@take_right = [{glyph_class(take_right)}];
@take_both = [{glyph_class(take_both)}];
@stationary = [{glyph_class(stationary)}];

feature calt {{
  lookup giveLeft {{ sub @give' @take by @give_left; }} giveLeft;
  lookup giveRight {{ sub @take @give' by @give_right; }} giveRight;
  lookup center {{ sub @give_left @take' @give_right by @take_both; }} center;
  lookup takeLeft {{ sub @give_left @take' by @take_left; }} takeLeft;
  lookup takeRight {{ sub @take' @give_right by @take_right; }} takeRight;
  lookup stationaryLeft {{ sub @stationary @take' by @take_left; }} stationaryLeft;
  lookup stationaryRight {{ sub @take' @stationary by @take_right; }} stationaryRight;
  lookup stationaryLeftSecond {{
    sub @give_left @take_left' @stationary by @take_both;
  }} stationaryLeftSecond;
  lookup stationaryRightSecond {{
    sub @stationary @take_right' @give_right by @take_both;
  }} stationaryRightSecond;
  lookup stationaryCenter {{
    sub @stationary @take_both' @stationary by @take_both;
    sub @stationary @take_left' @stationary by @take_both;
    sub @stationary @take_right' @stationary by @take_both;
  }} stationaryCenter;
}} calt;
"""

    buffer = BytesIO()
    font.save(buffer, reorderTables=False)
    buffer.seek(0)
    temp = TTFont(buffer)
    del temp["GSUB"]
    addOpenTypeFeaturesFromString(temp, feature)
    temp_gsub = temp["GSUB"].table
    temp_calt = next(
        record for record in temp_gsub.FeatureList.FeatureRecord if record.FeatureTag == "calt"
    )
    main_gsub = font["GSUB"].table
    offset = len(main_gsub.LookupList.Lookup)
    for lookup in temp_gsub.LookupList.Lookup:
        copied = deepcopy(lookup)
        for subtable in copied.SubTable:
            for record in getattr(subtable, "SubstLookupRecord", []) or []:
                record.LookupListIndex += offset
        main_gsub.LookupList.Lookup.append(copied)
    main_gsub.LookupList.LookupCount = len(main_gsub.LookupList.Lookup)
    main_calt = next(
        record for record in main_gsub.FeatureList.FeatureRecord if record.FeatureTag == "calt"
    )
    main_calt.Feature.LookupListIndex = [
        index + offset for index in temp_calt.Feature.LookupListIndex
    ]
    main_calt.Feature.LookupCount = len(main_calt.Feature.LookupListIndex)


def build_face(
    style,
    dest,
    scale,
    shift,
    visible_space=False,
    nerd_icons=False,
    jp_slant=8,
    bold_strength=0,
    regular_strength=0,
    italic_strength=0,
    *,
    version,
):
    with TTFont(INPUT / f"Iosevka-{style}.ttf", recalcTimestamp=False) as font:
        cmap = dict(font.getBestCmap())
        half = font["hmtx"][cmap[32]][0]
        em = font["head"].unitsPerEm
        # Load before appending, while the original GIDs still resolve.
        glyf = font["glyf"]
        metrics = font["hmtx"].metrics
        disable_ligatures(font)
        copy_true_italic(font, style, cmap)
        copy_single_storey_g(font, style, cmap)
        copy_rounded_w(font, style, cmap)
        copy_flat_t(font, style, cmap)
        copy_hanging_m(font, style, cmap)
        widen_r(font, style, cmap)
        lengthen_ij_serifs(font, style, cmap)
        shift_j(font, style, cmap)
        sweep_gj_tails(font, style, cmap)
        add_spacing_ligatures(font, cmap)
        add_script_variants(font, style, cmap)
        add_texture_healing(font)
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
        if style in ("Italic", "BoldItalic"):
            notices.add("0xProto Project Authors (https://github.com/0xType)")
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
        name = "ideographicSpaceMarker"
        glyf[name], bearing = space_marker(half, em, style)
        glyf[name].recalcBounds(glyf)
        metrics[name] = (2 * half, bearing)
        blank = "ideographicSpaceBlank"
        glyf[blank] = Glyph()
        metrics[blank] = (2 * half, 0)
        cmap[0x3000] = name if visible_space else blank
        add_substitution_feature(font, "ss20", cmap[0x3000], blank if visible_space else name)
        decompose_nested_components(glyf)
        font.setGlyphOrder(list(glyf.glyphOrder))
        uvs = [(cp, sel, name) for (cp, sel), name in sorted(variations.items())]
        FontBuilder(font=font).setupCharacterMap(cmap, uvs=uvs, allowFallback=True)
        os2 = font["OS/2"]
        os2.recalcUnicodeRanges(font)
        os2.recalcCodePageRanges(font)
        # Include transformed glyphs in Windows clipping metrics.
        for glyph_name in glyf.glyphOrder:
            glyph = glyf[glyph_name]
            normalize_overlap(glyph)
            if glyph.numberOfContours:
                os2.usWinAscent = max(os2.usWinAscent, glyph.yMax)
                os2.usWinDescent = max(os2.usWinDescent, -glyph.yMin)
        set_names(font, style, "\n".join(sorted(notices)), version)
        if nerd_icons:
            terms = font["name"].getDebugName(13)
            terms += "\nNerd Fonts 3.3.0: see accompanying nerd/ licenses and attributions."
            font["name"].setName(terms, 13, 3, 1, 0x409)
        add_stat(font, style)
        for tag in ("DSIG", "TTFA"):
            if tag in font:
                del font[tag]
        font.save(dest)


def restore_hints(path, style):
    """Re-hint rebuilt glyphs without replacing Iosevka's hint tables.

    The build replaces outlines for g/j/W/w/t/M/r/i and the italic a/f/y, which
    drops their TrueType programs. Iosevka's fpgm/cvt/prep tables are retained,
    so copy only the programs ttfautohint generates for those glyphs. Both sides
    use ttfautohint 1.8.4, which keeps the programs compatible.
    """
    with TTFont(INPUT / f"Iosevka-{style}.ttf", recalcTimestamp=False) as base:
        targets = {
            name
            for name in base.getGlyphOrder()
            if base["glyf"][name].numberOfContours > 0 and base["glyf"][name].program.getBytecode()
        }
    # Iosevka ships i and j as composites, so they have no programs of their own.
    targets.update(("i", "j"))

    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        auto_path = Path(tmp) / path.name
        try:
            subprocess.run(
                ["ttfautohint", "--no-info", str(path), str(auto_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "ttfautohint is required; run the build inside `nix develop`"
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"ttfautohint failed for {path.name}:\n{error.stderr}") from error

        merged = None
        with (
            TTFont(auto_path, recalcTimestamp=False) as auto,
            TTFont(path, recalcTimestamp=False) as font,
        ):
            # A different ttfautohint version can generate programs that do not
            # match Iosevka's retained tables.
            if auto["glyf"]["p"].program.getBytecode() != font["glyf"]["p"].program.getBytecode():
                raise RuntimeError(
                    "ttfautohint output does not match Iosevka's hinting; use ttfautohint 1.8.4"
                )
            changed = False
            for name in font.getGlyphOrder():
                glyph = font["glyf"][name]
                if (
                    name in targets
                    and glyph.numberOfContours > 0
                    and not glyph.program.getBytecode()
                ):
                    source = auto["glyf"][name]
                    if source.numberOfContours > 0 and source.program.getBytecode():
                        glyph.program = deepcopy(source.program)
                        changed = True
            if changed:
                font["maxp"].recalc(font)
                merged = Path(tmp) / "merged.ttf"
                font.save(merged)
        if merged:
            os.replace(merged, path)


def main():
    ensure_inputs()
    cfg = tomllib.loads(CONFIG.read_text())
    japanese, glyphs = cfg["japanese"], cfg["glyphs"]
    scale, shift = japanese["scale"], japanese["baseline_shift"]
    if (
        not math.isfinite(scale)
        or not 0 < scale <= 2
        or type(shift) is not int
        or abs(shift) > 2048
    ):
        raise ValueError(
            "Expected 0 < japanese.scale <= 2 and an integer japanese.baseline_shift within ±2048"
        )
    visible = glyphs.get("visible_fullwidth_space", False)
    if type(visible) is not bool:
        raise ValueError("glyphs.visible_fullwidth_space must be true or false")
    nerd = glyphs.get("nerd_icons", False)
    if type(nerd) is not bool:
        raise ValueError("glyphs.nerd_icons must be true or false")
    angle = japanese.get("italic_degrees", 8)
    if type(angle) not in (int, float) or not 0 <= angle <= 15:
        raise ValueError("japanese.italic_degrees must be between 0 and 15")
    strength = japanese.get("bold_strength", 0)
    if type(strength) is not int or not 0 <= strength <= 48:
        raise ValueError("japanese.bold_strength must be an integer from 0 to 48")
    regular_strength = japanese.get("regular_strength", 0)
    if type(regular_strength) is not int or not 0 <= regular_strength <= 48:
        raise ValueError("japanese.regular_strength must be an integer from 0 to 48")
    italic_strength = japanese.get("italic_strength", 0)
    if type(italic_strength) is not int or not 0 <= italic_strength <= 48:
        raise ValueError("japanese.italic_strength must be an integer from 0 to 48")
    out = DIST
    version = project_version()
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        for style in STYLES:
            build_face(
                style,
                Path(tmp) / f"{FILE_PREFIX}-{style}.ttf",
                scale,
                shift,
                visible,
                nerd,
                angle,
                strength,
                regular_strength,
                italic_strength,
                version=version,
            )
        faces = sorted(Path(tmp).glob("*.ttf"))
        # Family-wide win metrics keep line spacing consistent across styles.
        win_ascent = win_descent = 0
        for path in faces:
            with TTFont(path, recalcTimestamp=False) as font:
                win_ascent = max(win_ascent, font["OS/2"].usWinAscent)
                win_descent = max(win_descent, font["OS/2"].usWinDescent)
        for path in faces:
            with TTFont(path, recalcTimestamp=False) as font:
                os2 = font["OS/2"]
                if (os2.usWinAscent, os2.usWinDescent) == (win_ascent, win_descent):
                    continue
                os2.usWinAscent, os2.usWinDescent = win_ascent, win_descent
                saved = path.with_suffix(".tmp")
                font.save(saved)
            os.replace(saved, path)
        for style in STYLES:
            restore_hints(Path(tmp) / f"{FILE_PREFIX}-{style}.ttf", style)
        for path in faces:
            # Rename after hinting so ttfautohint and the hint merge keep Iosevka's names.
            with TTFont(path, recalcTimestamp=False) as font:
                set_glyph_names(font)
                named = path.with_suffix(".named")
                font.save(named)
            os.replace(named, out / path.name)
    shutil.copyfile(LICENSE, out / LICENSE.name)
    for path in LICENSES.iterdir():
        if path.is_dir():
            shutil.copytree(path, out / path.name, dirs_exist_ok=True)
        else:
            shutil.copyfile(path, out / path.name)


if __name__ == "__main__":
    main()
