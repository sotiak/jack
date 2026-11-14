"""Project and asset locations for the Jack font build."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
ASSETS = PROJECT_ROOT / "assets"
INPUT = ASSETS / "inputs"
LICENSES = ASSETS / "licenses"
LICENSE = PROJECT_ROOT / "LICENSE"
CONFIG = PROJECT_ROOT / "config.toml"
DIST = PROJECT_ROOT / "dist"
IMAGES = PROJECT_ROOT / ".github" / "images"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
SOURCES = ASSETS / "sources.toml"
