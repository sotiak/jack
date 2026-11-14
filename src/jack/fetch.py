"""Download, extract, and verify the pinned third-party font inputs."""

import base64
import hashlib
import json
import shutil
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from collections.abc import Mapping
from pathlib import Path

from .paths import INPUT, SOURCES

HACK_STYLES = ("Regular", "Italic", "Bold", "BoldItalic")
BIZ_WEIGHTS = (400, 700)
BIZ_NUMBERS = range(120)
BIZ_SUBSETS = ("latin", "latin-ext", "cyrillic", "greek-ext")


def _expected_files() -> set[str]:
    files = {f"Hack-{style}.ttf" for style in HACK_STYLES} | {"NerdSymbols.ttf"}
    files.update(
        f"biz-udgothic-{number}-{weight}-normal.woff"
        for number in BIZ_NUMBERS
        for weight in BIZ_WEIGHTS
    )
    files.update(
        f"biz-udgothic-{subset}-{weight}-normal.woff"
        for subset in BIZ_SUBSETS
        for weight in BIZ_WEIGHTS
    )
    return files


def _sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _sources() -> dict[str, dict[str, str]]:
    return tomllib.loads(SOURCES.read_text())


def _source_digest(sources: Mapping[str, Mapping[str, str]]) -> str:
    canonical = json.dumps(sources, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _verify_digest(path: Path, source: Mapping[str, str]) -> None:
    if "sha256" in source:
        actual = _sha256(path)
        if actual != source["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {path.name}: expected {source['sha256']}")
        return

    integrity = source.get("integrity")
    if not integrity:
        raise ValueError(f"No digest configured for {path.name}")
    algorithm, _, encoded = integrity.partition("-")
    with path.open("rb") as file:
        actual = base64.b64encode(hashlib.file_digest(file, algorithm).digest()).decode()
    if actual != encoded:
        raise ValueError(f"Integrity mismatch for {path.name}: expected {encoded}")


def verify_inputs(root: Path = INPUT) -> None:
    sources = _sources()
    lock = root / ".lock"
    if not lock.is_file() or lock.read_text().strip() != _source_digest(sources):
        raise ValueError("Input lock does not match assets/sources.toml")

    missing = sorted(name for name in _expected_files() if not (root / name).is_file())
    if missing:
        raise ValueError(f"Missing inputs: {', '.join(missing)}")


def _download(url: str, dest: Path, source: Mapping[str, str]) -> None:
    print(f"Downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "jack-font-fetch/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, dest.open("wb") as file:
        shutil.copyfileobj(response, file)
    _verify_digest(dest, source)


def _fetch_hack(source: Mapping[str, str], tmp: Path, staging: Path) -> None:
    archive = tmp / "Hack-v3.003-ttf.zip"
    _download(source["url"].format_map(source), archive, source)
    with zipfile.ZipFile(archive) as files:
        for style in HACK_STYLES:
            name = f"Hack-{style}.ttf"
            (staging / name).write_bytes(files.read(f"ttf/{name}"))


def _fetch_biz(source: Mapping[str, str], tmp: Path, staging: Path) -> None:
    archive = tmp / "biz-udgothic.tgz"
    _download(source["url"].format_map(source), archive, source)
    expected = _expected_files()
    with tarfile.open(archive) as files:
        for member in files.getmembers():
            name = Path(member.name).name
            if not member.isfile() or not member.name.startswith("package/files/"):
                continue
            if name not in expected:
                if name.endswith(".woff") and name not in {
                    f"biz-udgothic-japanese-{weight}-normal.woff" for weight in BIZ_WEIGHTS
                }:
                    raise ValueError(f"Unexpected BIZ WOFF file: {member.name}")
                continue
            extracted = files.extractfile(member)
            if extracted is None:
                raise ValueError(f"Cannot read {member.name}")
            (staging / name).write_bytes(extracted.read())


def _fetch_nerd(source: Mapping[str, str], tmp: Path, staging: Path) -> None:
    archive = tmp / "NerdFontsSymbolsOnly.zip"
    _download(source["url"].format_map(source), archive, source)
    with zipfile.ZipFile(archive) as files:
        (staging / "NerdSymbols.ttf").write_bytes(files.read("SymbolsNerdFont-Regular.ttf"))


def fetch_inputs(force: bool = False) -> None:
    if not force:
        try:
            verify_inputs()
            return
        except OSError, ValueError:
            pass

    sources = _sources()
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        staging = tmp / "inputs"
        staging.mkdir()
        _fetch_hack(sources["hack"], tmp, staging)
        _fetch_biz(sources["biz"], tmp, staging)
        _fetch_nerd(sources["nerd"], tmp, staging)
        (staging / ".lock").write_text(_source_digest(sources) + "\n")
        verify_inputs(staging)
        if INPUT.exists():
            shutil.rmtree(INPUT)
        shutil.copytree(staging, INPUT)


def ensure_inputs() -> None:
    try:
        verify_inputs()
    except OSError, ValueError:
        fetch_inputs(force=True)
