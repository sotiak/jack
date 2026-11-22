from io import BytesIO

import pytest
from fontTools.ttLib import TTFont

from jack.build import FILE_PREFIX, font_revision, set_names
from jack.paths import INPUT


def test_serialized_versions_increase():
    previous = -1
    for version, expected in (
        ("0.1.0", 0.01),
        ("0.1.1", 0.0101),
        ("1.9.0", 1.09),
        ("1.10.0", 1.10),
        ("1.99.99", 1.9999),
        ("2.0.0", 2.0),
        ("32767.99.99", 32767.9999),
    ):
        with TTFont(INPUT / "Iosevka-Regular.ttf") as font:
            set_names(font, "Regular", "test", version)
            data = BytesIO()
            font.save(data)
        data.seek(0)
        with TTFont(data) as saved:
            revision = saved["head"].fontRevision
            assert revision == pytest.approx(expected, abs=0.5 / 65536, rel=0)
            assert revision > previous
            assert saved["name"].getDebugName(3) == f"{version};{FILE_PREFIX}-Regular"
            assert saved["name"].getDebugName(5) == f"Version {font_revision(version):.4f}"
            previous = revision


@pytest.mark.parametrize(
    "version",
    ["1.100.0", "1.0.100", "32768.0.0", "01.0.0", "1.01.0", "1.0.01", "1.0", "1.0.0rc1"],
)
def test_invalid_version(version):
    with pytest.raises(ValueError):
        font_revision(version)
