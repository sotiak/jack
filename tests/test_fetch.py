import io
import tarfile
from pathlib import Path

import pytest

from jack import fetch


def test_verify_inputs_checks_lock_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = {"hack": {"tag": "v1"}}
    monkeypatch.setattr(fetch, "_sources", lambda: sources)
    expected = fetch._expected_files()
    assert len(expected) == 253

    with pytest.raises(ValueError, match="lock"):
        fetch.verify_inputs(tmp_path)
    (tmp_path / ".lock").write_text(fetch._source_digest(sources))
    with pytest.raises(ValueError, match="Missing inputs"):
        fetch.verify_inputs(tmp_path)
    for name in expected:
        (tmp_path / name).touch()
    fetch.verify_inputs(tmp_path)

    sources["hack"]["tag"] = "v2"
    with pytest.raises(ValueError, match="lock"):
        fetch.verify_inputs(tmp_path)


def test_biz_rejects_unknown_woff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "fixture.tgz"
    with tarfile.open(archive, "w:gz") as files:
        for name in ("biz-udgothic-japanese-400-normal.woff", "biz-udgothic-120-400-normal.woff"):
            data = b"font"
            member = tarfile.TarInfo(f"package/files/{name}")
            member.size = len(data)
            files.addfile(member, io.BytesIO(data))

    def download(url: str, dest: Path, source: object) -> None:
        dest.write_bytes(archive.read_bytes())

    monkeypatch.setattr(fetch, "_download", download)
    with pytest.raises(ValueError, match="Unexpected BIZ WOFF file"):
        fetch._fetch_biz({"url": "https://example.test"}, tmp_path, tmp_path)
