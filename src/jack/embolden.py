"""Apply FreeType's outline emboldening in unscaled font units."""

import ctypes as ct
from ctypes.util import find_library
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from PIL import ImageFont


class Vector(ct.Structure):
    _fields_ = [("x", ct.c_long), ("y", ct.c_long)]


class Outline(ct.Structure):
    _fields_ = [
        ("n_contours", ct.c_short),
        ("n_points", ct.c_short),
        ("points", ct.POINTER(Vector)),
        ("tags", ct.POINTER(ct.c_char)),
        ("contours", ct.POINTER(ct.c_short)),
        ("flags", ct.c_int),
    ]


@lru_cache(maxsize=1)
def embolden_function():
    site = Path(ImageFont.__file__).resolve().parent.parent
    bundled = sorted(
        p
        for folder in ("pillow.libs", "PIL/.dylibs", "PIL")
        for p in (site / folder).glob("*freetype*")
        if p.is_file() and any(ext in p.name for ext in (".so", ".dll", ".dylib"))
    )
    library = str(bundled[0]) if bundled else find_library("freetype")
    if not library:
        raise RuntimeError(
            "Install the FreeType shared library, or set both Japanese strength settings to 0"
        )
    fn = ct.CDLL(library).FT_Outline_EmboldenXY
    fn.argtypes = [ct.POINTER(Outline), ct.c_long, ct.c_long]
    fn.restype = ct.c_int
    return fn


def embolden(glyph, strength):
    count = len(glyph.coordinates)
    points = (Vector * count)(*(Vector(x, y) for x, y in glyph.coordinates))
    tags = (ct.c_char * count).from_buffer_copy(glyph.flags)
    ends = (ct.c_short * len(glyph.endPtsOfContours))(*glyph.endPtsOfContours)
    outline = Outline(len(ends), count, points, tags, ends, 0)
    if embolden_function()(ct.byref(outline), strength, strength):
        raise ValueError("FreeType could not embolden this outline")
    # FreeType grows to the right and upwards. Keep the original ink centered.
    offset = strength // 2
    glyph.coordinates = GlyphCoordinates((p.x - offset, p.y - offset) for p in points)
