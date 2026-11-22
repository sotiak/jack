import zipfile
from pathlib import Path

import pytest

from jack import fetch


def test_verify_inputs_checks_lock_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = {"iosevka": {"version": "1"}}
    monkeypatch.setattr(fetch, "_sources", lambda: sources)
    expected = fetch._expected_files()
    assert len(expected) == 10

    with pytest.raises(ValueError, match="lock"):
        fetch.verify_inputs(tmp_path)
    (tmp_path / ".lock").write_text(fetch._source_digest(sources))
    with pytest.raises(ValueError, match="Missing inputs"):
        fetch.verify_inputs(tmp_path)
    for name in expected:
        (tmp_path / name).touch()
    fetch.verify_inputs(tmp_path)

    sources["iosevka"]["version"] = "2"
    with pytest.raises(ValueError, match="lock"):
        fetch.verify_inputs(tmp_path)


def test_biz_extracts_ttfs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as files:
        for name in ("BIZUDGothic-Regular.ttf", "BIZUDGothic-Bold.ttf"):
            files.writestr(name, b"font")

    def download(url: str, dest: Path, source: object) -> None:
        dest.write_bytes(archive.read_bytes())

    monkeypatch.setattr(fetch, "_download", download)
    fetch._fetch_biz({"url": "https://example.test"}, tmp_path, tmp_path)
    for name in ("BIZUDGothic-Regular.ttf", "BIZUDGothic-Bold.ttf"):
        assert (tmp_path / name).read_bytes() == b"font"


def test_zeroxproto_extracts_italic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("fonts/0xProto-Italic.ttf", b"font")

    def download(url: str, dest: Path, source: object) -> None:
        dest.write_bytes(archive.read_bytes())

    monkeypatch.setattr(fetch, "_download", download)
    fetch._fetch_zeroxproto({"url": "https://example.test"}, tmp_path, tmp_path)
    assert (tmp_path / fetch.ZEROPROTO).read_bytes() == b"font"
