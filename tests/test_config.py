import pytest

from jack import build
from jack.paths import CONFIG


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("scale = 1.06", "scale = 0.0", "japanese.scale"),
        (
            "visible_fullwidth_space = true",
            "visible_fullwidth_space = 1",
            "glyphs.visible_fullwidth_space",
        ),
        ('zero_style = "feature"', 'zero_style = "invalid"', "glyphs.zero_style"),
    ],
)
def test_invalid_config(tmp_path, monkeypatch, old, new, message):
    path = tmp_path / "config.toml"
    path.write_text(CONFIG.read_text().replace(old, new))
    monkeypatch.setattr(build, "CONFIG", path)
    monkeypatch.setattr(build, "ensure_inputs", lambda: None)
    with pytest.raises(ValueError, match=message.replace(".", r"\.")):
        build.main()
